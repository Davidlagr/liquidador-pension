import pdfplumber
import pandas as pd
import re

def limpiar_moneda(valor_str):
    """
    Busca el primer patrón numérico que parezca dinero en un texto sucio.
    Maneja: "$ 1.200.000", "1200000", "1.200.000"
    """
    if not isinstance(valor_str, str): return 0.0
    # Buscar patrones de números con puntos/comas
    match = re.search(r'\$?\s*([\d\.,]+)', valor_str)
    if match:
        clean = match.group(1).replace('.', '').replace(',', '.')
        try:
            return float(clean)
        except:
            return 0.0
    return 0.0

def limpiar_semanas(valor_str):
    """
    Limpia el valor de semanas. Prioriza formato 4,29 o 4.29.
    """
    if not isinstance(valor_str, str): return 0.0
    # Limpiar basura alrededor
    clean = valor_str.strip().replace('\n', '').replace(' ', '')
    if not clean: return 0.0
    
    # Reemplazar coma por punto (estándar float Python)
    clean = clean.replace(',', '.')
    
    try:
        val = float(clean)
        return val
    except:
        return 0.0

def procesar_pdf_historia_laboral(archivo_pdf):
    datos = []
    
    # PATRÓN MAESTRO: Busca "FECHA","FECHA"
    # Captura: (Fecha1) ... (Fecha2)
    # Explicación regex: 
    #   "(\d{2}/\d{2}/\d{4})"  -> Busca Fecha DD/MM/AAAA entre comillas
    #   \s*,\s* -> Seguido de una coma (con posibles espacios)
    #   "(\d{2}/\d{2}/\d{4})"  -> Seguido de otra Fecha DD/MM/AAAA entre comillas
    regex_fechas = re.compile(r'"(\d{2}/\d{2}/\d{4})"\s*,\s*"(\d{2}/\d{2}/\d{4})"')

    with pdfplumber.open(archivo_pdf) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += "\n" + text # Unir todo el texto para manejar cortes de página

        # Iterar sobre cada coincidencia de fechas encontrada en todo el documento
        for match in regex_fechas.finditer(full_text):
            fecha_desde = match.group(1)
            fecha_hasta = match.group(2)
            
            start_idx = match.start()
            end_idx = match.end()

            # 1. BUSCAR NOMBRE (HACIA ATRÁS)
            # Miramos los 200 caracteres anteriores a la fecha
            contexto_atras = full_text[max(0, start_idx-200):start_idx]
            # Buscamos el último texto entre comillas antes de la fecha
            # Regex: "([^"]+)"\s*,\s*$ (Busca algo entre comillas justo antes del final)
            match_nombre = re.findall(r'"([^"]+)"', contexto_atras)
            
            nombre = "NO IDENTIFICADO"
            if match_nombre:
                # El último match suele ser el nombre (el penúltimo podría ser el ID)
                nombre = match_nombre[-1].strip()
                # Limpieza extra: si el nombre es solo números, probablemente cogimos el ID, intentamos el anterior
                if re.match(r'^[\d\.]+$', nombre) and len(match_nombre) > 1:
                    nombre = match_nombre[-2].strip()

            # 2. BUSCAR SALARIO Y SEMANAS (HACIA ADELANTE)
            # Miramos los 300 caracteres después de la segunda fecha
            contexto_adelante = full_text[end_idx:end_idx+300]
            
            # Dividimos por comas para aproximar columnas CSV, ignorando comillas vacías
            tokens = re.split(r'",|,"|,\s*,', contexto_adelante)
            tokens = [t.replace('"', '').strip() for t in tokens if t.strip()]

            salario = 0.0
            semanas = 0.0

            if tokens:
                # ESTRATEGIA SALARIO: El primer token suele ser el salario
                # A veces viene con $, a veces no.
                raw_salario = tokens[0]
                salario = limpiar_moneda(raw_salario)

                # ESTRATEGIA SEMANAS:
                # Buscamos números en los tokens restantes. 
                # La columna "Total" suele ser la última válida de la fila o la penúltima.
                # Recorremos los tokens buscando valores numéricos < 1500 (semanas lógicas)
                candidatos_semanas = []
                for t in tokens[1:]: # Saltamos el salario
                    # Limpieza agresiva de saltos de linea dentro del token (caso PDF 2022-12)
                    sub_tokens = t.split() 
                    for sub in sub_tokens:
                        v = limpiar_semanas(sub)
                        if 0 < v < 2000: # Filtro de cordura
                            candidatos_semanas.append(v)
                
                if candidatos_semanas:
                    # Usualmente el último número es el "Total Semanas" corregido
                    semanas = candidatos_semanas[-1]

            # Guardar el registro si encontramos datos válidos
            if semanas > 0:
                datos.append({
                    "Aportante": nombre.replace('\n', ' '), # Quitar saltos de linea en nombres
                    "Desde": pd.to_datetime(fecha_desde, dayfirst=True, errors='coerce'),
                    "Hasta": pd.to_datetime(fecha_hasta, dayfirst=True, errors='coerce'),
                    "IBC": salario,
                    "Semanas": semanas
                })

    # Crear DataFrame
    if not datos:
        return pd.DataFrame(columns=['Aportante', 'Desde', 'Hasta', 'IBC', 'Semanas'])

    df = pd.DataFrame(datos)
    df = df.dropna(subset=['Desde', 'Hasta'])
    df = df.sort_values('Desde')
    
    return df

def aplicar_regla_simultaneidad(df):
    """
    Agrupa por mes (Periodo). Suma IBC, Máximo de Semanas.
    """
    if df.empty: return df
    
    df['Periodo'] = df['Desde'].dt.to_period('M')
    
    df_consolidado = df.groupby('Periodo').agg({
        'IBC': 'sum',
        'Semanas': 'max', # Regla: no sumar semanas en el mismo mes
        'Desde': 'min',
        'Hasta': 'max',
        'Aportante': lambda x: ' / '.join(list(set(x))[:2]) # Limitar largo nombre
    }).reset_index()
    
    return df_consolidado.sort_values('Periodo')
