import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Despacho Lagos Pro", page_icon="⚖️", layout="wide")

# SMMLV 2026 OFICIAL
SMMLV_2026 = 1750905

# --- SEGURIDAD ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Privado - Dr. Lagos")
        password = st.text_input("Ingrese la clave maestra:", type="password")
        if st.button("Ingresar"):
            if password == "Lagos2026*":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ Clave incorrecta")
        return False
    return True

# --- FUNCIONES TÉCNICAS ---
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
    st.title("⚖️ Sistema de Liquidación Pensional")
    archivo_subido = st.sidebar.file_uploader("Subir Historia Laboral PDF", type="pdf")

    if archivo_subido:
        with st.spinner("Procesando..."):
            datos_puros = []
            nombre_cliente = "No detectado"
            
            with pdfplumber.open(archivo_subido) as pdf:
                # Nombre
                texto_p1 = pdf.pages[0].extract_text() or ""
                m_nom = re.search(r"Nombre:\s*\n?(.+?)(?=\n|Dirección:|Estado)", texto_p1, re.IGNORECASE)
                if m_nom: nombre_cliente = m_nom.group(1).strip().upper()

                # Tablas
                for pagina in pdf.pages:
                    tablas = pagina.extract_tables()
                    for tabla in tablas:
                        for fila in tabla:
                            if len(fila) > 11:
                                anio, mes = extraer_fecha(fila[3])
                                ibc = limpiar_num(fila[6])
                                dias = limpiar_num(fila[11])
                                if anio and mes and ibc > 0:
                                    datos_puros.append({"Fecha": datetime(anio, mes, 1), "Periodo": f"{anio}-{mes:02d}", "Semanas": dias/7, "IBC": ibc})

            if not datos_puros:
                st.error("No se detectaron datos en las columnas 3, 6 y 11.")
            else:
                df = pd.DataFrame(datos_puros).sort_values("Fecha")
                u_f = df["Fecha"].max()
                total_sem = df["Semanas"].sum()
                ibl_vida = df["IBC"].mean()
                f_10y = u_f.replace(year=u_f.year - 10)
                ibl_10y = df[df["Fecha"] >= f_10y]["IBC"].mean()
                ibl_final = max(ibl_vida, ibl_10y)
                
                # Tasa y Mesada
                s = ibl_final / SMMLV_2026
                tasa_base = 65.5 - (0.5 * s)
                pts = ((total_sem - 1300)//50)*1.5 if total_sem > 1300 else 0
                tasa_f = max(min(tasa_base + pts, 80.0), 55.0 if total_sem >= 1300 else 0)
                mesada = max(ibl_final * (tasa_f/100), SMMLV_2026)

                # Dashboard
                st.subheader(f"👤 Cliente: {nombre_cliente}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Semanas", f"{total_sem:,.1f}")
                c2.metric("IBL Aplicado", f"${ibl_final:,.0f}")
                c3.metric("Tasa Reemplazo", f"{tasa_f:.2f}%")
                c4.metric("Mesada Estimada", f"${mesada:,.0f}")

                # Proyecciones
                st.markdown("---")
                st.subheader("📈 Escenarios de Mejora (A 5 años)")
                data_proy = []
                for pct in [0.15, 0.30, 0.50]:
                    ibl_p = ibl_final * (1 + pct)
                    sem_p = total_sem + (5 * 51.42)
                    r_p = 65.5 - (0.5 * (ibl_p / SMMLV_2026))
                    pts_p = ((sem_p - 1300)//50)*1.5 if sem_p > 1300 else 0
                    tasa_p = max(min(r_p + pts_p, 80.0), 55.0)
                    m_p = max(ibl_p * (tasa_p/100), SMMLV_2026)
                    data_proy.append({"Escenario": f"+{int(pct*100)}%", "IBL Proyectado": f"${ibl_p:,.0f}", "Semanas": round(sem_p, 1), "Mesada": f"${m_p:,.0f}"})
                st.table(data_proy)

                # Exportar Excel (3 Libros)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    pd.DataFrame([("Cliente", nombre_cliente), ("Semanas", total_sem), ("IBL", ibl_final), ("Mesada", mesada)], columns=["C", "V"]).to_excel(writer, sheet_name="Resumen", index=False)
                    pd.DataFrame(data_proy).to_excel(writer, sheet_name="Proyecciones", index=False)
                    df.to_excel(writer, sheet_name="Soporte", index=False)
                
                st.download_button(label="📥 Descargar Reporte Completo (3 Libros)", data=output.getvalue(), file_name=f"Liquidacion_{nombre_cliente}.xlsx", mime="application/vnd.ms-excel")
    else:
        st.info("Suba el archivo PDF para iniciar.")
