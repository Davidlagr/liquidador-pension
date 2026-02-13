import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Liquidador Pensional - Dr. Lagos",
    page_icon="⚖️",
    layout="wide"
)

# --- ESTILOS ---
st.markdown("""
<style>
    .main {background-color: #f4f6f9;}
    h1 {color: #1f2c56; font-family: 'Arial';}
    .stMetric {background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
    div[data-testid="stExpander"] {background-color: white; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# --- BASE DE DATOS IPC ---
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
            datos.append({"anio": a1 + 1, "mes": mes, "indice": v1 + (delta * mes)})
    return pd.DataFrame(datos)

# --- FUNCIONES DE APOYO ---
def limpiar_numero(valor):
    if pd.isna(valor): return 0
    texto = re.sub(r'[^\d-]', '', str(valor).replace("$", "").replace(".", "").replace(",", "").strip())
    try: return float(texto)
    except: return 0

def extraer_fecha_segura(texto_raw):
    texto = str(texto_raw).strip()
    anio, mes = 0, 0
    if "-" in texto or "/" in texto:
        partes = re.split(r'[-/]', texto)
        if len(partes) >= 2:
            try:
                v1, v2 = int(re.sub(r'\D','',partes[0])), int(re.sub(r'\D','',partes[1]))
                if v1 > 1900: anio, mes = v1, v2
                elif v2 > 1900: anio, mes = v2, v1
            except: pass
    elif texto.isdigit() and len(texto) == 6:
        try: anio, mes = int(texto[:4]), int(texto[4:])
        except: pass
    if 1900 < anio < 2030 and 1 <= mes <= 12: return anio, mes
    return None, None

def obtener_ipc(df_ipc, anio, mes):
    row = df_ipc[(df_ipc['anio'] == anio) & (df_ipc['mes'] == mes)]
    return row.iloc[0]['indice'] if not row.empty else None

def extraer_metadatos_pdf(pdf_file):
    datos = {"Nombre": "No detectado", "Edad": 0, "Nacimiento": "N/A"}
    try:
        with pdfplumber.open(pdf_file) as pdf:
            txt = pdf.pages[0].extract_text()
            m_nom = re.search(r"Nombre:\s*\n?(.+?)(?=\n|Dirección:|Estado)", txt, re.IGNORECASE)
            if m_nom: datos["Nombre"] = re.sub(r"[^\w\sÑñ]", "", m_nom.group(1).strip().upper())
            m_nac = re.search(r"(\d{2}/\d{2}/\d{4})", txt)
            if m_nac:
                datos["Nacimiento"] = m_nac.group(1)
                fn = datetime.strptime(m_nac.group(1), '%d/%m/%Y')
                hoy = datetime.now()
                datos["Edad"] = hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))
    except: pass
    return datos

# --- INTERFAZ PRINCIPAL ---
st.title("⚖️ Sistema de Liquidación Pensional Online")
st.markdown("**Desarrollado para el Dr. David Lagos Riaño**")
st.divider()

# Sidebar para carga de archivos
with st.sidebar:
    st.header("Configuración")
    archivo = st.file_uploader("Subir Historia Laboral PDF", type="pdf")
    st.info("Utilice el formato oficial de Colpensiones.")

if archivo:
    with st.spinner("Procesando información..."):
        # 1. Extraer datos personales
        info = extraer_metadatos_pdf(archivo)
        
        # 2. Extraer tablas
        archivo.seek(0)
        filas = []
        with pdfplumber.open(archivo) as pdf:
            for p in pdf.pages:
                for t in p.extract_tables() or []:
                    for f in t:
                        filas.append([str(c).replace('\n', ' ') if c else '' for c in f])
        
        df_raw = pd.DataFrame(filas)
        df_ipc = generar_tabla_ipc()

        # 3. Cálculos técnicos
        datos_calc = []
        ultimo_anio, ultimo_mes = 0, 0
        SMMLV = 1300000

        # Identificar fecha de corte
        for i, row in df_raw.iterrows():
            if len(row) > 3:
                a, m = extraer_fecha_segura(row[3])
                if a and m:
                    if a > ultimo_anio or (a==ultimo_anio and m>ultimo_mes):
                        ultimo_anio, ultimo_mes = a, m
        
        ipc_final = obtener_ipc(df_ipc, ultimo_anio, ultimo_mes) or df_ipc.iloc[-1]['indice']

        # Procesar periodos
        for i, row in df_raw.iterrows():
            if len(row) > 11:
                sal = limpiar_numero(row[6])
                dias = limpiar_numero(row[11])
                a, m = extraer_fecha_segura(row[3])
                if a and m and dias > 0 and sal > 0:
                    ipc_ini = obtener_ipc(df_ipc, a, m)
                    if ipc_ini:
                        datos_calc.append({
                            "Fecha": datetime(a, m, 1),
                            "Periodo": f"{a}-{m:02d}",
                            "Semanas": dias/7,
                            "IBC": sal,
                            "Factor": ipc_final/ipc_ini,
                            "IBL_Ind": sal * (ipc_final/ipc_ini)
                        })

        if datos_calc:
            df_final = pd.DataFrame(datos_calc)
            total_sem = df_final["Semanas"].sum()
            ibl_vida = df_final["IBL_Ind"].mean()
            
            # IBL 10 años
            f_limite = datetime(ultimo_anio, ultimo_mes, 1).replace(year=ultimo_anio-10)
            df_10 = df_final[df_final["Fecha"] >= f_limite]
            ibl_10 = df_10["IBL_Ind"].mean() if not df_10.empty else 0
            
            ibl_favorable = max(ibl_vida, ibl_10)
            
            # Tasa de reemplazo
            r = 65.5 - (0.5 * (ibl_favorable/SMMLV))
            puntos = ((total_sem - 1300)//50)*1.5 if total_sem > 1300 else 0
            tasa_final = max(min(r + puntos, 80.0), 55.0 if total_sem >= 1300 else 0)
            mesada = max(ibl_favorable * (tasa_final/100), SMMLV)

            # --- VISTA DE RESULTADOS ---
            st.success(f"Análisis realizado para: **{info['Nombre']}**")
            
            res1, res2, res3, res4 = st.columns(4)
            res1.metric("Edad Actual", f"{info['Edad']} años")
            res2.metric("Semanas Totales", f"{total_sem:,.1f}")
            res3.metric("Tasa Reemplazo", f"{tasa_final:.2f}%")
            res4.metric("Mesada Estimada", f"${mesada:,.0f}")

            st.divider()
            
            col_izq, col_der = st.columns(2)
            with col_izq:
                st.subheader("Comparativa IBL")
                st.write(f"**IBL Toda la vida:** ${ibl_vida:,.0f}")
                st.write(f"**IBL Últimos 10 años:** ${ibl_10:,.0f}")
                st.info(f"IBL más favorable: **${ibl_favorable:,.0f}**")
            
            with col_der:
                st.subheader("Exportación")
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_final.to_excel(writer, index=False, sheet_name="Soporte_Liquidacion")
                st.download_button(
                    label="📥 Descargar Soporte Excel",
                    data=buffer.getvalue(),
                    file_name=f"Liquidacion_{info['Nombre']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            with st.expander("Ver detalle de cotizaciones"):
                st.dataframe(df_final.sort_values("Fecha", ascending=False))
        else:
            st.error("No se detectaron periodos de cotización válidos en el PDF.")
else:
    st.info("👈 Por favor, suba el archivo PDF en el panel lateral para comenzar.")
