import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Liquidador Pensional Pro - Dr. Lagos", page_icon="⚖️", layout="wide")

# --- ESTILOS PERSONALIZADOS ---
st.markdown("""
<style>
    .main {background-color: #f4f7f6;}
    .stMetric {background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
    .proyeccion-box {background-color: #e3f2fd; padding: 20px; border-radius: 10px; border-left: 5px solid #2196f3;}
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

# --- FUNCIONES TÉCNICAS ---
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

def calcular_pila(ibc):
    # Cálculo simplificado de aportes a pensión (16%) + Fondo Solidaridad
    ibc = max(min(ibc, 1300000 * 25), 1300000)
    tasa = 0.16
    if ibc >= 1300000 * 4: tasa += 0.01 # Fondo Solidaridad
    return ibc * tasa

# --- INTERFAZ ---
st.title("⚖️ Liquidador Pensional Dr. Lagos")
st.markdown("---")

archivo = st.sidebar.file_uploader("Subir Historia Laboral PDF", type="pdf")

if archivo:
    with st.spinner("Procesando..."):
        # Extracción inicial
        with pdfplumber.open(archivo) as pdf:
            txt = pdf.pages[0].extract_text()
            m_nom = re.search(r"Nombre:\s*\n?(.+?)(?=\n|Dirección:|Estado)", txt, re.IGNORECASE)
            nombre = re.sub(r"[^\w\sÑñ]", "", m_nom.group(1).strip().upper()) if m_nom else "Cliente"
            
        archivo.seek(0)
        filas = []
        with pdfplumber.open(archivo) as pdf:
            for p in pdf.pages:
                for t in p.extract_tables() or []:
                    for f in t: filas.append([str(c).replace('\n', ' ') if c else '' for c in f])
        
        df_raw = pd.DataFrame(filas)
        df_ipc = generar_tabla_ipc()
        
        datos = []
        u_anio, u_mes = 0, 0
        SMMLV = 1300000
        
        for i, row in df_raw.iterrows():
            if len(row) > 11:
                a, m = extraer_fecha_segura(row[3])
                if a and m:
                    if a > u_anio or (a==u_anio and m>u_mes): u_anio, u_mes = a, m
                    sal = limpiar_numero(row[6])
                    dias = limpiar_numero(row[11])
                    if dias > 0 and sal > 0:
                        ipc_i = obtener_ipc(df_ipc, a, m)
                        if ipc_i:
                            datos.append({"Fecha": datetime(a, m, 1), "Sem": dias/7, "IBC": sal, "IPC_I": ipc_i})
        
        if datos:
            df = pd.DataFrame(datos)
            ipc_f = obtener_ipc(df_ipc, u_anio, u_mes) or df_ipc.iloc[-1]['indice']
            df["IBL_I"] = df["IBC"] * (ipc_f / df["IPC_I"])
            
            total_sem = df["Sem"].sum()
            ibl_vida = df["IBL_I"].mean()
            f_10y = datetime(u_anio, u_mes, 1).replace(year=u_anio-10)
            ibl_10 = df[df["Fecha"] >= f_10y]["IBL_I"].mean()
            ibl_actual = max(ibl_vida, ibl_10)
            
            # Tasa Reemplazo
            r = 65.5 - (0.5 * (ibl_actual/SMMLV))
            pts = ((total_sem - 1300)//50)*1.5 if total_sem > 1300 else 0
            t_fin = max(min(r + pts, 80.0), 55.0 if total_sem >= 1300 else 0)
            mesada_actual = max(ibl_actual * (t_fin/100), SMMLV)

            # --- VISTA DE RESULTADOS ---
            st.subheader(f"📊 Situación Actual: {nombre}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Semanas", f"{total_sem:,.1f}")
            c2.metric("IBL Actual", f"${ibl_actual:,.0f}")
            c3.metric("Tasa", f"{t_fin:.1f}%")
            c4.metric("Mesada Hoy", f"${mesada_actual:,.0f}")
            
            st.markdown("---")
            
            # --- MÓDULO DE PROYECCIÓN MEJORADO ---
            st.subheader("🚀 Simulador de Mejora Pensional")
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                anios_futuros = st.slider("Años adicionales a cotizar", 1, 15, 5)
                ibc_proyectado = st.number_input("Nuevo IBC sugerido", value=int(SMMLV
