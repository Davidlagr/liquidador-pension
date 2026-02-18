import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, datetime
from data_processor import procesar_pdf_historia_laboral, aplicar_regla_simultaneidad
from logic import LiquidadorPension

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Liquidador Pensional Pro", layout="wide", page_icon="⚖️")

# CSS Personalizado
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #2E86C1; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    .big-number { font-size: 24px; font-weight: bold; color: #154360; }
    </style>
""", unsafe_allow_html=True)

st.title("⚖️ Liquidador de Pensión de Vejez Colombia")
st.markdown("**Versión Web 2.0** | Ley 100/93, Ley 797/03 y Dec. 758/90")

# --- SIDEBAR ---
with st.sidebar:
    st.header("👤 Datos del Usuario")
    nombre = st.text_input("Nombre Completo")
    identificacion = st.text_input("Número de Identificación")
    fecha_nacimiento = st.date_input("Fecha de Nacimiento", value=date(1975, 1, 1))
    genero = st.radio("Género", ["Masculino", "Femenino"])
    
    st.info("ℹ️ Para mujeres, se aplica reducción de semanas (Sentencia C-197/23) a partir de 2026.")

# --- MÓDULO 1: CARGA DE DATOS ---
st.header("1. Historia Laboral")
uploaded_file = st.file_uploader("Sube tu archivo PDF (Descargado de Colpensiones)", type="pdf")

if uploaded_file:
    with st.spinner('🔍 Analizando documento y extrayendo cotizaciones...'):
        # 1. Procesamiento (Lectura PDF)
        df_raw = procesar_pdf_historia_laboral(uploaded_file)
        
        # 2. Validación de Carga
        if df_raw.empty:
            st.error("""
            ❌ **No se pudieron detectar cotizaciones.**
            
            Posibles causas:
            1. El PDF está encriptado o protegido.
            2. Es una imagen escaneada (no tiene texto seleccionable).
            3. El formato es muy diferente al estándar de Colpensiones.
            
            *Intenta descargar nuevamente el archivo desde la página oficial de Colpensiones.*
            """)
            st.stop()
            
        # 3. Regla de Simultaneidad
        df_final = aplicar_regla_simultaneidad(df_raw)
    
    # --- RESUMEN DE DATOS ---
    total_semanas = df_final['Semanas'].sum()
    rango_ini = df_final['Desde'].min().year if not df_final.empty else "N/A"
    rango_fin = df_final['Hasta'].max().year if not df_final.empty else "N/A"
    
    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="metric-card">Total Semanas<br><span class="big-number">{total_semanas:,.2f}</span></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card">Periodos (Meses)<br><span class="big-number">{len(df_final)}</span></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card">Rango Temporal<br><span class="big-number">{rango_ini} - {rango_fin}</span></div>', unsafe_allow_html=True)
    
    with st.expander("📋 Ver Tabla Detallada de Cotizaciones (Clic para desplegar)"):
        st.dataframe(
            df_final[['Periodo', 'Desde', 'Hasta', 'Semanas', 'IBC', 'Aportante']].style.format({
                "IBC": "${:,.0f}",
                "Semanas": "{:.2f}",
                "Desde": "{:%d-%m-%Y}",
                "Hasta": "{:%d-%m-%Y}"
            }),
            use_container_width=True
        )

    # --- MÓDULO 2: ANÁLISIS ---
    st.divider()
    st.header("2. Estudio Pensional")
    
    # Inicializar Motor de Calculo
    liquidador = LiquidadorPension(df_final, genero, fecha_nacimiento)
    
    tipo_estudio = st.radio("¿Qué tipo de estudio deseas realizar?", 
                           ["1. Liquidación Pensión de Vejez (Derecho Adquirido / Normativa)", 
                            "2. Proyección y Mejora de Mesada (Futuro)"])

    if tipo_estudio.startswith("1"):
        col_L, col_R = st.columns([1, 1])
        
        # Cálculos
        ibl_10, detalle_10 = liquidador.calcular_ibl_indexado("ultimos_10")
        ibl_vida, detalle_vida = liquidador.calcular_ibl_indexado("toda_vida")
        
        # Determinación automática del favorable
        ibl_favorable = max(ibl_10, ibl_vida)
        origen_favorable = "Últimos 10 Años" if ibl_10 >= ibl_vida else "Toda la Vida"
        
        with col_L:
            st.subheader("Comparativo de IBL")
            st.write("El IBL es el promedio de salarios actualizado con el IPC.")
            
            graf_data = pd.DataFrame({'IBL': [ibl_10, ibl_vida]}, index=['Últimos 10', 'Toda la Vida'])
            st.bar_chart(graf_data, color="#2E86C1")
            
            with st.expander("Ver detalle indexación IPC"):
                 detalle = detalle_10 if ibl_10 >= ibl_vida else detalle_vida
                 st.dataframe(detalle)

        with col_R:
            st.subheader("Resultado Liquidación")
            st.info(f"✅ Se seleccionó automáticamente el IBL más favorable: **{origen_favorable}**")
            
            # Calculo mesada
            mesada, tasa, info = liquidador.calcular_tasa_reemplazo_797(ibl_favorable, total_semanas, datetime.now().year)
            
            st.metric("IBL Base", f"${ibl_favorable:,.0f}")
            st.metric("Tasa de Reemplazo", f"{tasa:.2f}%")
            st.markdown(f"### Mesada Estimada: :green[${mesada:,.0f}]")
            
            st.markdown("---")
            st.write("**Desglose Tasa (Ley 797):**")
            st.write(f"- Fórmula Base (r): {info['r_inicial']:.2f}%")
            st.write(f"- Semanas Extra ({info['semanas_extra']:.1f}): +{info['puntos_adicionales']:.2f}%")
            
            # Verificación Transición
            if liquidador.verificar_regimen_transicion():
                st.success("🌟 ¡Atención! Cumples requisitos para Régimen de Transición (Dec. 758/90). Verifica si te favorece más.")
                mesada_758, tasa_758 = liquidador.calcular_decreto_758(ibl_favorable, total_semanas)
                st.metric("Opción Decreto 758/90", f"${mesada_758:,.0f}", delta=f"{tasa_758}%")
            else:
                st.caption("No aplica Régimen de Transición.")

    elif tipo_estudio.startswith("2"):
        st.subheader("📈 Proyección y Mejora")
        st.info("Simulación proyectando tu IBL actual hacia el futuro.")
        
        ibl_base, _ = liquidador.calcular_ibl_indexado("ultimos_10")
        
        col_p1, col_p2 = st.columns(2)
        
        # Meta 1300
        anio_1300 = datetime.now().year + max(0, int((1300 - total_semanas)/52))
        m_1300, t_1300, _ = liquidador.calcular_tasa_reemplazo_797(ibl_base, 1300, anio_1300)
        
        col_p1.metric("Meta 1300 Semanas", f"${m_1300:,.0f}", f"Tasa: {t_1300:.2f}%")
        col_p1.caption(f"Fecha estimada: {anio_1300}")
        
        # Meta 1800
        anio_1800 = datetime.now().year + max(0, int((1800 - total_semanas)/52))
        m_1800, t_1800, _ = liquidador.calcular_tasa_reemplazo_797(ibl_base, 1800, anio_1800)
        
        col_p2.metric("Meta 1800 Semanas (Máx)", f"${m_1800:,.0f}", f"Tasa: {t_1800:.2f}%")
        col_p2.caption(f"Fecha estimada: {anio_1800}")
        
        # Simulador Aportes
        st.markdown("---")
        st.write("**Simulador de Aporte Voluntario**")
        aporte_extra = st.number_input("Si aportaras extra mensualmente ($):", min_value=0, step=100000)
        
        if aporte_extra > 0:
            # Calculo simplificado de impacto
            nuevo_ibl = ibl_base + aporte_extra
            m_mejorada, t_mejorada, _ = liquidador.calcular_tasa_reemplazo_797(nuevo_ibl, total_semanas + 250, datetime.now().year + 5)
            st.success(f"En 5 años, tu mesada podría subir a: **${m_mejorada:,.0f}**")

else:
    st.info("👋 Esperando archivo de historia laboral...")
