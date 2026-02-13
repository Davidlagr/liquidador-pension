import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Liquidador Pensional Pro - Dr. Lagos", page_icon="⚖️", layout="wide")

# --- PARÁMETROS LEGALES 2026 ---
SMMLV_2026 = 1750905  # Valor actualizado según requerimiento
TOPE_25_SMMLV = SMMLV_2026 * 25

# --- ESTILOS PERSONALIZADOS ---
st.markdown("""
<style>
    .main {background-color: #f4f7f6;}
    .stMetric {background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
    .proyeccion-box {background-color: #e3f2fd; padding: 20px; border-radius: 10px; border-left: 5px solid #2196f3; margin-bottom: 10px;}
    .scenario-card {padding: 15px; border-radius: 8px; border: 1px solid #ddd; background-color: white;}
</style>
""", unsafe_allow_html=True)

# --- BASE DE DATOS IPC (Ajustada) ---
@st.cache_data
def generar_tabla_ipc():
    historico = {
        1994: 15.02, 1995: 17.94, 1996: 21.83, 1997: 25.69, 1998: 30.01,
        1999: 32.78, 2000: 35.65, 2001: 38.37, 2002: 41.05, 2003: 43.71,
        2004: 46.11, 2005: 48.35, 2006: 50.51, 2007: 53.38, 2008: 57.47,
        2009: 58.62, 2010: 60.48, 2011: 62.74, 2012: 64.27, 2013: 65.52,
        2014: 67.92, 2015: 72.52, 2016: 76.69, 2017: 79.83, 2018: 82.37,
        2019: 85.50, 2020: 86.88, 2021: 91.77, 2022: 103.84, 2023: 113.48,
        2024: 121.00, 2025: 128.50, 2026: 135.00
    }
    datos = []
    anios = sorted(historico.keys())
    for i in range(len(anios)-1):
        a1, a2 = anios[i], anios[i+1]
        v1, v2 = historico[a1], historico[a2]
        delta = (v2 - v1) / 12
        for mes in range(1, 13):
            datos.append({"anio": a1, "mes": mes, "indice": v1 + (delta * (mes-1))})
    return pd.DataFrame(datos)

# --- FUNCIONES DE CÁLCULO ---
def limpiar_numero(valor):
    if pd.isna(valor) or valor == '': return 0.0
    texto = re.sub(r'[^\d.]', '', str(valor).replace(",", "."))
    try: return float(texto)
    except: return 0.0

def calcular_mesada(ibl, semanas):
    if semanas < 1300: return 0
    # Tasa de reemplazo: r = 65.5 - 0.5 * (IBL / SMMLV)
    r = 65.5 - (0.5 * (ibl / SMMLV_2026))
    # Puntos adicionales por cada 50 semanas después de las 1300
    pts = ((semanas - 1300) // 50) * 1.5
    tasa_final = max(min(r + pts, 80.0), 55.0)
    return max(ibl * (tasa_final / 100), SMMLV_2026)

# --- INTERFAZ ---
st.title("⚖️ Liquidador Pensional Dr. Lagos - Edición 2026")
st.markdown("---")

archivo = st.sidebar.file_uploader("Subir Historia Laboral PDF", type="pdf")

if archivo:
    try:
        with st.spinner("Analizando Historia Laboral..."):
            filas = []
            with pdfplumber.open(archivo) as pdf:
                # Intento de extraer nombre en la primera página
                txt_primera = pdf.pages[0].extract_text() or ""
                m_nom = re.search(r"Nombre:\s*(.+)", txt_primera, re.IGNORECASE)
                nombre_cliente = m_nom.group(1).strip() if m_nom else "Cliente"
                
                # Extracción de tablas de todas las páginas
                for page in pdf.pages:
                    tablas = page.extract_tables()
                    for t in tablas:
                        for f in t:
                            # Filtramos filas que parezcan tener datos (mínimo 7 columnas)
                            if len(f) >= 7:
                                filas.append(f)

            if not filas:
                st.error("❌ No se detectaron tablas con datos en el PDF. Verifique el formato.")
            else:
                df_raw = pd.DataFrame(filas)
                df_ipc = generar_tabla_ipc()
                
                # Procesamiento de IBC y Semanas (Basado en índices G[6] y L[11])
                datos_limpios = []
                for _, row in df_raw.iterrows():
                    try:
                        # Columna 3 suele ser Periodo, 6 IBC, 11 Días
                        ibc_val = limpiar_numero(row[6])
                        dias_val = limpiar_numero(row[11])
                        if ibc_val > 0:
                            semanas = dias_val / 7
                            datos_limpios.append({"IBC": ibc_val, "Sem": semanas})
                    except:
                        continue

                df = pd.DataFrame(datos_limpios)
                
                if df.empty:
                    st.warning("⚠️ Se leyó el archivo pero no se encontraron valores de IBC válidos.")
                else:
                    # --- RESULTADOS ACTUALES ---
                    total_sem = df["Sem"].sum()
                    ibl_actual = df["IBC"].tail(120).mean() # Promedio últimos 10 años aprox
                    mesada_hoy = calcular_mesada(ibl_actual, total_sem)

                    st.subheader(f"📊 Resumen Ejecutivo: {nombre_cliente}")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Semanas Totales", f"{total_sem:,.1f}")
                    c2.metric("IBL (Promedio)", f"${ibl_actual:,.0f}")
                    c3.metric("Mesada Estimada", f"${mesada_hoy:,.0f}")
                    c4.metric("Estado", "Derecho Adquirido" if total_sem >= 1300 else "En Proceso")

                    st.markdown("---")

                    # --- MÓDULO DE ESCENARIOS (SOLICITADO) ---
                    st.subheader("🚀 Simulador de Mejora de la Prestación")
                    st.write("Cálculo de impacto basado en el incremento del Ingreso Base de Cotización (IBC):")

                    def mostrar_escenario(pct_texto, multiplicador):
                        ibl_proy = ibl_actual * multiplicador
                        # Aplicar topes
                        ibl_proy = min(max(ibl_proy, SMMLV_2026), TOPE_25_SMMLV)
                        mesada_proy = calcular_mesada(ibl_proy, total_sem)
                        mejora = mesada_proy - mesada_hoy
                        
                        with st.container():
                            st.markdown(f"""
                            <div class="scenario-card">
                                <h4>Escenario {pct_texto}</h4>
                                <p>Nuevo IBL: <b>${ibl_proy:,.0f}</b></p>
                                <p>Nueva Mesada: <b>${mesada_proy:,.0f}</b></p>
                                <p style="color:green;">Incremento mensual: <b>+ ${mejora:,.0f}</b></p>
                            </div>
                            """, unsafe_allow_html=True)

                    col_e1, col_e2, col_e3 = st.columns(3)
                    with col_e1: mostrar_escenario("+20%", 1.20)
                    with col_e2: mostrar_escenario("+30%", 1.30)
                    with col_e3: mostrar_escenario("+50%", 1.50)

                    st.info("💡 **Nota del Dr. Lagos:** Estos escenarios asumen que el incremento se aplica al promedio de liquidación final. Los valores son proyectados a 2026.")

    except Exception as e:
        st.error(f"⚠️ Error crítico al procesar el documento: {e}")
        st.write("Sugerencia: Asegúrese de que el PDF no esté protegido con contraseña.")

else:
    st.info("👈 Dr. Lagos, por favor cargue la Historia Laboral en el panel izquierdo para comenzar.")
