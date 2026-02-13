import streamlit as st
import pandas as pd
from data_processor import procesar_pdf_historia_laboral, consolidar_historia_laboral
from logic import LiquidadorPension
from datetime import date

st.set_page_config(page_title="Liquidador Pensional Colombia", layout="wide")

st.title("🏛️ Liquidador de Pensión de Vejez - Colombia")
st.markdown("---")

# --- BARRA LATERAL: DATOS DEL USUARIO ---
st.sidebar.header("Datos del Solicitante")
nombre = st.sidebar.text_input("Nombre Completo")
identificacion = st.sidebar.text_input("Número de Identificación")
fecha_nacimiento = st.sidebar.date_input("Fecha de Nacimiento", value=date(1970, 1, 1))
genero = st.sidebar.selectbox("Género", ["Masculino", "Femenino"])

# --- PASO 1: CARGA DE HISTORIA LABORAL ---
st.header("1. Carga de Historia Laboral")
uploaded_file = st.file_uploader("Sube tu archivo PDF de Colpensiones", type="pdf")

if uploaded_file is not None:
    # 1. Procesar PDF
    df_raw = procesar_pdf_historia_laboral(uploaded_file)
    st.success("Archivo cargado exitosamente.")
    
    # 2. Consolidar (Regla de Simultaneidad)
    df_consolidado = consolidar_historia_laboral(df_raw)
    
    with st.expander("Ver Datos Extraídos y Consolidados"):
        st.dataframe(df_consolidado)
        total_semanas = df_consolidado['Semanas'].sum()
        st.metric("Total Semanas Acreditadas", f"{total_semanas:.2f}")

    # --- PASO 2: SELECCIÓN DE ESTUDIO ---
    st.header("2. Tipo de Estudio")
    tipo_estudio = st.radio(
        "Selecciona el objetivo del análisis:",
        (
            "1. Estudio de Pensión de Vejez (Derechos adquiridos / Retroactivo)",
            "2. Proyección de Mesada Pensional (Futuro)"
        )
    )

    liquidador = LiquidadorPension(df_consolidado, genero, fecha_nacimiento)

    if tipo_estudio.startswith("1"):
        # --- MODULO ESTUDIO PENSION VEJEZ ---
        st.subheader("Análisis Normativo")
        
        # Verificar transición
        tiene_transicion = liquidador.verificar_transicion()
        
        col1, col2 = st.columns(2)
        
        # Calculo IBL Toda la vida
        ibl_vida = liquidador.calcular_ibl(metodo="toda_vida")
        monto_vida, tasa_vida = liquidador.calcular_tasa_reemplazo_ley797(ibl_vida, total_semanas)
        
        # Calculo IBL Ultimos 10
        ibl_10 = liquidador.calcular_ibl(metodo="ultimos_10")
        monto_10, tasa_10 = liquidador.calcular_tasa_reemplazo_ley797(ibl_10, total_semanas)
        
        with col1:
            st.info(f"**Escenario Ley 797 (Toda la vida)**")
            st.write(f"IBL Indexado: ${ibl_vida:,.2f}")
            st.write(f"Tasa Reemplazo: {tasa_vida:.2f}%")
            st.write(f"**Mesada: ${monto_vida:,.2f}**")
            
        with col2:
            st.info(f"**Escenario Ley 797 (Últimos 10 años)**")
            st.write(f"IBL Indexado: ${ibl_10:,.2f}")
            st.write(f"Tasa Reemplazo: {tasa_10:.2f}%")
            st.write(f"**Mesada: ${monto_10:,.2f}**")
        
        mejor_opcion = max(monto_vida, monto_10)
        st.success(f"🎉 La opción más favorable es: **${mejor_opcion:,.2f}**")

    elif tipo_estudio.startswith("2"):
        # --- MODULO PROYECCIÓN ---
        st.subheader("Proyección a Futuro")
        st.warning("Este módulo proyecta tu IBL actual a fechas futuras.")
        
        ibl_actual = liquidador.calcular_ibl(metodo="ultimos_10")
        
        col_A, col_B = st.columns(2)
        
        # Proyección 1300 semanas
        monto_1300, tasa_1300 = liquidador.calcular_tasa_reemplazo_ley797(ibl_actual, 1300)
        col_A.metric("Proyección con 1300 Semanas", f"${monto_1300:,.2f}", f"Tasa: {tasa_1300}%")
        
        # Proyección 1800 semanas
        monto_1800, tasa_1800 = liquidador.calcular_tasa_reemplazo_ley797(ibl_actual, 1800)
        col_B.metric("Proyección con 1800 Semanas", f"${monto_1800:,.2f}", f"Tasa: {tasa_1800}%")

    # --- PASO 3: MEJORAR MI MESADA (SIMULADOR) ---
    st.markdown("---")
    st.header("3. Estrategia: Mejorar mi Mesada Pensional")
    activar_mejora = st.checkbox("Activar simulador de aportes extra")
    
    if activar_mejora:
        tipo_mejora = st.selectbox(
            "Selecciona tu perfil:",
            ["1. Soy Dependiente y quiero cotizar también como Independiente", 
             "2. Soy Independiente y quiero aumentar mi aporte"]
        )
        
        aporte_extra = st.number_input("¿Cuánto dinero adicional puedes aportar al IBC mensualmente?", min_value=0)
        
        if st.button("Simular Impacto"):
            # Lógica simplificada de impacto
            # En un caso real, esto recalcularía el promedio ponderado agregando este valor a los meses futuros
            ibl_actual = liquidador.calcular_ibl(metodo="ultimos_10")
            ibl_mejorado = ibl_actual + aporte_extra # Simplificación matemática
            
            monto_mejorado, tasa_mejorada = liquidador.calcular_tasa_reemplazo_ley797(ibl_mejorado, total_semanas)
            
            diferencia = monto_mejorado - (liquidador.calcular_tasa_reemplazo_ley797(ibl_actual, total_semanas)[0])
            
            st.success(f"Con esta estrategia, tu IBL base subiría a ${ibl_mejorado:,.2f}")
            st.metric("Nueva Mesada Estimada", f"${monto_mejorado:,.2f}", delta=f"+ ${diferencia:,.2f}")

# --- PIE DE PÁGINA ---
st.markdown("---")
st.caption(f"Estudio realizado para: {nombre} | ID: {identificacion}")
st.caption("Nota: Esta herramienta es una simulación académica y no constituye un acto administrativo oficial de Colpensiones.")
