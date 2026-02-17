import pdfplumber
import pandas as pd
import re

def limpiar_numero_flexible(valor_str):
    """
    Intenta convertir cualquier string con números a float.
    Maneja: "1.500.000", "5.500", "4,29", "30"
    """
    if not isinstance(valor_str, str): return None
    
    # 1. Limpieza inicial
    clean = re.sub(r'[^\d\.,]', '', valor_str)
    if not clean: return None

    # 2. Heurística para puntos y comas
    if ',' in clean and '.' in clean:
        if clean.find(',') > clean.find('.'): # 1.500,00
            clean = clean.replace('.', '').replace(',', '.')
        else: # 1,500.00
            clean = clean.replace(',', '')
    elif ',' in clean: 
        # Si tiene 2 decimales (4,29) es punto. Si son 3 (1,500) es mil.
        parts = clean.split(',')
        if len(parts) > 1 and len(parts[-1]) == 2: 
            clean = clean.replace(',', '.')
        else:
            clean = clean.replace(',', '')
    elif clean.count('.') > 1: # 1.500.000
        clean = clean.replace('.', '')
    
    try:
        return float(clean)
    except:
        return None

def procesar_pdf_historia_laboral(archivo_pdf):
    datos = []
    
    # REGEX NUCLEAR: Busca par de fechas ignorando basura intermedia
    # Esto funciona para formatos con y sin comillas (1980 vs 2024)
    regex_fechas = re.compile(r'(\d{2}/\d{2}/\d{4})[^\d]{1,150}(\d{2}/\d{2}/\d{4})')

    full_text = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += "\n" + text

    # Iteramos sobre todas las fechas encontradas
    for match in regex_fechas.finditer(full_text):
        fecha_desde = match.group(1)
        fecha_hasta = match.group(2)
        end_idx = match.end()
        start_idx = match.start()

        # 1. NOMBRE (HACIA ATRÁS)
        bloque_atras = full_text[max(0, start_idx-250):start_idx]
        # Buscamos texto entre comillas o la última línea legible
        nombres = re.findall(r'"([^"]+)"', bloque_atras)
        nombre = "NO IDENTIFICADO"
        
        if nombres:
            # Filtramos basura (fechas o IDs sueltos capturados como nombre)
            candidatos = [n for n in nombres if len(n) > 3 and not re.search(r'\d{2}/\d{2}/\d{4}', n)]
            if candidatos: nombre = candidatos[-1]
        else:
            # Fallback para años viejos sin comillas
            lineas = bloque_atras.strip().split('\n')
            if lineas: nombre = lineas[-1].strip()

        # 2. VALORES (HACIA ADELANTE)
        bloque_adelante = full_text[end_idx:end_idx+350]
        # Tokenizamos por espacios o separadores CSV
        tokens = re.split(r'["\n\s;]+', bloque_adelante)
        
        numeros = []
        for t in tokens:
            val = limpiar_numero_flexible(t)
            if val is not None: numeros.append(val)
        
        ibc = 0.0
        semanas = 0.0

        if numeros:
            # --- LÓGICA CORREGIDA PARA AÑOS 80 ---
            
            # 1. SALARIO (IBC)
            # En 1967 salario min era ~420 pesos.
            # Regla: Cualquier número MAYOR a 55 es salario (porque semanas max es 54).
            posibles_salarios = [n for n in numeros if n > 55]
            
            if posibles_salarios:
                ibc = posibles_salarios[0] # El primer número grande es el salario
            
            # 2. SEMANAS
            # Regla: Números entre 0 y 55.
            posibles_semanas = [n for n in numeros if 0 < n <= 55]
            
            if posibles_semanas:
                # Prioridad a decimales (4.29) sobre enteros (30)
                decimales = [n for n in posibles_semanas if n % 1 != 0]
                if decimales:
                    semanas = decimales[-1]
                else:
                    # Si solo hay enteros (ej: 50 semanas), tomamos el último
                    semanas = posibles_semanas[-1]

        if semanas > 0:
            datos.append({
                "Aportante": nombre,
                "Desde": fecha_desde,
                "Hasta": fecha_hasta,
                "IBC": ibc,
                "Semanas": semanas
            })

    # Crear DF
    if not datos: return pd.DataFrame(columns=['Aportante', 'Desde', 'Hasta', 'IBC', 'Semanas'])
    
    df = pd.DataFrame(datos)
    df['Desde'] = pd.to_datetime(df['Desde'], dayfirst=True, errors='coerce')
    df['Hasta'] = pd.to_datetime(df['Hasta'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Desde', 'Hasta'])
    
    return df.sort_values('Desde')

def aplicar_regla_simultaneidad(df):
    if df.empty: return df
    df['IBC'] = pd.to_numeric(df['IBC'])
    df['Semanas'] = pd.to_numeric(df['Semanas'])
    df['Periodo'] = df['Desde'].dt.to_period('M')
    
    return df.groupby('Periodo').agg({
        'IBC': 'sum',
        'Semanas': 'max',
        'Desde': 'min',
        'Hasta': 'max',
        'Aportante': lambda x: ' / '.join(list(set(str(v) for v in x))[:2])
    }).reset_index().sort_values('Periodo')
