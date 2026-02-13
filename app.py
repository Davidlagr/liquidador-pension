import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, datetime
from data_processor import procesar_pdf_historia_laboral, aplicar_regla_simultaneidad
from logic import LiquidadorPension

st.set_page_config(page_title="Liquidador Pensional Pro", layout="wide", page_icon="⚖️")

# Estilos CSS
st.markdown("""
    <style>
    .big-font { font-size:18px !important; }
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #2E86C1; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Liquidador de Pensión: Análisis Gráfico y Detallado")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Datos del Afiliado")
    nombre = st.text_input("Nombre", "Afiliado Ejemplo")
    identificacion = st.text_input("Identificación")
    fecha_nacimiento = st.date_input("Nacimiento", value=date(1970, 1, 1))
    genero = st.radio("Género", ["Masculino", "Femenino"])

# --- CARGA ---
uploaded_file = st.file_uploader("Sube tu Historia Laboral (PDF)", type="pdf")

if uploaded_file:
    # Procesamiento
    df_raw = procesar_pdf_historia_laboral(uploaded_file)
    df_final = aplicar_regla_simultaneidad(df_raw)
    liquidador = LiquidadorPension(df_final, genero, fecha_nacimiento)
    
    total_semanas = df_final['Semanas'].sum()
    
    st.info(f"✅ Historia Laboral Procesada: **{total_semanas:.2f} semanas** encontradas.")

    # --- TIPO DE ESTUDIO ---
    tipo = st.selectbox("Selecciona estudio:", 
        ["1. Estudio Pensión Vejez (Comparativo)", "2. Proyección Futura"])

    if tipo.startswith("1"):
        st.markdown("---")
        st.subheader("1. Comparativo de IBL (Ingreso Base de Liquidación)")
        
        # 1. CÁLCULOS
        ibl_10, detalle_10 = liquidador.calcular_ibl_indexado("ultimos_10")
        ibl_vida, detalle_vida = liquidador.calcular_ibl_indexado("toda_vida")
        
        # 2. GRÁFICA COMPARATIVA IBL
        col_graf, col_datos = st.columns([1, 1])
        
        with col_graf:
            # Crear DataFrame para la gráfica
            data_ibl = pd.DataFrame({
                'Tipo': ['Últimos 10 Años', 'Toda la Vida'],
                'Valor': [ibl_10, ibl_vida]
            })
            st.bar_chart(data_ibl, x='Tipo', y='Valor', color="#2E86C1")
            
        with col_datos:
            st.markdown("### Resultados IBL")
            st.write(f"🔹 **Últimos 10 Años:** ${ibl_10:,.2f}")
            st.write(f"🔹 **Toda la Vida:** ${ibl_vida:,.2f}")
            
            ibl_favorable = max(ibl_10, ibl_vida)
            origen_favorable = "Últimos 10 Años" if ibl_10 >= ibl_vida else "Toda la Vida"
            
            st.success(f"🏆 **Base más favorable:** {origen_favorable}")
            st.metric("IBL A USAR", f"${ibl_favorable:,.2f}")

        # --- EXPLICACIÓN ACTUALIZACIÓN IPC ---
        with st.expander("🔍 Ver detalle: ¿Cómo se actualizó el IBL con el IPC?"):
            st.markdown(f"#### Detalle del cálculo ({origen_favorable})")
            st.write("La norma indica que se debe tomar cada salario y multiplicarlo por la variación del IPC desde la fecha de pago hasta la fecha de liquidación.")
            st.latex(r"ValorPresente = ValorHistorico \times \frac{IPC_{Final}}{IPC_{Inicial}}")
            
            # Mostrar la tabla que devolvió la lógica
            if origen_favorable == "Últimos 10 Años":
                st.dataframe(detalle_10.style.format({"IBC": "${:,.2f}", "Factor_IPC": "{:.4f}", "IBC_Indexado": "${:,.2f}"}))
            else:
                st.dataframe(detalle_vida.style.format({"IBC": "${:,.2f}", "Factor_IPC": "{:.4f}", "IBC_Indexado": "${:,.2f}"}))
                
        # --- CÁLCULO MESADA (FORMULA DECRECIENTE) ---
        st.markdown("---")
        st.subheader("2. Cálculo de la Mesada (Fórmula Decreciente Ley 797)")
        
        # Calculamos usando el IBL FAVORABLE
        mesada, tasa, info_tasa = liquidador.calcular_tasa_reemplazo_797(ibl_favorable, total_semanas, datetime.now().year)
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Tasa de Reemplazo Final", f"{tasa:.2f}%")
            st.markdown('</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("MESADA PENSIONAL", f"${mesada:,.0f}")
            st.markdown('</div>', unsafe_allow_html=True)

        # --- EXPLICACIÓN FÓRMULA ---
        with st.expander("🧮 Ver detalle: ¿Cómo se aplicó la fórmula decreciente?"):
            st.markdown("La Ley 797 establece una fórmula que castiga porcentualmente a mayor salario, pero premia las semanas extra.")
            
            st.markdown("#### Paso 1: Fórmula Base")
            st.latex(r"r = 65.5 - 0.5 \times s")
            st.write(f"Donde $s$ es el número de salarios mínimos del IBL. Tu IBL es de **${ibl_favorable:,.0f}**.")
            st.write(f"Resultado inicial: **{info_tasa['r_inicial']:.2f}%**")
            
            st.markdown("#### Paso 2: Semanas Adicionales")
            st.write(f"Semanas cotizadas: **{total_semanas:.2f}**")
            st.write(f"Semanas mínimas requeridas: **{info_tasa['semanas_minimas']}**")
            st.write(f"Semanas extra: **{info_tasa['semanas_extra']:.2f}**")
            
            st.markdown("#### Paso 3: Cálculo Final")
            st.write("Por cada 50 semanas extra, se suma 1.5%:")
            st.latex(r"TasaFinal = TasaBase + (PaquetesDe50 \times 1.5)")
            st.write(f"{info_tasa['r_inicial']:.2f}% + {info_tasa['puntos_adicionales']:.2f}% = **{tasa:.2f}%**")

    elif tipo.startswith("2"):
        st.subheader("🔮 Proyección a Futuro")
        # Aquí iría la lógica de proyección similar a la anterior
        # (Se mantiene del código previo, pero puedes agregar gráficos de proyección también si deseas)
        st.info("Módulo de proyección en desarrollo visual...")
