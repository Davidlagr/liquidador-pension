import streamlit as st
import pandas as pd

# 1. Configuración de la página
st.set_page_config(page_title="Simulador de Mejora Pensional", layout="wide")
st.title("📊 Simulador de Mejora de Prestación (Colombia 2026)")

# Parámetros Globales
SMMLV_2026 = 1750905
TOPE_MAX = SMMLV_2026 * 25

# 2. Carga de archivo
uploaded_file = st.file_uploader("Sube tu archivo Excel con la Historia Laboral", type=["xlsx", "xls"])

if uploaded_file:
    try:
        # Leemos el archivo
        df = pd.read_excel(uploaded_file)
        
        # --- VALIDACIÓN DE COLUMNAS ---
        # Verificamos que existan las posiciones necesarias (G es 6, L es 11)
        if len(df.columns) < 12:
            st.error(f"❌ El archivo no tiene suficientes columnas. Se detectaron {len(df.columns)} de 12 requeridas.")
        else:
            # Seleccionamos las columnas por índice para evitar errores de nombres
            col_periodo = df.columns[3]  # Columna D [37]
            col_ibc = df.columns[6]      # Columna G [40]
            col_dias = df.columns[11]    # Columna L [45]

            # Limpieza básica
            df[col_ibc] = pd.to_numeric(df[col_ibc], errors='coerce').fillna(0)
            df[col_dias] = pd.to_numeric(df[col_dias], errors='coerce').fillna(30)

            # 3. Lógica de Escenarios
            def proyectar(valor, incremento, dias):
                nuevo = valor * incremento
                minimo_prop = (SMMLV_2026 / 30) * dias
                return min(max(nuevo, minimo_prop), TOPE_MAX)

            # Creamos los escenarios
            df['IBC +20%'] = df.apply(lambda x: proyectar(x[col_ibc], 1.20, x[col_dias]), axis=1)
            df['IBC +30%'] = df.apply(lambda x: proyectar(x[col_ibc], 1.30, x[col_dias]), axis=1)
            df['IBC +50%'] = df.apply(lambda x: proyectar(x[col_ibc], 1.50, x[col_dias]), axis=1)

            # 4. Mostrar Resultados
            st.subheader("Resultados de la Simulación")
            
            # Métricas rápidas
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Promedio Actual", f"${df[col_ibc].mean():,.0f}")
            c2.metric("Escenario 20%", f"${df['IBC +20%'].mean():,.0f}")
            c3.metric("Escenario 30%", f"${df['IBC +30%'].mean():,.0f}")
            c4.metric("Escenario 50%", f"${df['IBC +50%'].mean():,.0f}")

            # Tabla comparativa
            st.dataframe(df[[col_periodo, col_ibc, 'IBC +20%', 'IBC +30%', 'IBC +50%']])

    except Exception as e:
        st.error(f"⚠️ Se produjo un error al procesar los datos: {e}")
else:
    st.info("👋 Por favor, sube un archivo Excel para comenzar la validación.")
