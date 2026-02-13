import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sistema Privado - Dr. Lagos", page_icon="⚖️", layout="wide")

# --- SEGURIDAD ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<br><br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.image("https://cdn-icons-png.flaticon.com/512/1048/1048953.png", width=100)
            st.title("Acceso Restringido")
            st.info("Sistema de Liquidación Pensional | Despacho Jurídico Lagos")
            password = st.text_input("Ingrese la clave maestra:", type="password")
            if st.button("Desbloquear Sistema"):
                if password == "Lagos2026*":
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ Clave incorrecta. Acceso denegado.")
        return False
    return True

# --- INICIO DE LA APP SI LA CLAVE ES CORRECTA ---
if check_password():
    # --- LÓGICA DE SALARIO MÍNIMO ACTUALIZADA 2026 ---
    def obtener_smmlv_automatico():
        anio_actual = datetime.now().year
        historico_smmlv = {
            2024: 1300000,
            2025: 1423500,
            2026: 1750905  # VALOR OFICIAL SEGÚN DECRETO 1469/2025
        }
        return historico_smmlv.get(anio_actual, max(historico_smmlv.values()))

    # --- ESTILOS ---
    st.markdown("""
    <style>
        .main {background-color: #f8f9fa;}
        .stMetric {background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6;}
        .proyeccion-card {background-color: #e3f2fd; padding: 20px; border-radius: 10px; border-left: 5px solid #1976d2;}
    </style>
    """, unsafe_allow_html=True)

    # --- FUNCIONES TÉCNICAS ---
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

    def limpiar_num(v):
        if pd.isna(v): return 0
        t = re.sub(r'[^\d-]', '', str(v).replace("$","").replace(".","").replace(",","").strip())
        try: return float(t)
        except: return 0

    def extraer_fecha(t_raw):
        t = str(t_raw).strip()
        if "-" in t or "/" in t:
            p = re.split(r'[-/]', t)
            if len(p) >= 2:
                try:
                    v1, v2 = int(re.sub(r'\D','',p[0])), int(re.sub(r'\D','',p[1]))
                    if v1 > 1900: return v1, v2
                    elif v2 > 1900: return v2, v1
                except: pass
        return None, None

    # --- INTERFAZ PRINCIPAL ---
    st.title("⚖️ Liquidador Pensional Pro (Ley 797)")
    st.sidebar.title("Panel de Control")
    
    archivo = st.sidebar.file_uploader("Cargar Historia Laboral (PDF)", type="pdf")
    
    smmlv_auto = obtener_smmlv_automatico()
    smmlv_val = st.sidebar.number_input(
        f"SMMLV Vigente ({datetime.now().year})", 
        value=smmlv_auto, 
        step=1000
    )

    if archivo:
        with st.spinner("Analizando documentos..."):
            with pdfplumber.open(archivo) as pdf:
                txt = pdf.pages[0].extract_text()
                m_nom = re.search(r"Nombre:\s*\n?(.+?)(?=\n|Dirección:|Estado)", txt, re.IGNORECASE)
                nombre = m_nom.group(1).strip().upper() if m_nom else "CONSULTA"
            
            archivo.seek(0)
            filas = []
            with pdfplumber.open(archivo) as pdf:
                for p in pdf.pages:
                    for t in p.extract_tables() or []:
                        for f in t: filas.append([str(c).replace('\n', ' ') if c else '' for c in f])
            
            df_raw = pd.DataFrame(filas)
            df_ipc = generar_tabla_ipc()
            
            data_pts = []
            u_a, u_m = 0, 0
            for i, row in df_raw.iterrows():
                if len(row) > 11:
                    a, m = extraer_fecha(row[3])
                    if a and m:
                        if a > u_a or (a==u_a and m>u_m): u_a, u_m = a, m
                        sal, dias = limpiar_num(row[6]), limpiar_num(row[11])
                        if dias > 0 and sal > 0:
                            idx_i = df_ipc[(df_ipc['anio']==a)&(df_ipc['mes']==m)]['indice']
                            if not idx_i.empty:
                                data_pts.append({"Fecha": datetime(a,m,1), "Sem": dias/7, "IBC": sal, "IPC_I": idx_i.values[0]})
            
            if data_pts:
                df = pd.DataFrame(data_pts)
                ipc_f = df_ipc[(df_ipc['anio']==u_a)&(df_ipc['mes']==u_m)]['indice'].values[0] if u_a > 0 else df_ipc.iloc[-1]['indice']
                df["IBL_I"] = df["IBC"] * (ipc_f / df["IPC_I"])
                
                tot_sem = df["Sem"].sum()
                ibl_v = df["IBL_I"].mean()
                f_10 = datetime(u_a, u_m, 1).replace(year=u_a-10)
                ibl_10 = df[df["Fecha"] >= f_10]["IBL_I"].mean()
                ibl_act = max(ibl_v, ibl_10)
                
                # Fórmulas
                r0 = 65.5 - (0.5 * (ibl_act/smmlv_val))
                puntos = ((tot_sem - 1300)//50)*1.5 if tot_sem > 1300 else 0
                tasa_act = max(min(r0 + puntos, 80.0), 55.0 if tot_sem >= 1300 else 0)
                mesada_act = max(ibl_act * (tasa_act/100), smmlv_val)

                # DASHBOARD
                st.subheader(f"👤 Cliente: {nombre}")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Semanas", f"{tot_sem:,.1f}")
                m2.metric("IBL Hoy", f"${ibl_act:,.0f}")
                m3.metric("Tasa", f"{tasa_act:.1f}%")
                m4.metric("Mesada Hoy", f"${mesada_act:,.0f}")

                st.divider()

                # PROYECCIÓN
                st.subheader("🚀 Simulador de Invers
