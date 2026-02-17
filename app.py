import streamlit as st
import pandas as pd
from datetime import date, datetime
from data_processor import extraer_tabla_cruda, limpiar_y_estandarizar, aplicar_regla_simultaneidad
from logic import LiquidadorPension

st.set_page_config(page_title="Liquidador Manual", layout="wide", page_icon="🛠️")

st.title("🛠️ Liquidador Pensional: Selección Manual de Columnas")
st.markdown("El sistema extraerá todas las columnas posibles. **Tú debes indicar cuál es cuál.**")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Datos del Usuario")
    nombre = st.text_input("Nombre", "Usuario")
    fecha_nacimiento = st.date_input("Fecha Nacimiento", value=date(1975, 1, 1))
    genero = st.radio("Género", ["Masculino", "Femenino"])

# --- PASO 1: CARGA DE PDF ---
uploaded_file = st.file_uploader("1. Sube tu Historia Laboral (PDF)", type="pdf")

# Usamos session_state para que no se borre la tabla al interactuar
if 'df_crudo' not in st.session_state:
    st.session_state.df_crudo = None

if uploaded_file:
    # Procesar solo si es un archivo nuevo o no hay datos cargados
    if st.session_state.df_crudo is None:
        with st.spinner("Desfragmentando PDF (esto toma unos segundos)..."):
            st.session_state.df_crudo = extraer_tabla_cruda(uploaded_file)

    df_display = st.session_state.df_crudo

    # Validar si se extrajo algo
    if df_display is not None and not df_display.empty:
        st.success("✅ Estructura extraída exitosamente.")
        
        # --- PASO 2: MAPEO DE COLUMNAS ---
        st.markdown("### 2. Configura las columnas")
        st.info("Mira la tabla de muestra abajo y selecciona el nombre de la columna correcta en los menús.")
        
        # Muestra las primeras 5 filas para que el usuario se guíe
        st.dataframe(df_display.head(5), use_container_width=True)
        
        cols = df_display.columns.tolist()
        
        # Intentamos pre-seleccionar índices lógicos si existen
        idx_d = 2 if len(cols) > 2 else 0
        idx_h = 3 if len(cols) > 3 else 0
        idx_i = 4 if len(cols) > 4 else 0
        idx_s = len(cols) - 1
        
        c1, c2, c3, c4 = st.columns(4)
        col_desde = c1.selectbox("¿Dónde está FECHA DESDE?", cols, index=idx_d)
        col_hasta = c2.selectbox("¿Dónde está FECHA HASTA?", cols, index=idx_h)
        col_ibc = c3.selectbox("¿Dónde está el SALARIO (IBC)?", cols, index=idx_i)
        col_semanas = c4.selectbox("¿Dónde están las SEMANAS?", cols, index=idx_s)
        
        # --- PASO 3: CALCULAR ---
        if st.button("🚀 Confirmar Selección y Liquidar"):
            
            # Limpiar datos con la selección del usuario
            df_clean = limpiar_y_estandarizar(
                df_display, col_desde, col_hasta, col_ibc, col_semanas
            )
            
            if df_clean.empty:
                st.error("Error: Las columnas seleccionadas no contienen datos válidos (Fechas o Números). Intenta con otras.")
            else:
                # Aplicar simultaneidad
                df_final = aplicar_regla_simultaneidad(df_clean)
                
                # --- RESULTADOS ---
                st.divider()
                st.header("3. Resultados del Estudio")
                
                # Resumen de lectura
                total_sem = df_final['Semanas'].sum()
                min_y = df_final['Desde'].dt.year.min()
                max_y = df_final['Hasta'].dt.year.max()
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Semanas", f"{total_sem:,.2f}")
                m2.metric("Rango Años", f"{min_y} - {max_y}")
                m3.metric("Registros", len(df_final))
                
                # Motor de Cálculo
                liquidador = LiquidadorPension(df_final, genero, fecha_nacimiento)
                
                # Gráficos y Datos
                col_L, col_R = st.columns(2)
                
                # IBL
                ibl_10, _ = liquidador.calcular_ibl_indexado("ultimos_10")
                ibl_vida, _ = liquidador.calcular_ibl_indexado("toda_vida")
                ibl_fav = max(ibl_10, ibl_vida)
                origen = "Últimos 10 Años" if ibl_10 >= ibl_vida else "Toda la Vida"
                
                with col_L:
                    st.subheader("Ingreso Base (IBL)")
                    st.bar_chart(pd.DataFrame({'Valor': [ibl_10, ibl_vida]}, index=['Últimos 10', 'Toda Vida']))
                    st.write(f"**IBL Más Favorable:** {origen}")
                    st.metric("Monto IBL", f"${ibl_fav:,.0f}")

                with col_R:
                    st.subheader("Mesada Pensional")
                    mesada, tasa, info = liquidador.calcular_tasa_reemplazo_797(ibl_fav, total_sem, datetime.now().year)
                    
                    st.metric("Mesada Estimada", f"${mesada:,.0f}")
                    st.metric("Tasa Reemplazo", f"{tasa:.2f}%")
                    
                    with st.expander("Ver detalle de cálculo"):
                        st.write(info)
                        if liquidador.verificar_regimen_transicion():
                            st.success("Aplica Régimen de Transición (Dec. 758/90)")

                # Tabla Final
                st.markdown("#### Tabla Depurada Usada para el Cálculo")
                st.dataframe(df_final)

    else:
        st.warning("El archivo parece vacío o es una imagen sin texto reconocible.")

# Botón para reiniciar si carga otro archivo
if st.sidebar.button("Reiniciar / Cargar Nuevo Archivo"):
    st.session_state.df_crudo = None
    st.rerun()
