import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, datetime
from data_processor import procesar_pdf_historia_laboral, aplicar_regla_simultaneidad
from logic import LiquidadorPension

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Liquidador Pensional Pro", layout="wide", page_icon="⚖️")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #2E86C1; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Liquidador de Pensión de Vejez")
st.markdown("Herramienta avanzada para el análisis y proyección pensional en Colombia.")

# --- SIDEBAR: DATOS DEL AFILIADO ---
with st.sidebar:
    st.header("👤 Datos del Afiliado")
    nombre = st.text_input("Nombre Completo", "Afiliado Ejemplo")
    identificacion = st.text_input("Número de Identificación")
    fecha_nacimiento = st.date_input("Fecha de Nacimiento", value=date(1970, 1, 1))
    genero = st.radio("Género", ["Masculino", "Femenino"])
    
    st.info("ℹ️ El sistema calcula automáticamente la reducción de semanas para mujeres a partir de 2026.")

# --- PASO 1: CARGA Y VALIDACIÓN DE HISTORIA LABORAL ---
st.subheader("1. Carga de Historia Laboral (PDF Colpensiones)")
uploaded_file = st.file_uploader("Sube tu archivo PDF aquí", type="pdf")

if uploaded_file:
    with st.spinner('Procesando datos y aplicando reglas de simultaneidad...'):
        # 1. Procesamiento inicial
        df_raw = procesar_pdf_historia_laboral(uploaded_file)
        
        # --- BLOQUE DE SEGURIDAD ANTI-ERROR ---
        if df_raw.empty:
            st.error("⚠️ No se encontraron datos válidos en el archivo. Por favor verifica que sea el PDF original de 'Historia Laboral Unificada' descargado de Colpensiones y que no sea una imagen escaneada.")
            st.stop() # Detiene la ejecución para no mostrar errores técnicos
        # --------------------------------------

        # 2. Aplicar regla de simultaneidad
        df_final = aplicar_regla_simultaneidad(df_raw)
    
    # Cálculos básicos para resumen
    total_semanas = df_final['Semanas'].sum()
    min_fecha = df_final['Desde'].min()
    max_fecha = df_final['Hasta'].max()
    
    rango_fechas = "N/A"
    if pd.notnull(min_fecha) and pd.notnull(max_fecha):
        rango_fechas = f"{min_fecha.year} - {max_fecha.year}"

    # --- VISUALIZACIÓN DE MÉTRICAS INICIALES ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Semanas Cotizadas", f"{total_semanas:,.2f}")
    c2.metric("Periodos Consolidados", len(df_final))
    c3.metric("Rango de Años", rango_fechas)
    
    # --- VISUALIZACIÓN TABLA DE DATOS ---
    with st.expander("📋 Ver Detalle de Historia Laboral Procesada", expanded=True):
        st.dataframe(
            df_final[['Periodo', 'Desde', 'Hasta', 'Semanas', 'IBC', 'Aportante']].style.format({
                "IBC": "${:,.0f}",
                "Semanas": "{:.2f}",
                "Desde": "{:%d-%m-%Y}",
                "Hasta": "{:%d-%m-%Y}"
            }),
            use_container_width=True,
            height=300
        )

    # --- INICIALIZAR LÓGICA DE CÁLCULO ---
    liquidador = LiquidadorPension(df_final, genero, fecha_nacimiento)

    st.divider()
    st.subheader("2. Resultados del Estudio Pensional")
    
    tipo_estudio = st.radio("Selecciona el tipo de análisis a realizar:", 
                           ["1. Estudio Pensional (Ley 797 vs Transición)", 
                            "2. Proyección y Mejora de Pensión (Futuro)"], 
                           horizontal=True)

    if tipo_estudio.startswith("1"):
        # --- ESCENARIO 1: ESTUDIO DE VEJEZ ---
        col_res1, col_res2 = st.columns([1, 1])
        
        # Cálculos de IBL
        ibl_10, detalle_10 = liquidador.calcular_ibl_indexado("ultimos_10")
        ibl_vida, detalle_vida = liquidador.calcular_ibl_indexado("toda_vida")
        
        # Determinar el más favorable
        ibl_favorable = max(ibl_10, ibl_vida)
        origen_favorable = "Últimos 10 Años" if ibl_10 >= ibl_vida else "Toda la Vida"
        
        # Gráfica Comparativa
        with col_res1:
            st.markdown("##### Comparativo IBL (Ingreso Base de Liquidación)")
            chart_data = pd.DataFrame({
                'Monto': [ibl_10, ibl_vida]
            }, index=['Últimos 10 Años', 'Toda la Vida'])
            st.bar_chart(chart_data, color="#2E86C1")
        
        with col_res2:
            st.info(f"💡 El IBL más favorable es: **{origen_favorable}**")
            st.metric("Monto Base (IBL)", f"${ibl_favorable:,.0f}")
            
            with st.expander("🔍 Ver tabla detallada de indexación (IPC)"):
                detalle_mostrar = detalle_10 if ibl_10 >= ibl_vida else detalle_vida
                if not detalle_mostrar.empty:
                    st.dataframe(detalle_mostrar.style.format({
                        "IBC": "${:,.0f}",
                        "Factor_IPC": "{:.4f}", 
                        "IBC_Indexado": "${:,.0f}",
                        "Desde": "{:%d-%m-%Y}",
                        "Hasta": "{:%d-%m-%Y}"
                    }))
                else:
                    st.write("No hay datos suficientes para mostrar el detalle.")

        # Cálculo de Mesada (Ley 797)
        mesada, tasa, info_tasa = liquidador.calcular_tasa_reemplazo_797(ibl_favorable, total_semanas, datetime.now().year)
        
        st.markdown("---")
        c_final1, c_final2 = st.columns(2)
        
        with c_final1:
            st.markdown("### 💰 Mesada Pensional Estimada")
            st.markdown(f"<h1 style='color:#2E86C1'>${mesada:,.0f}</h1>", unsafe_allow_html=True)
            st.caption("Nota: Este valor es una estimación basada en la normativa vigente.")
            
        with c_final2:
            st.markdown("### 📊 Tasa de Reemplazo")
            st.metric("Porcentaje Aplicado", f"{tasa:.2f}%")
            
            with st.expander("🧮 Ver desglose de la fórmula decreciente"):
                st.write(f"**Fórmula Base (r = 65.5 - 0.5s):** {info_tasa['r_inicial']:.2f}%")
                st.write(f"**Semanas Cotizadas:** {total_semanas:,.2f}")
                st.write(f"**Semanas Mínimas Requeridas:** {info_tasa['semanas_minimas']}")
                st.write(f"**Semanas Adicionales:** {info_tasa['semanas_extra']:.2f}")
                st.write(f"**Puntos Adicionales (+1.5% x 50 sem):** +{info_tasa['puntos_adicionales']:.2f}%")
                st.markdown(f"**TOTAL:** {tasa:.2f}%")

    elif tipo_estudio.startswith("2"):
        # --- ESCENARIO 2: PROYECCIÓN ---
        st.subheader("🚀 Proyección a Futuro")
        st.info("Este módulo proyecta tu pensión asumiendo que continúas cotizando con tu promedio actual.")
        
        # Usamos el IBL de últimos 10 años como base de proyección
        ibl_actual, _ = liquidador.calcular_ibl_indexado("ultimos_10")
        
        col_p1, col_p2 = st.columns(2)
        
        # Proyección 1300 Semanas
        semanas_meta_1 = 1300
        semanas_faltantes_1 = max(0, semanas_meta_1 - total_semanas)
        meses_faltantes_1 = semanas_faltantes_1 / 4.29
        anio_proyeccion_1 = datetime.now().year + int(meses_faltantes_1 / 12)
        
        mesada_1, tasa_1, _ = liquidador.calcular_tasa_reemplazo_797(ibl_actual, semanas_meta_1, anio_proyeccion_1)
        
        with col_p1:
            st.markdown(f"#### Meta: {semanas_meta_1} Semanas")
            st.write(f"Tiempo estimado: {int(meses_faltantes_1/12)} años y {int(meses_faltantes_1%12)} meses")
            st.metric("Mesada Proyectada", f"${mesada_1:,.0f}", f"Tasa: {tasa_1:.2f}%")
            
        # Proyección 1800 Semanas
        semanas_meta_2 = 1800
        semanas_faltantes_2 = max(0, semanas_meta_2 - total_semanas)
        meses_faltantes_2 = semanas_faltantes_2 / 4.29
        anio_proyeccion_2 = datetime.now().year + int(meses_faltantes_2 / 12)
        
        mesada_2, tasa_2, _ = liquidador.calcular_tasa_reemplazo_797(ibl_actual, semanas_meta_2, anio_proyeccion_2)
        
        with col_p2:
            st.markdown(f"#### Meta: {semanas_meta_2} Semanas (Máxima)")
            st.write(f"Tiempo estimado: {int(meses_faltantes_2/12)} años y {int(meses_faltantes_2%12)} meses")
            st.metric("Mesada Proyectada", f"${mesada_2:,.0f}", f"Tasa: {tasa_2:.2f}%")

else:
    # Mensaje de bienvenida cuando no hay archivo
    st.info("👋 Por favor sube tu Historia Laboral Unificada (PDF) para comenzar el análisis.")
    st.markdown("""
        **Instrucciones:**
        1. Descarga tu historia laboral desde la página web de Colpensiones.
        2. No modifiques el archivo PDF.
        3. Cárgalo en el botón de arriba.
    """)
