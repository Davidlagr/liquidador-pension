import streamlit as st
import pandas as pd
from datetime import date, datetime
from data_processor import procesar_pdf_historia_laboral, aplicar_regla_simultaneidad
from logic import LiquidadorPension

# Configuración de página
st.set_page_config(page_title="Liquidador Pensional Pro", layout="wide", page_icon="⚖️")

# Estilos CSS personalizados para que se vea profesional
st.markdown("""
    <style>
    .big-font { font-size:20px !important; color: #2E86C1; }
    .result-box { background-color: #D4E6F1; padding: 20px; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

st.title("⚖️ Liquidador de Pensión de Vejez y Proyección")
st.markdown("Herramienta avanzada con análisis de **Simultaneidad**, **Transición** y **Beneficio Mujeres 2026**.")

# --- SIDEBAR: DATOS PERSONALES ---
with st.sidebar:
    st.header("👤 Datos del Afiliado")
    nombre = st.text_input("Nombre Completo")
    identificacion = st.text_input("Identificación (C.C.)")
    fecha_nacimiento = st.date_input("Fecha de Nacimiento", value=date(1975, 1, 1))
    genero = st.radio("Género", ["Masculino", "Femenino"])
    
    st.info("ℹ️ Recuerda: Para las mujeres, el sistema calculará automáticamente la reducción de semanas a partir de 2026.")

# --- PASO 1: CARGA DE ARCHIVO ---
st.header("1. Historia Laboral (Colpensiones)")
col1, col2 = st.columns([2, 1])
with col1:
    archivo = st.file_uploader("Cargar PDF Historia Laboral", type=['pdf'])

if archivo:
    # Procesar
    with st.spinner('Leyendo PDF y aplicando reglas de simultaneidad...'):
        df_raw = procesar_pdf_historia_laboral(archivo)
        df_final = aplicar_regla_simultaneidad(df_raw)
        
    total_semanas = df_final['Semanas'].sum()
    ultimo_ibl = df_final['IBC'].iloc[-1] if not df_final.empty else 0
    
    # Mostrar resumen
    st.success(f"Historia cargada. Semanas consolidadas: **{total_semanas:.2f}**")
    with st.expander("Ver detalle de cotizaciones (Simultaneidad aplicada)"):
        st.dataframe(df_final)

    # Instanciar lógica
    liquidador = LiquidadorPension(df_final, genero, fecha_nacimiento)

    # --- PASO 2: TIPO DE ESTUDIO ---
    st.divider()
    tipo_estudio = st.selectbox("Seleccione el Tipo de Estudio:", 
                 ["Seleccionar...", 
                  "1. Estudio de Pensión de Vejez (Derecho actual / Retroactivo)",
                  "2. Proyección de Mesada Pensional (Futuro)"])

    if tipo_estudio.startswith("1"):
        st.subheader("📋 Resultado: Estudio de Pensión de Vejez")
        
        col_res1, col_res2 = st.columns(2)
        
        # 1. Verificar Transición
        es_transicion = liquidador.verificar_regimen_transicion()
        
        # Cálculos IBL
        ibl_10 = liquidador.calcular_ibl_indexado("ultimos_10")
        ibl_vida = liquidador.calcular_ibl_indexado("toda_vida")
        
        # Cálculos Mesada Ley 797
        mesada_797_10, tasa_797_10, _ = liquidador.calcular_tasa_reemplazo_797(ibl_10, total_semanas, datetime.now().year)
        mesada_797_vida, tasa_797_vida, _ = liquidador.calcular_tasa_reemplazo_797(ibl_vida, total_semanas, datetime.now().year)
        
        mejor_797 = max(mesada_797_10, mesada_797_vida)
        
        with col_res1:
            st.markdown("#### Ley 797 de 2003")
            st.write(f"IBL (Últimos 10 años): ${ibl_10:,.0f}")
            st.write(f"IBL (Toda la vida): ${ibl_vida:,.0f}")
            st.metric("Mesada Ley 797", f"${mejor_797:,.0f}")

        with col_res2:
            st.markdown("#### Régimen de Transición (Dec. 758/90)")
            if es_transicion:
                mesada_758, tasa_758 = liquidador.calcular_decreto_758(ibl_10, total_semanas) # 758 suele usar ultimo año o prom, simplificado aqui
                st.success("✅ Es beneficiario del Régimen de Transición")
                st.metric("Mesada Decreto 758", f"${mesada_758:,.0f}", delta=f"{tasa_758}%")
                
                if mesada_758 > mejor_797:
                    st.balloons()
                    st.success(f"🏆 **Norma Favorable: Decreto 758 de 1990**")
            else:
                st.error("❌ No aplica Régimen de Transición")
                st.write("Se liquida exclusivamente bajo Ley 797 de 2003.")

    elif tipo_estudio.startswith("2"):
        st.subheader("🚀 Proyección de Futuro")
        
        # Proyecciones
        ibl_actual = liquidador.calcular_ibl_indexado("ultimos_10")
        
        # Escenario 1: 1300 Semanas
        anio_estimado_1300 = datetime.now().year + int((1300 - total_semanas)/52)
        mesada_1300, tasa_1300, sem_req_1300 = liquidador.calcular_tasa_reemplazo_797(ibl_actual, 1300, anio_estimado_1300)
        
        # Escenario 2: 1800 Semanas
        anio_estimado_1800 = datetime.now().year + int((1800 - total_semanas)/52)
        mesada_1800, tasa_1800, _ = liquidador.calcular_tasa_reemplazo_797(ibl_actual, 1800, anio_estimado_1800)

        c1, c2 = st.columns(2)
        with c1:
            st.info(f"**Proyección Meta: {sem_req_1300} Semanas (Mínimo)**")
            st.write(f"IBL Proyectado (Constante): ${ibl_actual:,.0f}")
            st.metric("Mesada Estimada", f"${mesada_1300:,.0f}", f"Tasa: {tasa_1300:.2f}%")
            
        with c2:
            st.info("**Proyección Meta: 1800 Semanas (Máximo)**")
            st.write(f"IBL Proyectado (Constante): ${ibl_actual:,.0f}")
            st.metric("Mesada Estimada", f"${mesada_1800:,.0f}", f"Tasa: {tasa_1800:.2f}%")

    # --- PASO 3: MODULO MEJORAR MI MESADA ---
    st.divider()
    st.header("📈 Estrategia: Mejorar mi Mesada Pensional")
    
    with st.expander("Abrir Simulador de Aportes"):
        estrategia = st.radio("Seleccione su caso:", 
                             ["1. Dependiente cotizando adicional como Independiente", 
                              "2. Independiente aumentando Ingreso Base"])
        
        aporte_extra_mensual = st.number_input("Monto ADICIONAL al IBC actual ($)", min_value=0, step=100000)
        
        if st.button("Simular Impacto"):
            # Lógica de simulación
            # Asumimos que este aporte extra se mantiene por los proximos 5 años para impactar el IBL
            nuevo_ibc_promedio = ultimo_ibl + aporte_extra_mensual
            
            # Recalculamos un IBL ficticio mezclando historia real + 5 años futuros mejorados
            # (Simplificación matemática para la demo)
            ibl_actual = liquidador.calcular_ibl_indexado("ultimos_10")
            ibl_proyectado_mejorado = (ibl_actual * 0.5) + (nuevo_ibc_promedio * 0.5) 
            
            mesada_base, _, _ = liquidador.calcular_tasa_reemplazo_797(ibl_actual, total_semanas + 250, datetime.now().year + 5)
            mesada_mejorada, _, _ = liquidador.calcular_tasa_reemplazo_797(ibl_proyectado_mejorado, total_semanas + 250, datetime.now().year + 5)
            
            diff = mesada_mejorada - mesada_base
            
            st.success(f"Con esta estrategia, tu mesada en 5 años podría aumentar en: **${diff:,.0f}**")
            st.metric("Nueva Mesada Proyectada", f"${mesada_mejorada:,.0f}")

# --- RESULTADO FINAL PARA IMPRESIÓN ---
if archivo:
    st.divider()
    st.markdown("### Resumen del Estudio")
    st.text(f"Nombre: {nombre}")
    st.text(f"ID: {identificacion}")
    st.text(f"Fecha Estudio: {date.today()}")
    st.caption("Generado con Liquidador Pensional Python v2.0")
