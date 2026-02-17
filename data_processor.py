import pdfplumber
import pandas as pd
import re

def extraer_tabla_cruda(archivo_pdf):
    """
    Extrae las líneas del PDF intentando respetar la estructura original de columnas.
    Prioriza el separador CSV '","' para evitar partir los nombres de empresas.
    """
    filas_crudas = []
    
    with pdfplumber.open(archivo_pdf) as pdf:
        full_text = ""
        for page in pdf.pages:
            # Extraer texto preservando estructura
            text = page.extract_text() or ""
            full_text += "\n" + text

    lineas = full_text.split('\n')
    
    # Regex para identificar líneas de datos (deben tener fechas)
    # Acepta DD/MM/AAAA con o sin comillas
    regex_fecha = re.compile(r'\d{2}/\d{2}/\d{4}')
    
    for linea in lineas:
        linea = linea.strip()
        if not linea: continue
        
        # 1. Filtro: La línea debe tener fechas para ser relevante
        if not regex_fecha.search(linea):
            continue
            
        # 2. ESTRATEGIA DE CORTE (SPLIT)
        
        # CASO A: Formato CSV Moderno (Tu archivo 2022-12)
        # Identificamos el patrón de separador ","
        if '","' in linea:
            # Truco: Reemplazamos el separador seguro por un token único
            # para no confundirnos con comas dentro del texto
            token_sep = "||SEP||"
            linea_temp = linea.replace('","', token_sep)
            
            # Limpiamos comillas del inicio y final absoluto de la línea
            linea_temp = linea_temp.strip('"')
            
            # Partimos
            partes = linea_temp.split(token_sep)
            
            # Limpieza final de cada celda
            fila = [p.strip() for p in partes]
            filas_crudas.append(fila)
            
        # CASO B: Formato Antiguo (Texto plano 1980s - sin comillas)
        else:
            # Aquí no podemos hacer split() por espacio porque romperíamos el nombre.
            # Usamos las FECHAS como anclas para dividir la línea en 3 bloques:
            # [NOMBRE] [FECHAS] [VALORES]
            
            fechas = regex_fecha.findall(linea)
            if len(fechas) >= 2:
                f_inicio = fechas[0]
                f_fin = fechas[1]
                
                try:
                    # Partimos el texto usando la primera fecha encontrada
                    # Parte 1: Todo lo que está antes de la fecha (El Nombre)
                    split_1 = linea.split(f_inicio, 1)
                    nombre = split_1[0].strip()
                    resto = split_1[1]
                    
                    # Parte 2: El resto lo partimos por la fecha fin
                    # Nota: resto empieza justo después de f_inicio.
                    # Buscamos f_fin dentro de resto
                    split_2 = resto.split(f_fin, 1)
                    
                    # Lo que queda después de la fecha fin son los números
                    valores_str = split_2[1].strip()
                    
                    # Los valores sí se separan por espacios (IBC Semanas)
                    # Usamos regex para separar por espacios grandes o tabs
                    valores = re.split(r'\s+', valores_str)
                    valores = [v for v in valores if v] # Quitar vacíos
                    
                    # Reconstruimos la fila ordenada:
                    # Col 0: Nombre, Col 1: Desde, Col 2: Hasta, Col 3...: Valores
                    fila = [nombre, f_inicio, f_fin] + valores
                    filas_crudas.append(fila)
                except:
                    # Si falla la lógica inteligente, fallback a split simple
                    filas_crudas.append(linea.split())
            else:
                # Si solo tiene 1 fecha o es muy raro, split simple
                filas_crudas.append(linea.split())

    if not filas_crudas:
        return pd.DataFrame()

    # 3. Normalizar para DataFrame (Rellenar huecos)
    max_cols = max(len(f) for f in filas_crudas)
    header = [f"Columna {i}" for i in range(max_cols)]
    
    datos_norm = [f + [None]*(max_cols-len(f)) for f in filas_crudas]
    
    return pd.DataFrame(datos_norm, columns=header)

def limpiar_y_estandarizar(df_crudo, col_desde, col_hasta, col_ibc, col_semanas):
    """
    Convierte las columnas seleccionadas en datos limpios.
    """
    datos = []
    
    for idx, row in df_crudo.iterrows():
        try:
            raw_desde = str(row[col_desde])
            raw_hasta = str(row[col_hasta])
            raw_ibc = str(row[col_ibc])
            raw_semanas = str(row[col_semanas])
            
            # --- VALIDAR FECHAS ---
            match_d = re.search(r'\d{2}/\d{2}/\d{4}', raw_desde)
            match_h = re.search(r'\d{2}/\d{2}/\d{4}', raw_hasta)
            
            if not match_d or not match_h: continue
            
            desde = pd.to_datetime(match_d.group(0), dayfirst=True, errors='coerce')
            hasta = pd.to_datetime(match_h.group(0), dayfirst=True, errors='coerce')
            
            if pd.isna(desde) or pd.isna(hasta): continue
            
            # --- LIMPIAR NÚMEROS ---
            def clean_num(val):
                if not val or val.lower() == 'none': return 0.0
                # Solo dígitos, puntos, comas
                v = re.sub(r'[^\d\.,]', '', val)
                if not v: return 0.0
                
                # Manejo de decimales vs miles
                if ',' in v and '.' in v: v = v.replace('.', '').replace(',', '.')
                elif v.count('.') > 1: v = v.replace('.', '')
                elif ',' in v:
                    # Si termina en ,XX es decimal (4,29)
                    if len(v.split(',')[-1]) == 2: v = v.replace(',', '.')
                    else: v = v.replace(',', '')
                
                try: return float(v)
                except: return 0.0

            ibc = clean_num(raw_ibc)
            semanas = clean_num(raw_semanas)
            
            # Filtro lógico
            if semanas > 55: semanas = 0
            
            if semanas > 0:
                datos.append({
                    "Desde": desde,
                    "Hasta": hasta,
                    "IBC": ibc,
                    "Semanas": semanas,
                    "Aportante": "Manual"
                })
        except:
            continue
            
    df = pd.DataFrame(datos)
    return df.sort_values('Desde') if not df.empty else df

def aplicar_regla_simultaneidad(df):
    if df.empty: return df
    df['Periodo'] = df['Desde'].dt.to_period('M')
    return df.groupby('Periodo').agg({
        'IBC': 'sum',
        'Semanas': 'max',
        'Desde': 'min',
        'Hasta': 'max'
    }).reset_index().sort_values('Periodo')
