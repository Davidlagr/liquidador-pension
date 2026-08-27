import streamlit as st
import pandas as pd
import numpy as np

def modulo_mejora_pensional():
    st.title("Módulo de Proyección y Mejora Pensional")
    st.subheader("Análisis de Viabilidad Financiera y Costos de Cotización")

    # Parámetros de entrada de la proyección
    with st.expander("Parámetros de Proyección", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            mesada_actual = st.number_input("Mesada Pensional Actual ($)", value=1750905, step=100000)
            ibc_proyectado = st.number_input("IBC Mensual Proyectado ($)", value=43772625, step=1000000)
        with col2:
            mesada_proyectada = st.number_input("Nueva Mesada Proyectada ($)", value=28086266, step=100000)
            meses_proyeccion = st.number_input("Meses a Proyectar (Ej. 5 años = 60)", value=60, step=12)

    # Porcentajes de Ley para Independientes
    tasa_pension = 0.16
    tasa_salud = 0.125
    tasa_fsp = 0.02 # 2% para IBC mayores a 20 SMLMV (Fondo de Solidaridad y Subsistencia)

    if st.button("Generar Cuadro de Cálculos y Reporte"):
        # Generación del DataFrame con los cálculos mes a mes
        meses = np.arange(1, meses_proyeccion + 1)
        
        # Para mayor precisión, se puede añadir un factor de incremento anual del IPC/SMLMV, 
        # aquí proyectamos un escenario estático como base, pero escalable.
        df_proyeccion = pd.DataFrame({
            "Mes": meses,
            "IBC Proyectado": ibc_proyectado,
            "Aporte Pensión (16%)": ibc_proyectado * tasa_pension,
            "Aporte Salud (12.5%)": ibc_proyectado * tasa_salud,
            "Aporte FSP (2%)": ibc_proyectado * tasa_fsp,
        })
        
        df_proyeccion["Costo Mensual Total"] = df_proyeccion["Aporte Pensión (16%)"] + df_proyeccion["Aporte Salud (12.5%)"] + df_proyeccion["Aporte FSP (2%)"]
        df_proyeccion["Inversión Acumulada"] = df_proyeccion["Costo Mensual Total"].cumsum()

        # Métricas de rentabilidad (ROI y Delta)
        inversion_total = df_proyeccion["Costo Mensual Total"].sum()
        delta_mensual = mesada_proyectada - mesada_actual
        meses_retorno = inversion_total / delta_mensual if delta_mensual > 0 else 0
        anios_retorno = meses_retorno / 12

        st.divider()
        st.subheader("1. Resumen Ejecutivo de la Proyección")
        
        met1, met2, met3, met4 = st.columns(4)
        met1.metric("Inversión Total Estimada", f"${inversion_total:,.0f}")
        met2.metric("Incremento Mesada (Delta)", f"${delta_mensual:,.0f}")
        met3.metric("Nueva Mesada", f"${mesada_proyectada:,.0f}")
        met4.metric("ROI (Años)", f"{anios_retorno:.2f}")

        st.divider()
        st.subheader("2. Cuadro de Cálculos Detallado (Aportes de Bolsillo)")
        
        # Formatear el dataframe para mostrar en Streamlit
        df_mostrar = df_proyeccion.style.format({
            "IBC Proyectado": "${:,.0f}",
            "Aporte Pensión (16%)": "${:,.0f}",
            "Aporte Salud (12.5%)": "${:,.0f}",
            "Aporte FSP (2%)": "${:,.0f}",
            "Costo Mensual Total": "${:,.0f}",
            "Inversión Acumulada": "${:,.0f}"
        })
        
        st.dataframe(df_mostrar, use_container_width=True)

        # Generador del texto formal para el reporte legal
        st.divider()
        st.subheader("3. Proyecto de Texto para el Dictamen Técnico")
        
        texto_reporte = f"""
**5. PROYECCIÓN ESTRATÉGICA Y ANÁLISIS DE COSTOS DE INVERSIÓN PENSIONAL**

En el marco del principio de favorabilidad y con el objetivo de maximizar la Tasa de Reemplazo, se proyecta un esquema de cotización como trabajador independiente sobre un Ingreso Base de Cotización (IBC) equivalente a 25 SMLMV durante un periodo de {int(meses_proyeccion/12)} años ({meses_proyeccion} meses).

**Desagregación del Esfuerzo Financiero (Costos Asumidos al 100% por el Afiliado):**
*   **Aporte a Pensión (16%):** ${ibc_proyectado * tasa_pension:,.0f} mensuales.
*   **Aporte a Salud (12.5%):** ${ibc_proyectado * tasa_salud:,.0f} mensuales.
*   **Aporte Fondo de Solidaridad Pensional (2% tope):** ${ibc_proyectado * tasa_fsp:,.0f} mensuales.
*   **COSTO TOTAL MENSUAL:** ${ibc_proyectado * (tasa_pension+tasa_salud+tasa_fsp):,.0f}

**Resumen de Viabilidad (ROI):**
*   **Inversión Total Acumulada de Bolsillo:** ${inversion_total:,.0f}
*   **Mesada Pensional Actual:** ${mesada_actual:,.0f}
*   **Nueva Mesada Proyectada (Últimos 10 Años):** ${mesada_proyectada:,.0f}
*   **Incremento Neto Mensual (Delta):** ${delta_mensual:,.0f}
*   **Tiempo de Retorno de la Inversión (ROI):** El capital invertido se recuperará íntegramente en {anios_retorno:.1f} años a partir del reconocimiento y pago de la primera mesada pensional reajustada.
"""
        st.markdown(texto_reporte)

        # Opción para descargar los cálculos en Excel
        csv = df_proyeccion.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar Cuadro de Cálculos en CSV",
            data=csv,
            file_name='proyeccion_pensional.csv',
            mime='text/csv',
        )

if __name__ == "__main__":
    modulo_mejora_pensional()
