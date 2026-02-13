import pdfplumber
import pandas as pd
import re

def procesar_pdf_historia_laboral(archivo_pdf):
    """
    Lee el PDF y retorna un DataFrame limpio con las columnas estandarizadas.
    """
    datos = []
    with pdfplumber.open(archivo_pdf) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines = text.split('\n')
                for line in lines:
                    # Expresión regular para detectar líneas de cotización
                    # Busca patrones de fechas y montos
                    # Adaptado a las columnas mencionadas: [1]... [2]...
                    # Esta lógica asume que el PDF es texto seleccionable.
                    
                    # LOGICA DE EXTRACCIÓN (Simplificada para el ejemplo)
                    # En la realidad, parsear el PDF de Colpensiones requiere un regex robusto
                    # Aquí simulamos que extraemos una línea válida
                    if "Periodo" in line or "Salario" in line:
                        continue
                        
                    # Simulación de extracción de datos basada en columnas visuales
                    # Se debe ajustar con el PDF real en mano para ver el espaciado
                    parts = line.split()
                    if len(parts) > 5:
                        try:
                            # Intentar parsear fechas para validar que es una linea de datos
                            # Asumimos estructura genérica para el ejemplo
                            datos.append({
                                "Aportante": "APORTANTE EJEMPLO", # Se extraería de [1] y [2]
                                "Desde": "2020-01-01", # Se extraería de [3]
                                "Hasta": "2020-01-30", # Se extraería de [4]
                                "IBC": 1500000, # Se extraería de [5]
                                "Semanas": 4.29, # Se extraería de [9]
                                "Origen": "PDF"
                            })
                        except:
                            pass

    # Si no logra leer (porque no tenemos el PDF real aquí para calibrar el regex),
    # creamos un DataFrame dummy para que el código no falle al probarlo.
    if not datos:
        return pd.DataFrame(columns=["Aportante", "Desde", "Hasta", "IBC", "Semanas"])

    df = pd.DataFrame(datos)
    
    # Conversión de tipos
    df['Desde'] = pd.to_datetime(df['Desde'])
    df['Hasta'] = pd.to_datetime(df['Hasta'])
    df['IBC'] = pd.to_numeric(df['IBC'])
    df['Semanas'] = pd.to_numeric(df['Semanas'])
    
    return df

def consolidar_historia_laboral(df):
    """
    Aplica la regla: Tiempos simultáneos NO suman semanas, pero SI suman IBC.
    Agrupa por Año-Mes.
    """
    if df.empty:
        return df

    # Crear columna Periodo (Año-Mes) para agrupar
    df['Periodo'] = df['Desde'].dt.to_period('M')

    # Agrupar
    df_consolidado = df.groupby('Periodo').agg({
        'IBC': 'sum',           # Se suman los salarios
        'Semanas': 'max',       # Se toma el máximo de semanas (aprox 4.28/mes), no la suma
        'Desde': 'min',
        'Hasta': 'max',
        'Aportante': lambda x: ' / '.join(x.unique()) # Concatenar nombres de empresas
    }).reset_index()

    return df_consolidado.sort_values('Periodo')
