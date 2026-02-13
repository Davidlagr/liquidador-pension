import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Liquidador Pro - Dr. Lagos", page_icon="⚖️", layout="wide")

# SMMLV 2026: $1.750.905
SMMLV_2026 = 1750905

# --- SEGURIDAD ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<br><br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.title("🔐 Acceso Privado")
            password = st.text_input("Ingrese la clave maestra:", type="password")
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
    t = re.sub(r'[^\d]', '', str(v).split(',')[0].split('.')[0].strip())
    try: return float(t)
    except: return 0

def extraer_fecha(t_raw):
    t = str(t_raw).strip()
    m = re.search(r'(\d{4})[-/](\d{1,2})|(\d{1,2})/(\d{1,2})/(\d{4})', t)
    if m:
        if m.group(1): return int(m.group(1)), int(m.group(2))
        else: return int(m.group(5)), int(m.group(4))
    return None, None

# --- APLICACIÓN ---
if check_password():
    st.title("⚖️ Sistema Pensional Pro (Versión 2026.2)")
    st.info("Configurado para detectar códigos [37], [40], [45] con respaldo en columnas D, G, L.")
    
    archivo_subido = st.sidebar.file_uploader("Cargar Historia Laboral (PDF)", type="pdf")

    if archivo_subido:
        with st.spinner("Analizando estructura del PDF..."):
            datos_puros = []
            nombre_cliente = "NO DETECTADO"
            
            # Índices por defecto (D=3, G=6, L=11)
            idx_p, idx_s, idx_d = 3, 6, 11
            columnas_detectadas = False

            with pdfplumber.open(archivo_subido) as pdf:
                # 1. Nombre
                texto_p1 = pdf.pages[0].extract_text() or ""
                m_nom = re.search(r"Nombre:\s*\n?(.+?)(?=\n|Dirección:|Estado)", texto_p1, re.IGNORECASE)
                if m_nom: nombre_cliente = m_nom.group(1).strip().upper()

                # 2. Diagnóstico de primeras filas (para el usuario)
                primeras_filas = []
                
                for pagina in pdf.pages:
                    tablas = pagina.extract_tables()
                    for tabla in tablas:
                        for fila in tabla:
                            fila_str = [str(c) if c else "" for c in fila]
                            
                            # Intentar detectar encabezados si aún no se han detectado
                            if not columnas_detectadas:
                                for i, celda in enumerate(fila_str):
                                    if "37" in celda: idx_p = i; columnas_detectadas = True
                                    if "40" in celda: idx_s = i
                                    if "45" in celda: idx_d = i
                            
                            # Recolección de datos
                            if len(fila) > max(idx_p, idx_s):
                                anio, mes = extraer_fecha(fila[idx_p])
                                ibc = limpiar_num(fila[idx_s])
                                dias = limpiar_num(fila[idx_d]) if len(fila) > idx_d else 30
                                
                                if anio and mes and ibc > 100000:
                                    datos_puros.append({
                                        "Fecha": datetime(anio, mes, 1),
                                        "Periodo": f"{anio}-{mes:02d}",
                                        "Semanas": dias / 7,
                                        "IBC": ibc
                                    })
                            
                            if len(primeras_filas) < 5: primeras_filas.append(fila_str)

            # --- CONSOLA DE DIAGNÓSTICO (Oculta por defecto) ---
            with st.expander("🔍 Ver diagnóstico de lectura del PDF"):
                st.write(f"**Índices usados:** Período: {idx_p} | IBC: {idx_s} | Días: {idx_d}")
                st.write("**Primeras 5 filas detectadas en las tablas:**")
                st.table(primeras_filas)

            if not datos_puros:
                st.error("❌ El sistema no pudo extraer datos. Revise el diagnóstico arriba para ver qué columnas está leyendo el programa.")
            else:
                df = pd.DataFrame(datos_puros).sort_values("Fecha")
                
                # --- CÁLCULOS LEGALES ---
                u_f = df["Fecha"].max()
                total_sem = df["Semanas"].sum()
                ibl_vida = df["IBC"].mean()
                f_10y = u_f.replace(year=u_f.year - 10)
                ibl_10y = df[df["Fecha"] >= f_10y]["IBC"].mean()
                
                ibl_final = max(ibl_vida, ibl_10y)
                
                # Fórmula Ley 797: $R = 65.5 - 0.5 \times (IBL / SMMLV)$
                s = ibl_final / SMMLV_2026
                tasa_base = 65.5 - (0.5 * s)
                pts = ((total_sem - 1300)//50)*1.5 if total_sem > 1300 else 0
                tasa_f = max(min(tasa_base + pts, 80.0), 55.0 if total_sem >= 1300 else 0)
                mesada = max(ibl_final * (tasa_f/100), SMMLV_2026)

                # --- DASHBOARD ---
                st.success(f"✅ Liquidación de {nombre_cliente} calculada.")
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Semanas Totales", f"{total_sem:,.1f}")
                col_b.metric("IBL Aplicado", f"${ibl_final:,.0f}")
                col_c.metric("Tasa Reemplazo", f"{tasa_f:.2f}%")
                col_d.metric("Mesada Estimada", f"${mesada:,.0f}")

                # --- PROYECCIONES ---
                st.markdown("---")
                st.subheader("🚀 Escenarios de Mejora Pensional (A 5 años)")
                data_proy = []
                for pct in [0.15, 0.30, 0.50]:
                    ibl_p = ibl_final * (1 + pct)
                    sem_p = total_sem + (5 * 51.42)
                    r_p = 65.5 - (0.5 * (ibl_p / SMMLV_2026))
                    pts_p = ((sem_p - 1300)//50)*1.5 if sem_p > 1300 else 0
                    tasa_p = max(min(r_p + pts_p, 80.0), 55.0)
                    m_p = max(ibl_p * (tasa_p/100), SMMLV_2026)
                    data_proy.append({
                        "Escenario": f"Mejora +{int(pct*100)}%",
                        "IBC Sugerido": f"${ibl_p:,.0f}",
                        "Semanas Finales": round(sem_p, 1),
                        "Mesada Proyectada": f"${m_p:,.0f}",
                        "Mejora Mensual": f"${(m_p - mesada):,.0f}"
                    })
                st.table(data_proy)

                # --- EXCEL ---
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    pd.DataFrame([("Cliente", nombre_cliente), ("Semanas", total_sem), ("IBL", ibl_final), ("Tasa", tasa_f), ("Mesada", mesada)], columns=["Concepto", "Valor"]).to_excel(writer, sheet_name="1_Liquidacion", index=False)
                    pd.DataFrame(data_proy).to_excel(writer, sheet_name="2_Proyecciones", index=False)
                    df.to_excel(writer, sheet_name="3_Soporte", index=False)
                
                st.download_button(
                    label="📥 Descargar Reporte de 3 Libros",
                    data=output.getvalue(),
                    file_name=f"Liquidacion_{nombre_cliente.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.info("Esperando carga de PDF para procesar la liquidación.")
