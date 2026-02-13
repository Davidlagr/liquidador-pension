import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Liquidador Pensional Lagos", page_icon="⚖️", layout="wide")

# --- VALORES LEGALES 2026 ---
# SMMLV 2026: $1.750.905
SMMLV_2026 = 1750905

# --- SEGURIDAD ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<br><br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.title("🔐 Acceso Dr. Lagos")
            password = st.text_input("Ingrese clave maestra:", type="password")
            if st.button("Ingresar"):
                if password == "Lagos2026*":
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ Clave incorrecta")
        return False
    return True

# --- FUNCIONES DE LIMPIEZA ---
def limpiar_num(v):
    if pd.isna(v) or v == '': return 0
    # Quitamos todo lo que no sea número, manejando decimales
    t = re.sub(r'[^\d]', '', str(v).split(',')[0].split('.')[0].strip())
    try: return float(t)
    except: return 0

def extraer_fecha(t_raw):
    # Buscamos patrones AAAA-MM, DD/MM/AAAA o simplemente el año y mes entre el ruido
    t = str(t_raw).strip()
    m = re.search(r'(\d{4})[-/](\d{1,2})|(\d{1,2})/(\d{1,2})/(\d{4})', t)
    if m:
        if m.group(1): return int(m.group(1)), int(m.group(2))
        else: return int(m.group(5)), int(m.group(4))
    return None, None

# --- APLICACIÓN ---
if check_password():
    st.title("⚖️ Sistema Pensional Pro (Ley 797)")
    
    archivo_subido = st.sidebar.file_uploader("Cargar Historia Laboral (PDF)", type="pdf")

    if archivo_subido:
        with st.spinner("Analizando PDF y mapeando columnas..."):
            datos_puros = []
            nombre_cliente = "NO DETECTADO"
            
            # Índices dinámicos (se buscarán en el PDF)
            idx_p, idx_s, idx_d = None, None, None

            with pdfplumber.open(archivo_subido) as pdf:
                # 1. Extraer nombre de la carátula
                texto_p1 = pdf.pages[0].extract_text() or ""
                m_nom = re.search(r"Nombre:\s*\n?(.+?)(?=\n|Dirección:|Estado)", texto_p1, re.IGNORECASE)
                if m_nom: nombre_cliente = m_nom.group(1).strip().upper()

                # 2. Procesar páginas buscando tablas
                for pagina in pdf.pages:
                    tablas = pagina.extract_tables()
                    for tabla in tablas:
                        for fila in tabla:
                            fila_str = [str(c) for c in fila]
                            
                            # BUSCAR COLUMNAS POR TICKET [37], [40], [45]
                            if idx_p is None:
                                for i, celda in enumerate(fila_str):
                                    if "[37]" in celda: idx_p = i
                                    if "[40]" in celda: idx_s = i
                                    if "[45]" in celda: idx_d = i
                            
                            # Si ya tenemos los índices, extraemos datos
                            if idx_p is not None and idx_s is not None and len(fila) > max(idx_p, idx_s):
                                anio, mes = extraer_fecha(fila[idx_p])
                                ibc = limpiar_num(fila[idx_s])
                                # Los días son opcionales, si no está el idx_d usamos 30
                                dias = limpiar_num(fila[idx_d]) if idx_d is not None and len(fila) > idx_d else 30
                                
                                if anio and mes and ibc > 100000: # Filtro de seguridad
                                    datos_puros.append({
                                        "Fecha": datetime(anio, mes, 1),
                                        "Periodo": f"{anio}-{mes:02d}",
                                        "Semanas": dias / 7,
                                        "IBC": ibc
                                    })

            if not datos_puros:
                st.error("❌ No se detectaron datos. Verifique que el PDF contenga los códigos [37], [40] y [45].")
            else:
                df = pd.DataFrame(datos_puros).sort_values("Fecha")
                
                # --- CÁLCULOS ---
                u_f = df["Fecha"].max()
                total_sem = df["Semanas"].sum()
                ibl_vida = df["IBC"].mean()
                f_10y = u_f.replace(year=u_f.year - 10)
                ibl_10y = df[df["Fecha"] >= f_10y]["IBC"].mean()
                
                ibl_final = max(ibl_vida, ibl_10y)
                
                s = ibl_final / SMMLV_2026
                tasa_base = 65.5 - (0.5 * s)
                pts = ((total_sem - 1300)//50)*1.5 if total_sem > 1300 else 0
                tasa_f = max(min(tasa_base + pts, 80.0), 55.0 if total_sem >= 1300 else 0)
                mesada = max(ibl_final * (tasa_f/100), SMMLV_2026)

                # --- DASHBOARD ---
                st.success(f"✅ Historia de {nombre_cliente} procesada con éxito.")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Semanas Totales", f"{total_sem:,.1f}")
                c2.metric("IBL Aplicable", f"${ibl_final:,.0f}")
                c3.metric("Tasa Reemplazo", f"{tasa_f:.2f}%")
                c4.metric("Mesada Estimada", f"${mesada:,.0f}")

                # --- PROYECCIONES AUTOMÁTICAS ---
                st.markdown("---")
                st.subheader("🚀 Proyecciones de Mejora (A 5 años)")
                data_proy = []
                for pct in [0.15, 0.30, 0.50]:
                    ibl_p = ibl_final * (1 + pct)
                    sem_p = total_sem + (5 * 51.42)
                    r_p = 65.5 - (0.5 * (ibl_p / SMMLV_2026))
                    pts_p = ((sem_p - 1300)//50)*1.5 if sem_p > 1300 else 0
                    tasa_p = max(min(r_p + pts_p, 80.0), 55.0)
                    m_p = max(ibl_p * (tasa_p/100), SMMLV_2026)
                    data_proy.append({
                        "Escenario": f"Incremento +{int(pct*100)}%",
                        "IBC Sugerido": f"${ibl_p:,.0f}",
                        "Semanas Finales": round(sem_p, 1),
                        "Mesada Proyectada": f"${m_p:,.0f}",
                        "Mejora Mensual": f"${(m_p - mesada):,.0f}"
                    })
                st.table(data_proy)

                # --- EXPORTAR EXCEL (3 LIBROS) ---
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Libro 1: Liquidación
                    res_df = pd.DataFrame([
                        ("Cliente", nombre_cliente),
                        ("Semanas Totales", total_sem),
                        ("IBL Seleccionado", ibl_final),
                        ("Tasa de Reemplazo", f"{tasa_f:.2f}%"),
                        ("Mesada Actual", mesada),
                        ("SMMLV 2026", SMMLV_2026)
                    ], columns=["Concepto", "Valor"])
                    res_df.to_excel(writer, sheet_name="1_Liquidacion", index=False)
                    
                    # Libro 2: Proyecciones
                    pd.DataFrame(data_proy).to_excel(writer, sheet_name="2_Proyecciones", index=False)
                    
                    # Libro 3: Soporte Detallado
                    df.to_excel(writer, sheet_name="3_Soporte", index=False)
                
                st.download_button(
                    label="📥 Descargar Reporte de 3 Libros",
                    data=output.getvalue(),
                    file_name=f"Liquidacion_{nombre_cliente.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.info("👋 Bienvenido Dr. Lagos. Cargue el PDF de la historia laboral para iniciar.")
