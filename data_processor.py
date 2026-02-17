import pdfplumber
import pandas as pd
import re

def extraer_tabla_cruda(archivo_pdf):
    """
    Extrae líneas del PDF y las alinea para que los registros antiguos (sin ID separado)
    coincidan en columnas con los registros modernos (con ID separado).
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
        
        # Filtro: Debe tener fechas
        if not regex_fecha.search(linea): continue
            
        # --- ESTRATEGIA DE EXTRACCIÓN Y ALINEACIÓN ---
        
        # CASO A: Formato Moderno (CSV con comillas) -> Tiene ID en Col 0
        if '","' in linea:
            token_sep = "||SEP||"
            linea_temp = linea.replace('","', token_sep).strip('"')
            partes = [p.strip() for p in linea_temp.split(token_sep)]
            filas_crudas.append(partes)
            
        # CASO B: Formato Antiguo (Sin comillas) -> A veces le falta el ID separado
        else:
            fechas = regex_fecha.findall(linea)
            if len(fechas) >= 2:
                f_inicio = fechas[0]
                f_fin = fechas[1]
                
                try:
                    # Partimos la línea usando las fechas como ancla
                    split_1 = linea.split(f_inicio, 1)
                    texto_previo = split_1[0].strip() # Nombre (y quizás ID pegado)
                    
                    resto = split_1[1]
                    split_2 = resto.split(f_fin, 1)
                    valores_str = split_2[1].strip()
                    
                    valores = re.split(r'\s+', valores_str)
                    valores = [v for v in valores if v]
                    
                    # --- TRUCO DE ALINEACIÓN ---
                    # El formato CSV moderno suele ser: [ID, Nombre, Fecha1, Fecha2...]
                    # El formato antiguo extraído es:   [Nombre, Fecha1, Fecha2...]
                    # Para que las columnas coincidan en la selección manual,
                    # insertamos una columna vacía al inicio del antiguo para simular el ID.
                    
                    fila_alineada = ["(Sin ID Separado)", texto_previo, f_inicio, f_fin] + valores
                    filas_crudas.append(fila_alineada)
                    
                except:
                    # Si falla, agregamos tal cual (usuario tendrá que revisar)
                    filas_crudas.append(linea.split())
            else:
                filas_crudas.append(linea.split())

    if not filas_crudas:
        return pd.DataFrame()

    # Normalizar longitud
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
            
            # NOTA: Aceptamos salarios bajos (>0) para incluir cotizaciones de 1980
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
