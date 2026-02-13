import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
from datetime import datetime

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Puedes cambiar esta clave por la que tú quieras
CLAVE_MAESTRA = "Lagos2026*" 

def check_password():
    """Retorna True si el usuario ingresó la clave correcta."""
    if "password_correct" not in st.session_state:
        # Primera vez, mostrar formulario
        st.title("🔒 Acceso Restringido")
        st.markdown("### Sistema de Liquidación - Dr. Lagos")
        password = st.text_input("Ingrese la clave de acceso:", type="password")
        if st.button("Ingresar"):
            if password == CLAVE_MAESTRA:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ Clave incorrecta")
        return False
    return True

# --- INICIO DE LA APP ---
if check_password():
    # TODO EL CÓDIGO QUE YA TENÍAMOS VA AQUÍ ADENTRO
    st.set_page_config(page_title="Liquidador Pensional Pro - Dr. Lagos", page_icon="⚖️", layout="wide")
    
    # (Aquí pegas el resto del código que ya tenías: estilos, funciones de IPC, interfaz, etc.)
    # IMPORTANTE: Asegúrate de que todo el código del liquidador esté INDENTADO (con 4 espacios a la derecha)
    # para que Python entienda que solo se ejecuta SI la clave es correcta.
    
    st.sidebar.success("✅ Acceso Autorizado")
    
    # ... resto del código ...
