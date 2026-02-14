import pdfplumber
import pandas as pd
import re

def limpiar_moneda(valor_str):
    """Limpia formatos de moneda: $ 1.000.000 -> 1000000.0"""
    if not isinstance(valor_str, str): return 0.0
    clean = valor_str.replace('$', '').replace(' ', '')
    clean = clean.replace('.', '') # Quitar miles
    clean = clean.replace(',', '.') # Decimal
    try:
        return float(clean)
    except:
        return 0.0

def limpiar_semanas(valor_str):
    """Limpia formatos de semanas: 4,29 o 4.29"""
    if not isinstance(valor_str, str): return 0.0
    clean = valor_str.strip().replace(' ', '')
    if not clean: return 0.0
    clean = clean.replace(',', '.')
    try:
        val = float(clean)
        return val
    except:
        return 0.0

def procesar_pdf_historia_laboral(archivo_pdf):
    datos = []
    
    # REGEX FLEXIBLE:
    # Acepta fechas con comillas "DD/MM/AAAA" O sin comillas DD/MM/AAAA
    # Estructura: Fecha1 + separador + Fecha2
    regex_fechas = re.compile(r'"?(\d{2}/\d{2}/\d{4})"?\s*,\s*"?(\d{2}/\d{2}/\d{4})"?')

    with pdfplumber.open(archivo_pdf) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += "\n" + text 

        # Buscar coincidencias en todo el texto unido
        for match in regex_fechas.finditer(full_text):
            fecha_desde = match.group(1)
            fecha_hasta = match.group(2)
            
            start_idx = match.start()
            end_idx = match.end()

            # --- 1. BUSCAR NOMBRE (HACIA ATRÁS) ---
            # Miramos 200 chars atrás. Buscamos texto entre comillas o al final de linea
            contexto_atras = full_text[max(0, start_idx-250):start_idx]
            
            nombre = "NO IDENTIFICADO"
            # Intento 1: Buscar texto entre comillas (formato CSV)
            match_nombre_comillas = re.findall(r'"([^"]+)"', contexto_atras)
            if match_nombre_comillas:
                # El último match suele ser el nombre, el penúltimo el ID
                candidato = match_nombre_comillas[-1].strip()
                # Si parece un ID (solo numeros), tomamos el anterior
                if re.match(r'^[\d\.]+$', candidato) and len(match_nombre_comillas) > 1:
                    nombre = match_nombre_comillas[-2].strip()
                else:
                    nombre = candidato
            else:
                # Intento 2: Si no hay comillas, tomar la línea anterior
                lineas = contexto_atras.split('\n')
                if lineas:
                    nombre = lineas[-1].strip()

            # --- 2. BUSCAR VALORES (HACIA ADELANTE) ---
            # Miramos 300 chars adelante
            contexto_adelante = full_text[end_idx:end_idx+350]
            
            # Dividimos por comas o espacios grandes
            tokens = re.split(r'",|,"|,\s*,|\s{2,}', contexto_adelante)
            tokens = [t.replace('"', '').strip() for t in tokens if t.strip()]

            salario = 0.0
            semanas = 0.0

            if tokens:
                # El primer token suele ser el salario
                salario = limpiar_moneda(tokens[0])
                
                # Buscamos las semanas en los tokens siguientes
                # Recorremos buscando el último número válido menor a 100 (semanas mes) o 1500 (total)
                candidatos_semanas = []
                for t in tokens[1:]:
                    # A veces hay saltos de linea pegados: "0\n4.29"
                    sub_tokens = t.split()
                    for sub in sub_tokens:
                        v = limpiar_semanas(sub)
                        # Validamos que sea un número de semanas razonable (0 a 2000)
                        if 0 < v < 2000:
                            candidatos_semanas.append(v)
                
                if candidatos_semanas:
                    # Usualmente el último número es el "Total Semanas" reportado
                    semanas = candidatos_semanas[-1]

            if semanas > 0:
                datos.append({
                    "Aportante": nombre.replace('\n', ' ').strip(),
                    "Desde": fecha_desde,
                    "Hasta": fecha_hasta,
                    "IBC": salario,
                    "Semanas": semanas
                })

    # CREACIÓN DEL DATAFRAME (BLINDADO)
    if not datos:
        # Retornamos vacío pero con los TIPOS CORRECTOS para evitar AttributeError
        df = pd.DataFrame(columns=['Aportante', 'Desde', 'Hasta', 'IBC', 'Semanas'])
        df['Desde'] = pd.to_datetime(df['Desde'])
        df['Hasta'] = pd.to_datetime(df['Hasta'])
        return df

    df = pd.DataFrame(datos)
    # Convertir a datetime explícitamente
    df['Desde'] = pd.to_datetime(df['Desde'], dayfirst=True, errors='coerce')
    df['Hasta'] = pd.to_datetime(df['Hasta'], dayfirst=True, errors='coerce')
    
    # Limpiar nulos resultantes
    df = df.dropna(subset=['Desde', 'Hasta'])
    df = df.sort_values('Desde')
    
    return df

def aplicar_regla_simultaneidad(df):
    if df.empty: return df
    
    # Asegurar tipos antes de operar
    df['IBC'] = pd.to_numeric(df['IBC'])
    df['Semanas'] = pd.to_numeric(df['Semanas'])
    
    # Si por alguna razón 'Desde' perdió el formato fecha (muy raro), reintentar
    if not pd.api.types.is_datetime64_any_dtype(df['Desde']):
         df['Desde'] = pd.to_datetime(df['Desde'], errors='coerce')

    df['Periodo'] = df['Desde'].dt.to_period('M')
    
    df_consolidado = df.groupby('Periodo').agg({
        'IBC': 'sum',
        'Semanas': 'max',
        'Desde': 'min',
        'Hasta': 'max',
        'Aportante': lambda x: ' / '.join(list(set(x))[:2])
    }).reset_index()
    
    return df_consolidado.sort_values('Periodo')
