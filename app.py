import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, datetime
from data_processor import procesar_pdf_historia_laboral, aplicar_regla_simultaneidad
from logic import LiquidadorPension

st.set_page_config(page_title="Liquidador Pensional Pro", layout="wide", page_icon="⚖️")

st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #2E86C1; }
    </style>
""", unsafe_allow_html=True)

st.title("⚖️ Liquidador de Pensión: Auditoría y Cálculo")

# --- SIDEBAR ---
with st.sidebar:
    st.header("👤 Afiliado")
    nombre = st.text_input("Nombre", "Usuario")
    identificacion = st.text_input("Cédula")
    fecha_nacimiento = st.date_input("Fecha Nacimiento", value=date(1975, 1, 1))
    genero = st.radio("Género", ["Masculino", "Femenino"])

# --- PASO 1: CARGA ---
st.header("1. Carga de Datos")
uploaded_file = st.file_uploader("Sube historia laboral (PDF)", type="pdf")

if uploaded_file:
    with st.spinner('Decodificando archivo y extrayendo valores...'):
        df_raw = procesar_pdf_historia_laboral(uploaded_file)
        
        if df_raw.empty:
            st.error("No se encontraron datos. Verifica el archivo.")
            st.stop()
            
        df_final = aplicar_regla_simultaneidad(df_raw)

    # --- VERIFICACIÓN DE DATOS (CRUCIAL) ---
    total_semanas = df_final['Semanas'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Semanas Leídas", f"{total_semanas:,.2f}")
    c2.metric("Registros", len(df_final))
    c3.metric("Rango", f"{df_final['Desde'].dt.year.min()} - {df_final['Hasta'].dt.year.max()}")
    
    st.info("👇 Revisa esta tabla. Si el IBC o Semanas están mal aquí, el PDF tiene un formato inusual.")
    with st.expander("🔍 AUDITORÍA DE DATOS EXTRAÍDOS (Clic para abrir/cerrar)", expanded=True):
        st.dataframe(
            df_final[['Periodo', 'Desde', 'Hasta', 'Semanas', 'IBC', 'Aportante']].style.format({
                "IBC": "${:,.0f}",
                "Semanas": "{:.2f}",
                "Desde": "{:%d-%m-%Y}",
                "Hasta": "{:%d-%m-%Y}"
            }),
            use_container_width=True,
            height=400
        )

    # --- PASO 2: CÁLCULOS ---
    st.divider()
    liquidador = LiquidadorPension(df_final, genero, fecha_nacimiento)
    
    opcion = st.radio("Tipo de Análisis:", 
                      ["1. Estudio Pensional (Normativa Vigente)", 
                       "2. Proyección Futura"])

    if opcion.startswith("1"):
        col1, col2 = st.columns(2)
        
        # IBL
        ibl_10, det_10 = liquidador.calcular_ibl_indexado("ultimos_10")
        ibl_vida, det_vida = liquidador.calcular_ibl_indexado("toda_vida")
        
        ibl_fav = max(ibl_10, ibl_vida)
        origen = "Últimos 10" if ibl_10 >= ibl_vida else "Toda la Vida"
        
        with col1:
            st.subheader("Análisis IBL")
            st.bar_chart(pd.DataFrame({'IBL': [ibl_10, ibl_vida]}, index=['Últimos 10', 'Toda Vida']))
            st.write(f"**IBL Favorable:** {origen}")
            
        with col2:
            st.subheader("Resultado Pensión")
            mesada, tasa, info = liquidador.calcular_tasa_reemplazo_797(ibl_fav, total_semanas, datetime.now().year)
            
            st.metric("Mesada Estimada", f"${mesada:,.0f}")
            st.metric("Tasa Reemplazo", f"{tasa:.2f}%")
            
            with st.expander("Ver detalle fórmula"):
                st.write(info)

    elif opcion.startswith("2"):
        st.subheader("Proyección")
        ibl, _ = liquidador.calcular_ibl_indexado("ultimos_10")
        
        # Proyección simple 1300
        m_1300, t_1300, _ = liquidador.calcular_tasa_reemplazo_797(ibl, 1300, datetime.now().year + 5)
        st.metric("Proyección 1300 Semanas", f"${m_1300:,.0f}", f"Tasa: {t_1300}%")
