import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Privado - Dr. Lagos", page_icon="⚖️", layout="wide")

# --- SEGURIDAD ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<br><br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.title("🔐 Acceso Restringido")
            password = st.text_input("Ingrese la clave maestra:", type="password")
            if st.button("Ingresar"):
                if password == "Lagos2026*":
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ Clave incorrecta.")
        return False
    return True

if check_password():
    # --- LÓGICA DE SALARIO MÍNIMO ---
    def obtener_smmlv_automatico():
        anio_actual = datetime.now().year
        # VALORES OFICIALES ACTUALIZADOS
        historico_smmlv = {
            2024: 1300000,
            2025: 1423500,
            2026: 1750905  # CORREGIDO SEGÚN DECRETO 1469/2025
        }
        return historico_smmlv.get(anio_actual, max(historico_smmlv.values()))

    # --- (Resto de funciones: generar_tabla_ipc, limpiar_num, extraer_fecha, etc.) ---
    # [Se mantienen igual para conservar la estabilidad del sistema]
    
    # --- INTERFAZ ---
    st.title("⚖️ Liquidador Pensional Pro")
    st.sidebar.info(f"SMMLV 2026: $1.750.905")
    
    # ... resto del código del liquidador ...
