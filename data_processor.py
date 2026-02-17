import pdfplumber
import pandas as pd
import re

def limpiar_numero_flexible(valor_str):
    """
    Intenta convertir cualquier string con números a float.
    Maneja: "1.500.000", "1,500,000.00", "4,29", "30"
    """
    if not isinstance(valor_str, str): return None
    
    # 1. Limpieza inicial: quitar símbolos de moneda y espacios
    clean = re.sub(r'[^\d\.,]', '', valor_str)
    if not clean: return None

    # 2. Heurística para puntos y comas
    # Si tiene coma y punto (1.500,00 o 1,500.00), asumimos formato moneda
    if ',' in clean and '.' in clean:
        if clean.find(',') > clean.find('.'): # Caso 1.500,00 (Europa/Col)
            clean = clean.replace('.', '').replace(',', '.')
        else: # Caso 1,500.00 (USA)
            clean = clean.replace(',', '')
    elif ',' in clean: # Solo comas (4,29 o 1,500)
        # Si parece decimal pequeño (4,29), reemplazar por punto
        # Si parece mil (1,500), quitar
        if len(clean.split(',')[1]) == 2: # probable decimal 4,29
            clean = clean.replace(',', '.')
        else:
            clean = clean.replace(',', '')
    elif clean.count('.') > 1: # Caso 1.500.000 (Puntos de miles)
        clean = clean.replace('.', '')
    
    try:
        return float(clean)
    except:
        return None

def procesar_pdf_historia_laboral(archivo_pdf):
    datos = []
    
    # REGEX: Busca par de fechas. Ignora lo que hay en medio.
    regex_fechas = re.compile(r'(\d{2}/\d{2}/\d{4})[^\d]{1,100}(\d{2}/\d{2}/\d{4})')

    full_text = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += "\n" + text

    if not full_text.strip(): return pd.DataFrame()

    for match in regex_fechas.finditer(full_text):
        fecha_desde = match.group(1)
        fecha_hasta = match.group(2)
        end_idx = match.end()
        start_idx = match.start()

        # --- 1. EXTRAER NOMBRE (HACIA ATRÁS) ---
        bloque_atras = full_text[max(0, start_idx-250):start_idx]
        nombres_potenciales = re.findall(r'"([^"]+)"', bloque_atras)
        
        nombre = "NO IDENTIFICADO"
        # Filtramos candidatos que no sean fechas ni vacíos
        candidatos = [n.strip() for n in nombres_potenciales if len(n) > 4 and not re.search(r'\d{2}/\d{2}/\d{4}', n)]
        if candidatos:
            nombre = candidatos[-1] # El más cercano a la fecha
        else:
            # Fallback: tomar la línea anterior
            lines = bloque_atras.split('\n')
            if lines: nombre = lines[-1].strip()

        # --- 2. EXTRAER VALORES (HACIA ADELANTE) ---
        # Miramos lo que hay después de la segunda fecha
        bloque_adelante = full_text[end_idx:end_idx+300]
        
        # Tokenizamos rompiendo por cualquier cosa que no sea un caracter numérico/moneda
        # Esto separa "$1.500.000" de "4,29"
        raw_tokens = re.split(r'["\n\s]+', bloque_adelante)
        
        numeros = []
        for t in raw_tokens:
            val = limpiar_numero_flexible(t)
            if val is not None:
                numeros.append(val)
        
        ibc = 0.0
        semanas = 0.0

        if numeros:
            # ESTRATEGIA DE MAGNITUDES
            
            # A. ENCONTRAR IBC (Salario)
            # El salario suele ser el primer número GRANDE (> 5000) o el primero > 0 si es antiguo
            posibles_salarios = [n for n in numeros if n > 5000] # Filtro de ruido
            if posibles_salarios:
                ibc = posibles_salarios[0]
            elif numeros:
                # Si no hay números grandes (salarios viejos), tomamos el primero > 0
                if numeros[0] > 0: ibc = numeros[0]

            # B. ENCONTRAR SEMANAS
            # Las semanas suelen ser números PEQUEÑOS (0 a 53)
            # Colpensiones pone: Días (30) ... Semanas (4.29)
            # Debemos priorizar el decimal (4.29) sobre el entero (30) y tomar el último.
            
            posibles_semanas = [n for n in numeros if 0 < n <= 54] # Filtro rango semanas
            
            weeks_candidate = 0.0
            
            # Prioridad 1: Buscar decimales exactos típicos de semanas (x.14, x.29, x.57, x.71, x.86)
            # Esto diferencia 4.29 (semanas) de 30.0 (días)
            decimales = [n for n in posibles_semanas if n % 1 != 0]
            
            if decimales:
                weeks_candidate = decimales[-1] # Tomamos el último decimal encontrado (columna final)
            elif posibles_semanas:
                # Si solo hay enteros (ej: 4, 12, 50), tomamos el último
                # Pero cuidado: si el último es 30, podría ser Días.
                ultimo = posibles_semanas[-1]
                if ultimo == 30 and len(posibles_semanas) > 1:
                     # Si es 30, intentamos ver si hay otro candidato anterior que sea semanas
                     weeks_candidate = ultimo # Riesgoso, pero si dice 30 semanas es válido
                else:
                    weeks_candidate = ultimo
            
            semanas = weeks_candidate

        if semanas > 0:
            datos.append({
                "Aportante": nombre,
                "Desde": fecha_desde,
                "Hasta": fecha_hasta,
                "IBC": ibc,
                "Semanas": semanas
            })

    # Crear DF y convertir fechas
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
    
    df_consolidado = df.groupby('Periodo').agg({
        'IBC': 'sum',
        'Semanas': 'max', # REGLA: Tiempos simultáneos no suman semanas
        'Desde': 'min',
        'Hasta': 'max',
        'Aportante': lambda x: ' + '.join(list(set(str(v) for v in x))[:2])
    }).reset_index()
    
    return df_consolidado.sort_values('Periodo')
