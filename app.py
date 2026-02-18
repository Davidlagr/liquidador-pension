import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from data_processor import extraer_tabla_cruda, limpiar_y_estandarizar, aplicar_regla_simultaneidad
from logic import LiquidadorPension

st.set_page_config(page_title="Liquidador & Proyector Pensional", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .metric-box { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-left: 5px solid #2E86C1; }
    .investment-card { background-color: #eaf2f8; padding: 15px; border-radius: 10px; border: 1px solid #d6eaf8; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 Planeación Pensional: Calculadora & Inversión")

if 'df_crudo' not in st.session_state: st.session_state.df_crudo = None
if 'df_final' not in st.session_state: st.session_state.df_final = None

# --- SIDEBAR ---
with st.sidebar:
    st.header("👤 Perfil")
    nombre = st.text_input("Nombre", "Usuario")
    genero = st.radio("Género", ["Masculino", "Femenino"])
    fecha_nac = st.date_input("Fecha Nacimiento", value=date(1975, 1, 1))
    
    st.markdown("---")
    
    # --- CONFIGURACIÓN DE CÁLCULO ---
    st.header("⚙️ Configuración")
    aplicar_tope = st.checkbox(
        "Aplicar tope de 1800 Semanas", 
        value=True,
        help="Si está marcado, se limita el cálculo a 1800 semanas (máx 15% extra). Desmárcalo para proyectar hasta el 80% sin límite."
    )
    
    st.markdown("---")
    if st.button("🔄 Reiniciar"):
        st.session_state.df_crudo = None
        st.session_state.df_final = None
        st.rerun()

# --- FASE 1: CARGA ---
if st.session_state.df_final is None:
    st.info("📂 Carga tu Historia Laboral (PDF) para comenzar.")
    uploaded_file = st.file_uploader("Subir Archivo Colpensiones", type="pdf")

    if uploaded_file:
        if st.session_state.df_crudo is None:
            st.session_state.df_crudo = extraer_tabla_cruda(uploaded_file)

        df_disp = st.session_state.df_crudo
        
        if df_disp is not None and not df_disp.empty:
            st.success("✅ Archivo leído. Identifica las columnas:")
            st.dataframe(df_disp.head(3), use_container_width=True)
            
            cols = df_disp.columns.tolist()
            c1, c2, c3, c4 = st.columns(4)
            col_d = c1.selectbox("FECHA DESDE", cols, index=2 if len(cols)>2 else 0)
            col_h = c2.selectbox("FECHA HASTA", cols, index=3 if len(cols)>3 else 0)
            col_i = c3.selectbox("SALARIO", cols, index=4 if len(cols)>4 else 0)
            col_s = c4.selectbox("SEMANAS", cols, index=len(cols)-1)
            
            if st.button("🚀 Procesar Liquidación"):
                df_clean = limpiar_y_estandarizar(df_disp, col_d, col_h, col_i, col_s)
                if not df_clean.empty:
                    st.session_state.df_final = aplicar_regla_simultaneidad(df_clean)
                    st.rerun()
                else: st.error("Las columnas seleccionadas no contienen datos válidos.")
        else: st.warning("No se encontró texto legible en el PDF.")

# --- FASE 2: RESULTADOS ---
else:
    df = st.session_state.df_final
    liq = LiquidadorPension(df, genero, fecha_nac)
    
    tab1, tab2 = st.tabs(["📊 DIAGNÓSTICO ACTUAL", "💰 PROYECCIÓN E INVERSIÓN"])
    
    # === TAB 1: DIAGNÓSTICO ACTUAL ===
    with tab1:
        st.markdown(f"### Situación Actual de {nombre}")
        
        # Resumen Rápido
        total_sem = df['Semanas'].sum()
        ultimo_ibc = df['IBC'].iloc[-1] if not df.empty else 0
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Semanas Acumuladas", f"{total_sem:,.2f}")
        k2.metric("Último IBC Reportado", f"${ultimo_ibc:,.0f}")
        k3.metric("Rango Histórico", f"{df['Desde'].dt.year.min()} - {df['Hasta'].dt.year.max()}")
        
        st.divider()
        
        # Análisis IBL
        ibl_10, det_10 = liq.calcular_ibl_indexado("ultimos_10")
        ibl_vida, det_vida = liq.calcular_ibl_indexado("toda_vida")
        ibl_def = max(ibl_10, ibl_vida)
        origen = "Últimos 10 Años" if ibl_10 >= ibl_vida else "Toda la Vida"
        
        colL, colR = st.columns(2)
        with colL:
            st.markdown("#### Base de Liquidación (IBL)")
            st.bar_chart(pd.DataFrame({"Monto":[ibl_10, ibl_vida]}, index=["10 Años", "Toda Vida"]), color="#2E86C1")
            st.info(f"IBL Más Favorable: **{origen}** (${ibl_def:,.0f})")
            
        with colR:
            st.markdown("#### Soportes Técnicos")
            with st.expander(f"Ver Detalle 10 Años (${ibl_10:,.0f})"):
                st.dataframe(det_10)
            with st.expander(f"Ver Detalle Toda Vida (${ibl_vida:,.0f})"):
                st.dataframe(det_vida)

        # Liquidación Hoy
        mesada, tasa, info = liq.calcular_tasa_reemplazo_797(
            ibl_def, total_sem, datetime.now().year, 
            limitar_semanas_cotizadas=aplicar_tope
        )
        
        st.markdown("---")
        st.markdown(f"### 💵 Pensión Hoy: <span style='color:green'>${mesada:,.0f}</span>", unsafe_allow_html=True)
        c_t1, c_t2 = st.columns(2)
        c_t1.metric("Tasa Reemplazo", f"{tasa:.2f}%")
        c_t2.metric("Semanas Computadas", f"{info['semanas_usadas']:,.2f}", 
                    delta="Tope 1800 Activo" if aplicar_tope and total_sem > 1800 else "Sin Tope")

    # === TAB 2: PROYECCIÓN E INVERSIÓN ===
    with tab2:
        st.markdown("### 🔮 Simulador de Futuro & Costos")
        
        col_conf, col_res = st.columns([1, 2])
        
        with col_conf:
            st.markdown("#### 1. Estrategia")
            modo = st.radio("¿Qué deseas hacer?", ["Cotizar como Independiente (Nuevo IBC Total)", "Sumar un Aporte Extra"])
            
            if modo.startswith("Cotizar"):
                nuevo_ibc = st.number_input("Nuevo IBC Total ($)", value=float(ultimo_ibc), step=100000.0)
                base_costo = nuevo_ibc
            else:
                extra = st.number_input("Valor Aporte Adicional ($)", value=1000000.0, step=100000.0)
                nuevo_ibc = ultimo_ibc + extra
                base_costo = extra
            
            anios = st.slider("Tiempo a cotizar (Años)", 1, 15, 5)
            
            # Cálculo de Costos (Salud + Pensión + FSP)
            smmlv_est = 1423500 # Valor ref 2025
            tasa_ss = 0.285 # 16% Pensión + 12.5% Salud
            
            costo_mensual = base_costo * tasa_ss
            
            # Fondo Solidaridad pensional (> 4 SMMLV)
            fsp = 0
            if base_costo > (4 * smmlv_est):
                fsp = base_costo * 0.01 # 1% Base
                costo_mensual += fsp
                st.caption(f"Incluye 1% de Fondo Solidaridad (${fsp:,.0f})")
            
            inversion_total = costo_mensual * (anios * 12)
            
            st.markdown("#### 💸 Costo de la Estrategia")
            st.markdown(f"""
            <div class="investment-card">
                <b>Pago Mensual (Salud+Pensión):</b><br>
                <span style="font-size:20px; color:#c0392b">${costo_mensual:,.0f}</span><br><br>
                <b>Inversión Total ({anios} años):</b><br>
                <span style="font-size:18px">${inversion_total:,.0f}</span>
            </div>
            """, unsafe_allow_html=True)

        with col_res:
            st.markdown("#### 2. Resultado Financiero")
            
            # --- MOTOR DE PROYECCIÓN ---
            filas_fut = []
            fecha_cursor = df['Hasta'].max() + timedelta(days=1)
            for _ in range(anios*12):
                fin = fecha_cursor + timedelta(days=30)
                filas_fut.append({
                    "Desde": fecha_cursor, "Hasta": fin, "IBC": nuevo_ibc, 
                    "Semanas": 4.29, "Periodo": pd.Period(fecha_cursor, freq='M')
                })
                fecha_cursor = fin + timedelta(days=1)
            
            df_fut = pd.concat([df, pd.DataFrame(filas_fut)], ignore_index=True)
            total_fut = df_fut['Semanas'].sum()
            
            liq_f = LiquidadorPension(df_fut, genero, fecha_nac)
            fi_10, _ = liq_f.calcular_ibl_indexado("ultimos_10")
            fi_vida, _ = liq_f.calcular_ibl_indexado("toda_vida")
            fi_def = max(fi_10, fi_vida)
            
            f_mesada, f_tasa, f_info = liq_f.calcular_tasa_reemplazo_797(
                fi_def, total_fut, datetime.now().year + anios,
                limitar_semanas_cotizadas=aplicar_tope
            )
            
            # --- MÉTRICAS DE IMPACTO ---
            delta_mesada = f_mesada - mesada
            delta_tasa = f_tasa - tasa
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Nueva Mesada", f"${f_mesada:,.0f}", f"+ ${delta_mesada:,.0f} / mes")
            m2.metric("Nueva Tasa", f"{f_tasa:.2f}%", f"+ {delta_tasa:.2f}%")
            m3.metric("Total Semanas", f"{total_fut:,.0f}", f"+ {int(anios*12*4.29)}")
            
            st.markdown("---")
            
            # --- ANÁLISIS DE ROI (RETORNO DE INVERSIÓN) ---
            st.subheader("📊 Análisis de Retorno (ROI)")
            
            col_roi1, col_roi2 = st.columns(2)
            
            with col_roi1:
                st.write("¿Vale la pena la inversión?")
                if delta_mesada > 0:
                    meses_recup = inversion_total / delta_mesada
                    anios_recup = meses_recup / 12
                    
                    st.success(f"✅ **¡Proyecto Viable!**")
                    st.write(f"Recuperas tu inversión en:")
                    st.markdown(f"### {anios_recup:.1f} Años")
                    st.caption(f"Después de ese tiempo, el aumento de ${delta_mesada:,.0f} es ganancia neta vitalicia.")
                else:
                    st.error("⚠️ La inversión no genera aumento en la mesada (posiblemente ya estás en el tope o el IBL bajó).")
            
            with col_roi2:
                # Gráfico Comparativo
                df_chart = pd.DataFrame({
                    "Concepto": ["Mesada Hoy", "Mesada Futura"],
                    "Valor": [mesada, f_mesada]
                })
                st.bar_chart(df_chart.set_index("Concepto"), color="#27AE60")
