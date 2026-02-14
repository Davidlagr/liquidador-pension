import pdfplumber
import pandas as pd
import re

def limpiar_moneda(valor_str):
    """
    Intenta extraer el primer número que parezca dinero.
    Ej: "$ 1.500.000", "1500000", "1.500.000.00"
    """
    if not isinstance(valor_str, str): return 0.0
    # Quitamos letras y símbolos raros, dejamos solo numeros, puntos y comas
    clean_str = re.sub(r'[^\d\.,]', '', valor_str)
    
    # Si queda algo como 1.500.000, quitamos los puntos y cambiamos coma por punto
    # Heurística: Si hay puntos y comas, el último suele ser el decimal
    if '.' in clean_str and ',' in clean_str:
        clean_str = clean_str.replace('.', '').replace(',', '.')
    elif clean_str.count('.') > 1: # Caso 1.500.000
        clean_str = clean_str.replace('.', '')
    
    try:
        return float(clean_str)
    except:
        return 0.0

def limpiar_semanas(valor_str):
    """
    Limpia semanas buscando formato decimal.
    Ej: "4,29", "4.29", "12,00"
    """
    if not isinstance(valor_str, str): return 0.0
    
    # Buscar patrón de número decimal simple (ej: 4,29 o 12.5)
    match = re.search(r'(\d+[\.,]\d+)', valor_str)
    if match:
        num = match.group(1).replace(',', '.')
        try:
            val = float(num)
            if 0 < val < 55: # Semanas lógicas por mes
                return val
            if 55 <= val < 2000: # Semanas acumuladas o ajustes
                return val
        except:
            pass
            
    # Si falla el regex, intento limpieza bruta
    try:
        clean = valor_str.split()[0].replace(',', '.')
        return float(clean)
    except:
        return 0.0

def procesar_pdf_historia_laboral(archivo_pdf):
    datos = []
    
    # REGEX NUCLEAR:
    # Busca par de fechas (DD/MM/AAAA) separadas por lo que sea (1 a 50 caracteres no numéricos)
    # Esto atrapa:
    # "01/01/2000","30/01/2000"
    # "01/01/2000" \n "30/01/2000"
    # 01/01/2000 ...espacio... 30/01/2000
    regex_fechas = re.compile(r'(\d{2}/\d{2}/\d{4})[^\d]{1,50}(\d{2}/\d{2}/\d{4})')

    full_text = ""
    
    with pdfplumber.open(archivo_pdf) as pdf:
        for page in pdf.pages:
            # Extraemos texto crudo
            text = page.extract_text() or ""
            # Truco: Reemplazar saltos de línea con un caracter especial para no perder la estructura visual,
            # pero permitiendo al regex ver "a través" de ellos.
            full_text += "\n" + text

    # Si no hay texto, es un PDF imagen
    if not full_text.strip():
        return pd.DataFrame()

    # Iterar sobre todas las parejas de fechas encontradas
    for match in regex_fechas.finditer(full_text):
        fecha_desde = match.group(1)
        fecha_hasta = match.group(2)
        
        start_idx = match.start()
        end_idx = match.end()

        # --- ANÁLISIS DEL NOMBRE (HACIA ATRÁS) ---
        # Miramos 250 caracteres antes de la fecha de inicio
        bloque_atras = full_text[max(0, start_idx-250):start_idx]
        
        # Limpieza rápida: quitamos saltos de línea excesivos
        bloque_atras_clean = bloque_atras.replace('\n', ' ')
        
        # Buscamos texto entre comillas
        nombres_potenciales = re.findall(r'"([^"]+)"', bloque_atras_clean)
        
        nombre = "NO IDENTIFICADO"
        if nombres_potenciales:
            # Filtramos candidatos que parezcan IDs o fechas basura
            candidatos = [n for n in nombres_potenciales if len(n) > 3 and not re.match(r'^[\d\.\-,/]+$', n)]
            if candidatos:
                nombre = candidatos[-1] # Tomamos el más cercano a la fecha
        else:
            # Si no hay comillas, tomamos la última "frase" larga
            frases = bloque_atras.split('\n')
            if frases:
                nombre = frases[-1].strip()

        # --- ANÁLISIS DE VALORES (HACIA ADELANTE) ---
        # Miramos 400 caracteres después de la fecha fin
        bloque_adelante = full_text[end_idx:end_idx+400]
        
        # Intentamos separar por la estructura CSV visual (comillas y comas)
        # O simplemente por espacios si el CSV está roto
        tokens = re.split(r'["\n,]+', bloque_adelante)
        tokens = [t.strip() for t in tokens if t.strip()]

        ibc = 0.0
        semanas = 0.0
        
        # Buscamos Salario (IBC) y Semanas en los tokens
        # Asumimos: Salario es un numero grande (> 10000), Semanas es pequeño (< 100)
        # O Salario es el PRIMER número que encontramos
        
        numeros_encontrados = []
        for t in tokens:
            # Limpiamos para ver si es número
            try:
                # Quitamos simbolos monetarios
                val_clean = t.replace('$', '').replace('.', '').replace(',', '.')
                val_float = float(val_clean)
                numeros_encontrados.append(val_float)
            except:
                # Intentar limpiar moneda con decimales
                try: 
                    # Caso 1.200.000,00 -> 1200000.00
                    v = limpiar_moneda(t)
                    if v > 0: numeros_encontrados.append(v)
                except:
                    pass

        # Lógica de asignación basada en magnitud
        if numeros_encontrados:
            # El salario suele ser mayor al salario mínimo (o al menos miles)
            posibles_salarios = [n for n in numeros_encontrados if n > 1000]
            # Las semanas suelen ser decimales pequeños (4.29) o enteros < 55
            posibles_semanas = [n for n in numeros_encontrados if 0 < n < 55]

            # Asignar Salario
            if posibles_salarios:
                ibc = posibles_salarios[0] # El primero suele ser el IBC
            elif numeros_encontrados:
                # Si no hay numero grande, quizás es un salario muy viejo o en formato raro
                # Tomamos el primero como IBC por defecto si es > 0
                if numeros_encontrados[0] > 50: ibc = numeros_encontrados[0]

            # Asignar Semanas (Columna Total es la última)
            if posibles_semanas:
                # Tomamos el último valor pequeño encontrado (suele ser el Total Semanas)
                semanas = posibles_semanas[-1]
            else:
                # Si no encontramos semanas explicitas pequeñas, miramos si hay un valor "total" 
                # a veces Colpensiones pone el total acumulado.
                # Para seguridad, si no hay semanas claras, no cargamos, o ponemos 0
                pass

        if semanas > 0:
            datos.append({
                "Aportante": nombre,
                "Desde": fecha_desde,
                "Hasta": fecha_hasta,
                "IBC": ibc,
                "Semanas": semanas
            })

    # Construcción Final
    if not datos:
        return pd.DataFrame(columns=['Aportante', 'Desde', 'Hasta', 'IBC', 'Semanas'])

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
        'Semanas': 'max',
        'Desde': 'min',
        'Hasta': 'max',
        'Aportante': lambda x: ' / '.join(list(set(str(v) for v in x))[:2])
    }).reset_index()
    
    return df_consolidado.sort_values('Periodo')
