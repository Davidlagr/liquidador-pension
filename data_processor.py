import pdfplumber
import pandas as pd
import re

def extraer_tabla_cruda(archivo_pdf):
    """
    Extrae tabla cruda alineando columnas antiguas y nuevas.
    """
    filas_crudas = []
    
    with pdfplumber.open(archivo_pdf) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += "\n" + text

    lineas = full_text.split('\n')
    regex_fecha = re.compile(r'\d{2}/\d{2}/\d{4}')
    
    for linea in lineas:
        linea = linea.strip()
        if not linea: continue
        if not regex_fecha.search(linea): continue
            
        # A. Formato Moderno
        if '","' in linea:
            token_sep = "||SEP||"
            linea_temp = linea.replace('","', token_sep).strip('"')
            partes = [p.strip() for p in linea_temp.split(token_sep)]
            filas_crudas.append(partes)
            
        # B. Formato Antiguo (Sin comillas)
        else:
            fechas = regex_fecha.findall(linea)
            if len(fechas) >= 2:
                try:
                    # Usamos fechas como separadores
                    split_1 = linea.split(fechas[0], 1)
                    p1 = split_1[0].strip() # Nombre
                    
                    split_2 = split_1[1].split(fechas[1], 1)
                    p3 = split_2[1].strip() # Valores
                    
                    valores = re.split(r'\s+', p3)
                    valores = [v for v in valores if v]
                    
                    # Alineamos agregando columna dummy al inicio
                    filas_crudas.append(["(Sin ID)", p1, fechas[0], fechas[1]] + valores)
                except:
                    filas_crudas.append(linea.split())
            else:
                filas_crudas.append(linea.split())

    if not filas_crudas: return pd.DataFrame()

    max_cols = max(len(f) for f in filas_crudas)
    header = [f"Columna {i}" for i in range(max_cols)]
    datos_norm = [f + [None]*(max_cols-len(f)) for f in filas_crudas]
    
    return pd.DataFrame(datos_norm, columns=header)

def limpiar_y_estandarizar(df_crudo, col_desde, col_hasta, col_ibc, col_semanas):
    """
    Limpieza inteligente: Si faltan semanas, las calcula por fechas.
    """
    datos = []
    
    for idx, row in df_crudo.iterrows():
        try:
            raw_desde = str(row[col_desde])
            raw_hasta = str(row[col_hasta])
            raw_ibc = str(row[col_ibc])
            raw_semanas = str(row[col_semanas])
            
            # --- 1. FECHAS ---
            match_d = re.search(r'\d{2}/\d{2}/\d{4}', raw_desde)
            match_h = re.search(r'\d{2}/\d{2}/\d{4}', raw_hasta)
            
            if not match_d or not match_h: continue
            
            desde = pd.to_datetime(match_d.group(0), dayfirst=True, errors='coerce')
            hasta = pd.to_datetime(match_h.group(0), dayfirst=True, errors='coerce')
            
            if pd.isna(desde) or pd.isna(hasta): continue
            
            # --- 2. VALORES ---
            def clean_num(val):
                if not val or val.lower() == 'none': return 0.0
                v = re.sub(r'[^\d\.,]', '', val)
                if not v: return 0.0
                if ',' in v and '.' in v: v = v.replace('.','').replace(',','.')
                elif v.count('.') > 1: v = v.replace('.','')
                elif ',' in v: 
                    if len(v.split(',')[-1])==2: v = v.replace(',','.')
                    else: v = v.replace(',','')
                try: return float(v)
                except: return 0.0

            ibc = clean_num(raw_ibc)
            semanas_leidas = clean_num(raw_semanas)
            
            # --- 3. LÓGICA DE RESCATE (LA SOLUCIÓN) ---
            semanas_final = semanas_leidas
            
            # Si el PDF dice 0 semanas o está vacío, calculamos matemáticamente
            # También si dice > 55 (probablemente leyó días o dinero por error)
            recalcular = False
            
            if semanas_leidas <= 0.1: recalcular = True
            elif semanas_leidas > 55: recalcular = True # Error común: leyó "30" días como semanas o un código
            
            if recalcular:
                dias_calculados = (hasta - desde).days + 1
                # Validación: Un periodo no puede ser negativo ni excesivo (ej: 50 años)
                if 0 < dias_calculados < 12000:
                    semanas_final = dias_calculados / 7
                else:
                    semanas_final = 0
            
            # --- 4. GUARDAR ---
            # Aceptamos el registro si logramos obtener semanas válidas (leídas o calculadas)
            if semanas_final > 0:
                datos.append({
                    "Desde": desde,
                    "Hasta": hasta,
                    "IBC": ibc,
                    "Semanas": semanas_final,
                    "Aportante": "Manual"
                })

        except Exception as e:
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
