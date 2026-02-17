import streamlit as st
import pandas as pd
from datetime import date, datetime
from data_processor import extraer_tabla_cruda, limpiar_y_estandarizar, aplicar_regla_simultaneidad
from logic import LiquidadorPension

st.set_page_config(page_title="Liquidador Manual", layout="wide", page_icon="🛠️")

st.title("🛠️ Liquidador Asistido: Mapeo Manual de Columnas")
st.markdown("Si la lectura automática falla, aquí tú tienes el control. Indica qué columna es cuál.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Datos Personales")
    nombre = st.text_input("Nombre", "Usuario")
    fecha_nacimiento = st.date_input("Fecha Nacimiento", value=date(1975, 1, 1))
    genero = st.radio("Género", ["Masculino", "Femenino"])

# --- PASO 1: SUBIR Y LEER CRUDO ---
uploaded_file = st.file_uploader("1. Sube tu Historia Laboral (PDF)", type="pdf")

if 'df_crudo' not in st.session_state:
    st.session_state.df_crudo = None

if uploaded_file:
    # Solo procesar si cambió el archivo o no hay datos
    if st.session_state.df_crudo is None:
        with st.spinner("Extrayendo estructura de la tabla..."):
            st.session_state.df_crudo = extraer_tabla_cruda(uploaded_file)

    df_display = st.session_state.df_crudo

    if df_display is not None and not df_display.empty:
        st.success("✅ Estructura extraída. Ahora ayúdame a identificar las columnas.")
        
        # --- PASO 2: VISUALIZAR Y MAPEAR ---
        st.markdown("### 2. Identifica tus columnas")
        st.markdown("Mira la tabla de abajo (primeras 5 filas) y selecciona qué columna corresponde a cada dato.")
        
        # Mostrar muestra de datos para guiarse
        st.dataframe(df_display.head(5), use_container_width=True)
        
        col_opts = df_display.columns.tolist()
        
        # Intentar adivinar índices por defecto (heurística básica)
        idx_desde = 2 if len(col_opts) > 2 else 0
        idx_hasta = 3 if len(col_opts) > 3 else 0
        idx_ibc = 4 if len(col_opts) > 4 else 0
        idx_semanas = len(col_opts) - 1 # Usualmente la última
        
        c1, c2, c3, c4 = st.columns(4)
        sel_desde = c1.selectbox("Columna: FECHA DESDE", col_opts, index=idx_desde)
        sel_hasta = c2.selectbox("Columna: FECHA HASTA", col_opts, index=idx_hasta)
        sel_ibc = c3.selectbox("Columna: SALARIO (IBC)", col_opts, index=idx_ibc)
        sel_semanas = c4.selectbox("Columna: SEMANAS", col_opts, index=idx_semanas)
        
        # --- PASO 3: PROCESAR Y CALCULAR ---
        if st.button("✅ Confirmar Columnas y Calcular"):
            
            # Limpiar datos usando el mapeo del usuario
            df_clean = limpiar_y_estandarizar(
                df_display, sel_desde, sel_hasta, sel_ibc, sel_semanas
            )
            
            if df_clean.empty:
                st.error("No se pudieron convertir los datos con esas columnas. Verifica tu selección.")
            else:
                # Aplicar simultaneidad
                df_final = aplicar_regla_simultaneidad(df_clean)
                
                # --- RESULTADOS ---
                st.divider()
                st.header("3. Resultados del Estudio")
                
                # Métricas de validación inmediata
                total_sem = df_final['Semanas'].sum()
                st.info(f"Datos procesados: **{len(df_final)} periodos** encontrados. Total Semanas: **{total_sem:,.2f}**")
                
                # Instanciar Lógica
                liquidador = LiquidadorPension(df_final, genero, fecha_nacimiento)
                
                # 1. IBL
                ibl_10, _ = liquidador.calcular_ibl_indexado("ultimos_10")
                ibl_vida, _ = liquidador.calcular_ibl_indexado("toda_vida")
                ibl_fav = max(ibl_10, ibl_vida)
                origen = "Últimos 10" if ibl_10 >= ibl_vida else "Toda la Vida"
                
                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.subheader("Ingreso Base (IBL)")
                    st.bar_chart(pd.DataFrame({'Valor': [ibl_10, ibl_vida]}, index=['Últimos 10', 'Toda Vida']))
                    st.write(f"IBL Favorable: **${ibl_fav:,.0f}** ({origen})")
                
                # 2. Mesada
                with col_res2:
                    st.subheader("Mesada Pensional")
                    mesada, tasa, info = liquidador.calcular_tasa_reemplazo_797(ibl_fav, total_sem, datetime.now().year)
                    st.metric("Mesada Estimada", f"${mesada:,.0f}")
                    st.metric("Tasa Reemplazo", f"{tasa:.2f}%")
                    with st.expander("Ver detalle"):
                        st.write(info)
                
                # Tabla final para que el usuario valide que quedó bien
                st.markdown("#### Detalle usado para el cálculo:")
                st.dataframe(df_final)

    else:
        st.warning("No pude extraer una estructura de tabla clara. El PDF podría ser una imagen.")
