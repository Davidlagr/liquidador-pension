import pdfplumber
import pandas as pd
import re

def extraer_tabla_cruda(archivo_pdf):
    """
    Extrae TODAS las líneas del PDF que contengan al menos una fecha.
    Divide cada línea en 'tokens' (pedazos) y crea una tabla genérica.
    """
    filas_crudas = []
    
    with pdfplumber.open(archivo_pdf) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += "\n" + text

    lineas = full_text.split('\n')
    
    for linea in lineas:
        # 1. Filtro Mínimo: La línea debe tener al menos una fecha (DD/MM/AAAA)
        # Esto elimina encabezados y pies de página basura.
        if not re.search(r'\d{2}/\d{2}/\d{4}', linea):
            continue
            
        # 2. Estrategia de Corte (Split)
        # Si tiene comillas de CSV (Colpensiones moderno), partimos por ellas
        if '","' in linea:
            partes = linea.strip().strip('"').split('","')
        else:
            # Si es texto plano (Colpensiones antiguo 1980s), partimos por espacios múltiples
            # Usamos regex para partir por 2 o más espacios, o tabulaciones
            partes = re.split(r'\s{2,}|\t|;', linea)
            
            # Si el split falló y dejó todo junto, intentamos split por espacio simple
            if len(partes) < 3:
                partes = linea.split()

        # Limpiamos espacios en blanco de cada celda
        partes_limpias = [p.strip() for p in partes if p.strip()]
        
        if partes_limpias:
            filas_crudas.append(partes_limpias)

    if not filas_crudas:
        return pd.DataFrame()

    # 3. Normalizar: Crear columnas genéricas (Col 0, Col 1, Col 2...)
    max_cols = max(len(fila) for fila in filas_crudas)
    header = [f"Columna {i}" for i in range(max_cols)]
    
    # Rellenar filas cortas con None para que encajen en el DataFrame
    datos_normalizados = [fila + [None]*(max_cols-len(fila)) for fila in filas_crudas]
    
    df = pd.DataFrame(datos_normalizados, columns=header)
    return df

def limpiar_y_estandarizar(df_crudo, col_desde, col_hasta, col_ibc, col_semanas):
    """
    Toma la tabla cruda y las columnas elegidas por el usuario para generar la tabla limpia.
    """
    datos = []
    
    for idx, row in df_crudo.iterrows():
        try:
            # Extraer valores crudos de las columnas seleccionadas
            raw_desde = str(row[col_desde])
            raw_hasta = str(row[col_hasta])
            raw_ibc = str(row[col_ibc])
            raw_semanas = str(row[col_semanas])
            
            # --- LIMPIEZA DE FECHAS ---
            match_d = re.search(r'\d{2}/\d{2}/\d{4}', raw_desde)
            match_h = re.search(r'\d{2}/\d{2}/\d{4}', raw_hasta)
            
            if not match_d or not match_h: continue
            
            desde = pd.to_datetime(match_d.group(0), dayfirst=True, errors='coerce')
            hasta = pd.to_datetime(match_h.group(0), dayfirst=True, errors='coerce')
            
            if pd.isna(desde) or pd.isna(hasta): continue

            # --- LIMPIEZA DE NÚMEROS (IBC y Semanas) ---
            def clean_num(val):
                if not val or val.lower() == 'none': return 0.0
                # Dejar solo digitos, puntos y comas
                v = re.sub(r'[^\d\.,]', '', val)
                if not v: return 0.0
                
                # Heurística Punto/Coma
                if ',' in v and '.' in v: v = v.replace('.', '').replace(',', '.')
                elif v.count('.') > 1: v = v.replace('.', '')
                elif ',' in v:
                    # Si tiene 2 decimales (4,29) es decimal. Si tiene 3 (1,500) es mil.
                    parts = v.split(',')
                    if len(parts) > 1 and len(parts[-1]) == 2: v = v.replace(',', '.')
                    else: v = v.replace(',', '')
                
                try: return float(v)
                except: return 0.0

            ibc = clean_num(raw_ibc)
            semanas = clean_num(raw_semanas)
            
            # Filtro de seguridad: Semanas imposibles (> 55) se vuelven 0
            if semanas > 55: semanas = 0
            
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
