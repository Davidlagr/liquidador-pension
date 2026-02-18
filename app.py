import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from data_processor import extraer_tabla_cruda, limpiar_y_estandarizar, aplicar_regla_simultaneidad
from logic import LiquidadorPension

st.set_page_config(page_title="Liquidador & Proyector Pensional", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .metric-box { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-left: 5px solid #2E86C1; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 Planeación Pensional Inteligente")

if 'df_crudo' not in st.session_state: st.session_state.df_crudo = None
if 'df_final' not in st.session_state: st.session_state.df_final = None

# --- SIDEBAR ---
with st.sidebar:
    st.header("👤 Perfil")
    nombre = st.text_input("Nombre", "Usuario")
    genero = st.radio("Género", ["Masculino", "Femenino"])
    fecha_nac = st.date_input("Fecha Nacimiento", value=date(1975, 1, 1))
    
    st.markdown("---")
    
    # --- PREGUNTA CLAVE DE CONFIGURACIÓN ---
    st.header("⚙️ Configuración de Cálculo")
    aplicar_tope = st.checkbox(
        "Aplicar tope de 1800 Semanas", 
        value=True,
        help="Si está marcado, Colpensiones solo cuenta hasta 1800 semanas (máx 15% extra). Si lo desmarcas, usará todas tus semanas para intentar llegar al 80%."
    )
    
    st.markdown("---")
    if st.button("🔄 Reiniciar"):
        st.session_state.df_crudo = None
        st.session_state.df_final = None
        st.rerun()

# --- FASE 1: CARGA ---
if st.session_state.df_final is None:
    st.info("📂 Carga tu PDF para empezar.")
    uploaded_file = st.file_uploader("Subir Archivo Colpensiones", type="pdf")

    if uploaded_file:
        if st.session_state.df_crudo is None:
            st.session_state.df_crudo = extraer_tabla_cruda(uploaded_file)

        df_disp = st.session_state.df_crudo
        
        if df_disp is not None and not df_disp.empty:
            st.success("✅ Archivo leído.")
            st.dataframe(df_disp.head(3), use_container_width=True)
            
            cols = df_disp.columns.tolist()
            c1, c2, c3, c4 = st.columns(4)
            col_d = c1.selectbox("FECHA DESDE", cols, index=2 if len(cols)>2 else 0)
            col_h = c2.selectbox("FECHA HASTA", cols, index=3 if len(cols)>3 else 0)
            col_i = c3.selectbox("SALARIO", cols, index=4 if len(cols)>4 else 0)
            col_s = c4.selectbox("SEMANAS", cols, index=len(cols)-1)
            
            if st.button("🚀 Procesar"):
                df_clean = limpiar_y_estandarizar(df_disp, col_d, col_h, col_i, col_s)
                if not df_clean.empty:
                    st.session_state.df_final = aplicar_regla_simultaneidad(df_clean)
                    st.rerun()
                else: st.error("Columnas sin datos.")
        else: st.warning("No se encontró texto.")

# --- FASE 2: RESULTADOS ---
else:
    df = st.session_state.df_final
    liq = LiquidadorPension(df, genero, fecha_nac)
    
    tab1, tab2 = st.tabs(["📊 DIAGNÓSTICO", "🚀 PROYECCIÓN"])
    
    # === TAB 1: DIAGNÓSTICO ===
    with tab1:
        st.markdown(f"### Análisis Actual: {nombre}")
        
        # Resumen
        total_sem = df['Semanas'].sum()
        ultimo_ibc = df['IBC'].iloc[-1] if not df.empty else 0
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Semanas Totales", f"{total_sem:,.2f}")
        k2.metric("IBC Reciente", f"${ultimo_ibc:,.0f}")
        k3.metric("Rango Años", f"{df['Desde'].dt.year.min()} - {df['Hasta'].dt.year.max()}")
        
        st.divider()
        
        # IBLs
        ibl_10, det_10 = liq.calcular_ibl_indexado("ultimos_10")
        ibl_vida, det_vida = liq.calcular_ibl_indexado("toda_vida")
        ibl_def = max(ibl_10, ibl_vida)
        origen = "Últimos 10 Años" if ibl_10 >= ibl_vida else "Toda la Vida"
        
        colL, colR = st.columns(2)
        with colL:
            st.markdown("#### Comparativo IBL")
            st.bar_chart(pd.DataFrame({"Monto":[ibl_10, ibl_vida]}, index=["10 Años", "Toda Vida"]), color="#2E86C1")
            st.info(f"IBL Aplicado: **{origen}** (${ibl_def:,.0f})")
            
        with colR:
            st.markdown("#### Detalle Soportes")
            with st.expander(f"Ver IBL 10 Años (${ibl_10:,.0f})"):
                st.dataframe(det_10)
            with st.expander(f"Ver IBL Toda Vida (${ibl_vida:,.0f})"):
                st.dataframe(det_vida)

        # LIQUIDACIÓN
        # Aquí pasamos el parámetro del checkbox 'aplicar_tope'
        mesada, tasa, info = liq.calcular_tasa_reemplazo_797(
            ibl_def, total_sem, datetime.now().year, 
            limitar_semanas_cotizadas=aplicar_tope
        )
        
        st.markdown("---")
        st.markdown(f"### 💰 Pensión: <span style='color:green'>${mesada:,.0f}</span>", unsafe_allow_html=True)
        
        c_t1, c_t2 = st.columns(2)
        c_t1.metric("Tasa Reemplazo", f"{tasa:.2f}%")
        c_t2.metric("Semanas Computadas", f"{info['semanas_usadas']:,.2f}", 
                    delta="Tope aplicado" if aplicar_tope and total_sem > 1800 else "Sin tope")

    # === TAB 2: PROYECCIÓN ===
    with tab2:
        st.markdown("### 🔮 Simulador Futuro")
        
        c_in, c_out = st.columns([1, 2])
        
        with c_in:
            st.subheader("Configuración")
            modo = st.radio("Estrategia:", ["Aumentar IBC (Independiente)", "Sumar Aporte Extra"])
            
            if modo.startswith("Aumentar"):
                nuevo_ibc = st.number_input("Nuevo IBC Total ($)", value=float(ultimo_ibc), step=100000.0)
            else:
                extra = st.number_input("Aporte Extra ($)", value=1000000.0)
                nuevo_ibc = ultimo_ibc + extra
            
            anios = st.slider("Años a cotizar", 1, 15, 5)
            
            # Recordatorio del tope
            if aplicar_tope:
                st.warning("⚠️ Nota: Tienes activo el tope de 1800 semanas en el menú lateral.")
            else:
                st.success("✅ Nota: Estás calculando SIN tope de semanas (hasta llegar al 80%).")

        with c_out:
            st.subheader("Resultado")
            
            # Simulación
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
            
            # Usamos el mismo flag de tope del sidebar
            f_mesada, f_tasa, f_info = liq_f.calcular_tasa_reemplazo_797(
                fi_def, total_fut, datetime.now().year + anios,
                limitar_semanas_cotizadas=aplicar_tope
            )
            
            d_mes = f_mesada - mesada
            d_tasa = f_tasa - tasa
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Nueva Mesada", f"${f_mesada:,.0f}", f"+ ${d_mes:,.0f}")
            m2.metric("Nueva Tasa", f"{f_tasa:.2f}%", f"+ {d_tasa:.2f}%")
            m3.metric("Total Semanas", f"{total_fut:,.0f}", f"+ {int(anios*12*4.29)}")
            
            st.bar_chart(pd.DataFrame({"Mesada": [mesada, f_mesada]}, index=["Hoy", f"+{anios} Años"]), color="#2ecc71")
