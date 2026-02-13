import pandas as pd
import numpy as np

# 1. CONFIGURACIÓN DE PARÁMETROS (Valores 2026)
SMMLV_2026 = 1750905
TOPE_MAX_25_SMMLV = SMMLV_2026 * 25
VALOR_DIA_MIN = SMMLV_2026 / 30

def simulador_mejora_pensional(df_input):
    """
    df_input debe tener al menos:
    - Columna G (índice 6): IBC Reportado
    - Columna L (índice 11): Días cotizados
    """
    df = df_input.copy()
    
    # Identificar columnas por posición (según tu estructura G[40] y L[45])
    # G es la columna 7 (index 6), L es la columna 12 (index 11)
    col_ibc_original = df.columns[6]
    col_dias = df.columns[11]
    
    # Limpieza de datos: Convertir a numérico y tratar nulos
    df[col_ibc_original] = pd.to_numeric(df[col_ibc_original], errors='coerce').fillna(0)
    df[col_dias] = pd.to_numeric(df[col_dias], errors='coerce').fillna(30) # Asumimos 30 si está vacío

    # Función interna para aplicar topes legales
    def aplicar_topes(valor_ibc, dias):
        # El mínimo es proporcional a los días trabajados
        minimo_proporcional = VALOR_DIA_MIN * dias
        
        # Aplicar el piso (SMMLV proporcional)
        nuevo_ibc = max(valor_ibc, minimo_proporcional)
        
        # Aplicar el techo (25 SMMLV)
        nuevo_ibc = min(nuevo_ibc, TOPE_MAX_25_SMMLV)
        
        return nuevo_ibc

    # 2. GENERACIÓN DE ESCENARIOS
    escenarios = {
        'Escenario_20': 1.20,
        'Escenario_30': 1.30,
        'Escenario_50': 1.50
    }

    for nombre, multiplicador in escenarios.items():
        # Calculamos el incremento base
        df[nombre] = df[col_ibc_original] * multiplicador
        
        # Aplicamos topes legales fila por fila considerando los días
        df[nombre] = df.apply(lambda x: aplicar_topes(x[nombre], x[col_dias]), axis=1)

    # 3. CÁLCULO DE RESULTADOS (IBL Promedio)
    resumen = {
        'Concepto': ['IBC Promedio (IBL)', 'Incremento vs Original'],
        'Original': [df[col_ibc_original].mean(), 0]
    }

    for nombre in escenarios.keys():
        promedio = df[nombre].mean()
        dif_porcentaje = ((promedio / resumen['Original'][0]) - 1) * 100
        resumen[nombre] = [promedio, f"{dif_porcentaje:.2f}%"]

    df_resumen = pd.DataFrame(resumen)
    
    return df, df_resumen

# --- EJEMPLO DE USO CON DATOS DE PRUEBA ---
if __name__ == "__main__":
    # Creamos un DataFrame de ejemplo similar a tu estructura
    data = {
        'Periodo': ['2025-01', '2025-02', '2025-03', '2025-04'],
        'A': [0]*4, 'B': [0]*4, 'C': [0]*4, 'D': [0]*4, 'E': [0]*4,
        'IBC_Reportado': [1800000, 2500000, 1750905, 45000000], # G [40]
        'H': [0]*4, 'I': [0]*4, 'J': [0]*4, 'K': [0]*4,
        'Dias': [30, 15, 30, 30] # L [45]
    }
    df_prueba = pd.DataFrame(data)

    df_resultado, tabla_comparativa = simulador_mejora_pensional(df_prueba)

    print("--- TABLA COMPARATIVA DE ESCENARIOS ---")
    print(tabla_comparativa.to_string(index=False))
    
    print("\n--- DETALLE DE LOS PRIMEROS REGISTROS ---")
    columnas_ver = ['IBC_Reportado', 'Dias', 'Escenario_20', 'Escenario_30', 'Escenario_50']
    print(df_resultado[columnas_ver].head())
