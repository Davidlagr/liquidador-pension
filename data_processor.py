import pdfplumber
import pandas as pd
import re

def limpiar_moneda(valor):
    """Convierte strings como '$ 1.500.000' a float"""
    if isinstance(valor, str):
        valor = valor.replace('$', '').replace('.', '').replace(',', '.').strip()
        try:
            return float(valor)
        except:
            return 0.0
    return valor

def procesar_pdf_historia_laboral(archivo_pdf):
    """
    Lee el PDF y extrae las columnas [1], [2], [3], [4], [5], [9].
    """
    datos = []
    
    # Regex ajustado al formato visual de Colpensiones
    # Busca patrones de fecha (AAAA-MM-DD o DD/MM/AAAA) para anclar la fila
    # Asumimos que la fila tiene: Aportante | Fechas | Salario | Semanas
    
    with pdfplumber.open(archivo_pdf) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            
            lines = text.split('\n')
            for line in lines:
                # Filtrar encabezados y basura
                if "Identificación" in line or "Historia Laboral" in line: continue
                
                parts = line.split()
                if len(parts) < 5: continue
                
                # Intentamos identificar si la línea tiene fechas válidas
                # Buscamos índices de fechas. Usualmente columna 3 y 4.
                # Estrategia: Buscar dos fechas en la linea
                try:
                    # Encontrar elementos que parecen fechas
                    fechas = [p for p in parts if re.match(r'\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}', p)]
                    
                    if len(fechas) >= 2:
                        fecha_desde = fechas[0]
                        fecha_hasta = fechas[1]
                        
                        # El salario suele estar después de las fechas
                        # Las semanas suelen estar al final
                        # Esta es una heurística; en producción se ajusta con coordenadas exactas (pdfplumber table)
                        
                        # Extraer indices
                        idx_desde = parts.index(fecha_desde)
                        
                        # Nombre aportante es todo lo anterior a la fecha (aprox)
                        aportante = " ".join(parts[:idx_desde])
                        # Limpiar ID del aportante si viene pegado
                        
                        # Asumimos posición relativa para IBC y Semanas
                        # Buscamos valores numéricos después de las fechas
                        valores_numericos = []
                        for x in parts[idx_desde+2:]:
                            clean_x = x.replace('.', '').replace(',', '.')
                            if re.match(r'^\d+(\.\d+)?$', clean_x):
                                valores_numericos.append(x)
                        
                        ibc = 0
                        semanas = 0
                        
                        if len(valores_numericos) >= 2:
                            ibc = limpiar_moneda(valores_numericos[0]) # Columna [5]
                            # A veces hay columnas intermedias vacias o ceros
                            semanas = float(valores_numericos[-1].replace(',', '.')) # Columna [9] usualmente la ultima
                        
                        datos.append({
                            "Aportante": aportante,
                            "Desde": fecha_desde,
                            "Hasta": fecha_hasta,
                            "IBC": ibc,
                            "Semanas": semanas
                        })
                except Exception as e:
                    continue

    df = pd.DataFrame(datos)
    
    # Normalización de fechas
    df['Desde'] = pd.to_datetime(df['Desde'], errors='coerce')
    df['Hasta'] = pd.to_datetime(df['Hasta'], errors='coerce')
    df = df.dropna(subset=['Desde', 'Hasta'])
    
    return df

def aplicar_regla_simultaneidad(df):
    """
    CRITICO: Si hay periodos superpuestos (mismo mes/año):
    1. Se SUMAN los IBC (Salarios).
    2. NO se suman las semanas (se toma la mayor o el tope de 4.28/mes).
    """
    if df.empty: return df
    
    # Crear columna Año-Mes para agrupar
    df['Periodo'] = df['Desde'].dt.to_period('M')
    
    # Agrupación
    df_consolidado = df.groupby('Periodo').agg({
        'IBC': 'sum',                # REGLA: Sumar bases de cotización
        'Semanas': 'max',            # REGLA: No sumar tiempo, tomar el reporte principal
        'Desde': 'min',
        'Hasta': 'max',
        'Aportante': lambda x: ' + '.join(x.unique()) # Rastro de simultaneidad
    }).reset_index()
    
    df_consolidado = df_consolidado.sort_values('Periodo')
    return df_consolidado
