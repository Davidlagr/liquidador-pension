import pdfplumber
import pandas as pd
import re

def extraer_tabla_cruda(archivo_pdf):
    """
    Intenta extraer datos tabulares usando múltiples estrategias.
    Garantiza devolver un DataFrame, aunque sea con datos desordenados, para que el usuario filtre.
    """
    filas_extraidas = []
    
    with pdfplumber.open(archivo_pdf) as pdf:
        full_text = ""
        for page in pdf.pages:
            # Extraer texto preservando el layout físico lo mejor posible
            text = page.extract_text() or ""
            full_text += "\n" + text

    # Separar por líneas físicas
    lineas = full_text.split('\n')
    
    # --- ESTRATEGIA 1: DETECCIÓN POR SEPARADOR CSV ("," o ";") ---
    # Colpensiones suele usar: "Dato","Dato","Dato"
    separador_detectado = None
    if '","' in full_text:
        separador_detectado = '","'
    elif '";"' in full_text:
        separador_detectado = '";"'
        
    for linea in lineas:
        # Filtro Básico: Solo nos interesan líneas que tengan fechas (DD/MM/AAAA)
        # Esto elimina encabezados, pies de página y basura.
        if not re.search(r'\d{2}/\d{2}/\d{4}', linea):
            continue
            
        fila_actual = []
        
        if separador_detectado and separador_detectado in linea:
            # Opción A: Es un CSV oculto
            # Limpiamos comillas de inicio y fin
            linea_limpia = linea.strip().strip('"')
            # Partimos por el separador
            cols = linea_limpia.split(separador_detectado)
            fila_actual = [c.strip() for c in cols]
        else:
            # Opción B: Texto plano (espacios)
            # Usamos las fechas como "Anclas" para dividir la línea
            
            # Buscamos todas las fechas en la línea
            fechas = re.findall(r'\d{2}/\d{2}/\d{4}', linea)
            
            if len(fechas) >= 2:
                # Asumimos estructura: [Texto Nombre] [Fecha1] [Fecha2] [Numeros...]
                fecha_ini = fechas[0]
                fecha_fin = fechas[1]
                
                # Partir la línea usando las fechas
                try:
                    parte1 = linea.split(fecha_ini)[0].strip() # Nombre/ID
                    resto = linea.split(fecha_fin)[-1].strip() # Salarios/Semanas
                    
                    # Tokenizar la parte final (números)
                    tokens_final = resto.split()
                    
                    # Construir fila artificial
                    fila_actual = [parte1, fecha_ini, fecha_fin] + tokens_final
                except:
                    # Si falla el split exacto, usar split por espacios simple
                    fila_actual = linea.split()
            else:
                # Si solo hay 1 fecha o formato raro, split simple
                fila_actual = linea.split()

        if fila_actual:
            filas_extraidas.append(fila_actual)

    # --- GENERACIÓN DEL DATAFRAME ---
    if not filas_extraidas:
        return pd.DataFrame()

    # Normalizar longitud de filas (rellenar con None para que cuadre en un DF)
    max_cols = max(len(f) for f in filas_extraidas)
    
    # Generar nombres de columnas genéricos (Columna 1, Columna 2...)
    header = [f"Columna {i+1}" for i in range(max_cols)]
    
    datos_normalizados = []
    for fila in filas_extraidas:
        # Rellenar faltantes
        fila_rellena = fila + [None] * (max_cols - len(fila))
        datos_normalizados.append(fila_rellena)
        
    df = pd.DataFrame(datos_normalizados, columns=header)
    
    return df

def limpiar_y_estandarizar(df_crudo, nombre_col_desde, nombre_col_hasta, nombre_col_ibc, nombre_col_semanas):
    """
    Convierte las columnas seleccionadas por el usuario en el formato estándar.
    """
    datos = []
    
    for idx, row in df_crudo.iterrows():
        try:
            raw_desde = str(row[nombre_col_desde])
            raw_hasta = str(row[nombre_col_hasta])
            raw_ibc = str(row[nombre_col_ibc])
            raw_semanas = str(row[nombre_col_semanas])
            
            # 1. Validar Fechas (Si no hay fechas, saltar fila)
            match_d = re.search(r'\d{2}/\d{2}/\d{4}', raw_desde)
            match_h = re.search(r'\d{2}/\d{2}/\d{4}', raw_hasta)
            
            if not match_d or not match_h: continue
            
            desde = pd.to_datetime(match_d.group(0), dayfirst=True, errors='coerce')
            hasta = pd.to_datetime(match_h.group(0), dayfirst=True, errors='coerce')
            
            if pd.isna(desde) or pd.isna(hasta): continue
            
            # 2. Limpiar Numeros (IBC y Semanas)
            def clean_num(val):
                if not val or val.lower() == 'none': return 0.0
                # Dejar solo numeros, puntos y comas
                v = re.sub(r'[^\d\.,]', '', val)
                # Estandarizar decimales
                if ',' in v and '.' in v: v = v.replace('.', '').replace(',', '.')
                elif v.count('.') > 1: v = v.replace('.', '')
                elif ',' in v: 
                    # Decidir si coma es mil o decimal (ej: 4,29 vs 1,500)
                    if len(v.split(',')[1]) == 2: v = v.replace(',', '.')
                    else: v = v.replace(',', '')
                try: return float(v)
                except: return 0.0

            ibc = clean_num(raw_ibc)
            semanas = clean_num(raw_semanas)
            
            # Filtro lógico
            if semanas > 55: semanas = 0 # Error lectura
            
            if semanas > 0:
                datos.append({
                    "Desde": desde,
                    "Hasta": hasta,
                    "IBC": ibc,
                    "Semanas": semanas,
                    "Aportante": "Manual"
                })
                
        except Exception:
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
