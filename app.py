import streamlit as st
import pandas as pd
from datetime import date, datetime
from data_processor import extraer_tabla_cruda, limpiar_y_estandarizar, aplicar_regla_simultaneidad
from logic import LiquidadorPension

st.set_page_config(page_title="Liquidador Manual", layout="wide", page_icon="🛠️")
st.title("🛠️ Liquidador Pensional: Selección Manual")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Datos Usuario")
    nombre = st.text_input("Nombre")
    genero = st.radio("Género", ["Masculino", "Femenino"])
    fecha_nac = st.date_input("Fecha Nacimiento", value=date(1975,1,1))

# --- CARGA ---
uploaded_file = st.file_uploader("1. Sube PDF", type="pdf")

if 'df_crudo' not in st.session_state: st.session_state.df_crudo = None

if uploaded_file:
    if st.session_state.df_crudo is None:
        st.session_state.df_crudo = extraer_tabla_cruda(uploaded_file)
    
    df_disp = st.session_state.df_crudo
    
    if df_disp is not None and not df_disp.empty:
        st.success("Archivo leído. Selecciona las columnas:")
        st.dataframe(df_disp.head(3), use_container_width=True)
        
        cols = df_disp.columns.tolist()
        # Índices sugeridos
        c1, c2, c3, c4 = st.columns(4)
        col_d = c1.selectbox("Columna DESDE", cols, index=2 if len(cols)>2 else 0)
        col_h = c2.selectbox("Columna HASTA", cols, index=3 if len(cols)>3 else 0)
        col_i = c3.selectbox("Columna SALARIO", cols, index=4 if len(cols)>4 else 0)
        col_s = c4.selectbox("Columna SEMANAS", cols, index=len(cols)-1)
        
        if st.button("Calcular Liquidación"):
            # 1. Limpieza
            df_clean = limpiar_y_estandarizar(df_disp, col_d, col_h, col_i, col_s)
            
            if df_clean.empty:
                st.error("Error: Columnas sin datos válidos.")
            else:
                # 2. Consolidación
                df_final = aplicar_regla_simultaneidad(df_clean)
                
                # 3. Lógica
                liq = LiquidadorPension(df_final, genero, fecha_nac)
                
                # Calcular IBLs
                ibl_10, det_10 = liq.calcular_ibl_indexado("ultimos_10")
                ibl_vida, det_vida = liq.calcular_ibl_indexado("toda_vida")
                
                # Comparar
                ibl_fav = max(ibl_10, ibl_vida)
                origen = "Últimos 10 Años" if ibl_10 >= ibl_vida else "Toda la Vida (Desde 1967)"
                
                # RESULTADOS
                st.divider()
                st.header("Resultados")
                
                colL, colR = st.columns(2)
                
                with colL:
                    st.subheader("Análisis IBL")
                    st.write(f"IBL Favorable: **${ibl_fav:,.0f}** ({origen})")
                    st.bar_chart(pd.DataFrame({'IBL': [ibl_10, ibl_vida]}, index=['10 Años', 'Toda Vida']))
                    
                    # AUDITORÍA DE DATOS
                    with st.expander("🔍 Auditoría Técnica (Ver filas usadas)"):
                        st.write("Si seleccionaste 'Toda la Vida', aquí deben aparecer los años 80 indexados.")
                        mostrar = det_10 if ibl_10 >= ibl_vida else det_vida
                        st.dataframe(mostrar.style.format({
                            'IBC_Historico': "${:,.0f}",
                            'IBC_Actualizado': "${:,.0f}",
                            'Factor_IPC': "{:.2f}"
                        }))

                with colR:
                    st.subheader("Mesada Pensional")
                    total_sem = df_final['Semanas'].sum()
                    mesada, tasa, info = liq.calcular_tasa_reemplazo_797(ibl_fav, total_sem, datetime.now().year)
                    
                    st.metric("Semanas Totales", f"{total_sem:,.2f}")
                    st.metric("Mesada Estimada", f"${mesada:,.0f}")
                    st.metric("Tasa Reemplazo", f"{tasa:.2f}%")
                    
                    if liq.verificar_regimen_transicion():
                        st.success("Aplica Régimen de Transición")
    else:
        st.warning("Archivo vacío o ilegible.")

if st.sidebar.button("Reiniciar"):
    st.session_state.df_crudo = None
    st.rerun()
