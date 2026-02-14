import pdfplumber
import pandas as pd
import re

def limpiar_moneda(valor_str):
    """
    Busca el primer patrón numérico que parezca dinero en un texto sucio.
    Maneja: "$ 1.200.000", "1200000", "1.200.000", "7.470"
    """
    if not isinstance(valor_str, str): return 0.0
    # Buscar patrón de moneda: dígitos con puntos/comas opcionales
    # Ignora el signo $ y espacios
    match = re.search(r'(?:[\d]{1,3}(?:[.,]\d{3})*|[.,]\d+)(?:[.,]\d+)?', valor_str)
    if match:
        clean = match.group(0).replace('.', '').replace(',', '.')
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
    clean = valor_str.strip()
    if not clean: return 0.0
    
    # Truco para "124.29\n0.00": tomar solo el primer valor numérico limpio
    # O limpiar saltos de linea
    clean = clean.split()[0] # Tomar la primera "palabra" si hay varias pegadas
    
    clean = clean.replace(',', '.')
    try:
        val = float(clean)
        return val
    except:
        return 0.0

def procesar_pdf_historia_laboral(archivo_pdf):
    datos = []
    
    # PATRÓN DE ORO (REGEX) MEJORADO v4
    # Explica al motor que entre la fecha y la coma puede haber CUALQUIER COSA
    # (comillas, espacios, saltos de línea \n, tabulaciones)
    # Grupo 1: Fecha Inicio
    # Grupo 2: Fecha Fin
    regex_fechas = re.compile(r'(\d{2}/\d{2}/\d{4})\s*["\n]*\s*,\s*["\n]*\s*(\d{2}/\d{2}/\d{4})')

    with pdfplumber.open(archivo_pdf) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += "\n" + text 

        # Iterar sobre cada coincidencia de fechas encontrada
        for match in regex_fechas.finditer(full_text):
            fecha_desde = match.group(1)
            fecha_hasta = match.group(2)
            
            start_idx = match.start()
            end_idx = match.end()

            # --- 1. BUSCAR NOMBRE (HACIA ATRÁS) ---
            # Miramos 250 caracteres hacia atrás
            contexto_atras = full_text[max(0, start_idx-250):start_idx]
            
            nombre = "NO IDENTIFICADO"
            # Buscamos el último texto que esté entre comillas
            matches_comillas = re.findall(r'"([^"]+)"', contexto_atras)
            
            if matches_comillas:
                # El último suele ser el nombre. El penúltimo el ID.
                candidato = matches_comillas[-1].strip()
                # Validación simple: si el nombre son solo números, probablemente es el NIT/CC
                if re.match(r'^[\d\.,]+$', candidato) and len(matches_comillas) > 1:
                    nombre = matches_comillas[-2].strip()
                else:
                    nombre = candidato
            else:
                # Si no hay comillas, tomamos la línea inmediatamente anterior no vacía
                lineas = [l.strip() for l in contexto_atras.split('\n') if l.strip()]
                if lineas:
                    nombre = lineas[-1]

            # --- 2. BUSCAR VALORES (HACIA ADELANTE) ---
            # Miramos 400 caracteres hacia adelante para asegurar capturar semanas lejanas
            contexto_adelante = full_text[end_idx:end_idx+400]
            
            # Dividimos por la estructura de CSV (comilla-coma-comilla) O salto de línea grande
            tokens = re.split(r'",|,"|,\s*,', contexto_adelante)
            
            # Limpieza básica de tokens (quitar comillas sueltas)
            tokens = [t.replace('"', '').strip() for t in tokens if t.strip()]

            salario = 0.0
            semanas = 0.0

            if tokens:
                # El salario suele ser el primer token después de las fechas
                salario = limpiar_moneda(tokens[0])
                
                # Las semanas están en los tokens siguientes.
                # A veces Colpensiones pone "0.00" y luego "4.29".
                # Buscamos TODOS los números válidos y tomamos el mayor o el último > 0
                candidatos_semanas = []
                
                for t in tokens[1:]:
                    # A veces un token trae basura: "4.29\n0.00"
                    # Lo partimos por espacios/enters
                    sub_tokens = t.split()
                    for sub in sub_tokens:
                        v = limpiar_semanas(sub)
                        # Filtro de cordura: Semanas entre 0 y 1500 (aprox 30 años en un solo registro, raro pero posible)
                        if 0 < v < 2000:
                            candidatos_semanas.append(v)
                
                if candidatos_semanas:
                    # Usualmente el último valor es el "Total Semanas" reportado en la col 9
                    semanas = candidatos_semanas[-1]

            # Solo guardamos si hay datos coherentes
            if semanas > 0:
                datos.append({
                    "Aportante": nombre.replace('\n', ' ').strip(),
                    "Desde": fecha_desde,
                    "Hasta": fecha_hasta,
                    "IBC": salario,
                    "Semanas": semanas
                })

    # RETORNO SEGURO (Dataframe vacío con columnas si no hay datos)
    if not datos:
        df = pd.DataFrame(columns=['Aportante', 'Desde', 'Hasta', 'IBC', 'Semanas'])
        df['Desde'] = pd.to_datetime(df['Desde'])
        df['Hasta'] = pd.to_datetime(df['Hasta'])
        return df

    df = pd.DataFrame(datos)
    df['Desde'] = pd.to_datetime(df['Desde'], dayfirst=True, errors='coerce')
    df['Hasta'] = pd.to_datetime(df['Hasta'], dayfirst=True, errors='coerce')
    
    # Limpieza final
    df = df.dropna(subset=['Desde', 'Hasta'])
    df = df.sort_values('Desde')
    
    return df

def aplicar_regla_simultaneidad(df):
    if df.empty: return df
    
    df['IBC'] = pd.to_numeric(df['IBC'])
    df['Semanas'] = pd.to_numeric(df['Semanas'])
    
    df['Periodo'] = df['Desde'].dt.to_period('M')
    
    df_consolidado = df.groupby('Periodo').agg({
        'IBC': 'sum',
        'Semanas': 'max',
        'Desde': 'min',
        'Hasta': 'max',
        'Aportante': lambda x: ' / '.join(list(set(x))[:2])
    }).reset_index()
    
    return df_consolidado.sort_values('Periodo')
