import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, datetime
from data_processor import procesar_pdf_historia_laboral, aplicar_regla_simultaneidad
from logic import LiquidadorPension

st.set_page_config(page_title="Liquidador Pensional Pro", layout="wide", page_icon="⚖️")

# Estilos
st.markdown("""
    <style>
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #2E86C1; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Liquidador de Pensión de Vejez")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Datos del Afiliado")
    nombre = st.text_input("Nombre", "Afiliado")
    identificacion = st.text_input("Identificación")
    fecha_nacimiento = st.date_input("Nacimiento", value=date(1961, 6, 21)) # Fecha ajustada a tu ejemplo
    genero = st.radio("Género", ["Masculino", "Femenino"])

# --- CARGA Y VISUALIZACIÓN ---
st.subheader("1. Carga y Validación de Historia Laboral")
uploaded_file = st.file_uploader("Sube tu Historia Laboral (PDF)", type="pdf")

if uploaded_file:
    # Procesar
    with st.spinner('Procesando datos y separando periodos fusionados...'):
        df_raw = procesar_pdf_historia_laboral(uploaded_file)
        df_final = aplicar_regla_simultaneidad(df_raw)
    
    total_semanas = df_final['Semanas'].sum()
    
    # --- BLOQUE DE VALIDACIÓN DE DATOS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Semanas", f"{total_semanas:,.2f}")
    c2.metric("Periodos Consolidados", len(df_final))
    c3.metric("Rango Fechas", f"{df_final['Desde'].dt.year.min()} - {df_final['Hasta'].dt.year.max()}")
    
    # VISUALIZACIÓN DE LA TABLA (Lo que pediste)
    st.markdown("### 📋 Detalle de Historia Laboral Procesada")
    st.dataframe(
        df_final[['Periodo', 'Desde', 'Hasta', 'Semanas', 'IBC', 'Aportante']].style.format({
            "IBC": "${:,.0f}",
            "Semanas": "{:.2f}"
        }),
        use_container_width=True,
        height=300 # Altura fija con scroll
    )

    # --- LÓGICA DE ESTUDIO ---
    liquidador = LiquidadorPension(df_final, genero, fecha_nacimiento)

    st.divider()
    st.subheader("2. Resultados del Estudio")
    
    tipo = st.radio("Selecciona Análisis:", ["Estudio Pensional (Ley 797 vs Transición)", "Proyección Futura"], horizontal=True)

    if tipo.startswith("Estudio"):
        # Cálculos
        ibl_10, detalle_10 = liquidador.calcular_ibl_indexado("ultimos_10")
        ibl_vida, detalle_vida = liquidador.calcular_ibl_indexado("toda_vida")
        
        col_res1, col_res2 = st.columns(2)
        
        # Gráfica IBL
        with col_res1:
            st.markdown("##### Comparativo IBL (Ingreso Base)")
            chart_data = pd.DataFrame({'IBL': [ibl_10, ibl_vida]}, index=['Últimos 10 Años', 'Toda la Vida'])
            st.bar_chart(chart_data)
        
        with col_res2:
            ibl_favorable = max(ibl_10, ibl_vida)
            origen = "Últimos 10 años" if ibl_10 >= ibl_vida else "Toda la vida"
            st.info(f"💡 IBL Favorable: **{origen}**")
            st.metric("Monto IBL", f"${ibl_favorable:,.0f}")
            
            # Detalle desplegable del IBL
            with st.expander("Ver tabla de indexación (IPC)"):
                detalle_mostrar = detalle_10 if ibl_10 >= ibl_vida else detalle_vida
                st.dataframe(detalle_mostrar)

        # Cálculo Mesada
        mesada, tasa, info = liquidador.calcular_tasa_reemplazo_797(ibl_favorable, total_semanas, datetime.now().year)
        
        st.markdown("---")
        st.success(f"### 💰 Mesada Pensional Estimada: ${mesada:,.0f} (Tasa: {tasa:.2f}%)")
        
        with st.expander("Ver desglose de la fórmula decreciente"):
            st.write(f"**Fórmula Base (r):** {info['r_inicial']:.2f}%")
            st.write(f"**Semanas Extra:** {info['semanas_extra']:.2f} semanas (+ {info['puntos_adicionales']:.2f}%)")
            st.write(f"**Total:** {tasa:.2f}%")

    elif tipo.startswith("Proy"):
        st.info("Módulo de proyección disponible. Selecciona opciones arriba.")
        # Aquí puedes conectar la lógica de proyección si la necesitas en esta vista
