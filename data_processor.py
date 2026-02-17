import pdfplumber
import pandas as pd
import re

def extraer_tabla_cruda(archivo_pdf):
    """
    Extrae filas basándose en la presencia de FECHAS, ignorando si tienen comillas o no.
    Esto recupera registros antiguos que pueden estar en texto plano.
    """
    filas_extraidas = []
    
    # Patrón: Busca cualquier línea que tenga al menos una fecha DD/MM/AAAA
    regex_fecha = re.compile(r'\d{2}/\d{2}/\d{4}')

    with pdfplumber.open(archivo_pdf) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += "\n" + text

    # Dividimos por saltos de línea físicos
    lineas = full_text.split('\n')
    
    for linea in lineas:
        # 1. Filtro: La línea debe tener al menos una fecha válida
        matches = regex_fecha.findall(linea)
        if not matches:
            continue
            
        # 2. Estrategia de División
        # Intento A: CSV con comillas (Formato Moderno)
        if '","' in linea:
            # Limpiar comillas extremas y partir
            parts = linea.strip().strip('"').split('","')
            filas_extraidas.append([p.strip() for p in parts])
            
        # Intento B: Texto plano / CSV roto (Formato Antiguo o Sucio)
        else:
            # Usamos espacios grandes o tabulaciones como separador
            # O simplemente el espacio ' ' si no hay comillas
            parts = linea.split()
            # Si la línea tiene muy pocos elementos, quizás está rota, pero la guardamos
            if len(parts) > 3: 
                filas_extraidas.append(parts)

    if not filas_extraidas:
        return pd.DataFrame()

    # Normalizar para crear DataFrame (rellenar columnas faltantes)
    max_cols = max(len(x) for x in filas_extraidas)
    header = [f"Columna {i+1}" for i in range(max_cols)]
    
    # Rellenar filas cortas con None
    datos_norm = [row + [None]*(max_cols-len(row)) for row in filas_extraidas]
    
    return pd.DataFrame(datos_norm, columns=header)

def limpiar_y_estandarizar(df_crudo, nombre_col_desde, nombre_col_hasta, nombre_col_ibc, nombre_col_semanas):
    datos = []
    
    for idx, row in df_crudo.iterrows():
        try:
            # Convertir a string seguro
            raw_desde = str(row[nombre_col_desde]) if row[nombre_col_desde] is not None else ""
            raw_hasta = str(row[nombre_col_hasta]) if row[nombre_col_hasta] is not None else ""
            raw_ibc = str(row[nombre_col_ibc]) if row[nombre_col_ibc] is not None else ""
            raw_semanas = str(row[nombre_col_semanas]) if row[nombre_col_semanas] is not None else ""
            
            # --- 1. Fechas ---
            match_d = re.search(r'\d{2}/\d{2}/\d{4}', raw_desde)
            match_h = re.search(r'\d{2}/\d{2}/\d{4}', raw_hasta)
            
            if not match_d or not match_h: continue
            
            desde = pd.to_datetime(match_d.group(0), dayfirst=True, errors='coerce')
            hasta = pd.to_datetime(match_h.group(0), dayfirst=True, errors='coerce')
            
            if pd.isna(desde) or pd.isna(hasta): continue
            
            # --- 2. Limpieza Numérica Universal ---
            def limpiar_num(val):
                if not val: return 0.0
                # Quitar todo lo que no sea dígito, punto o coma
                v = re.sub(r'[^\d\.,]', '', val)
                if not v: return 0.0
                
                # Heurística Punto/Coma
                if ',' in v and '.' in v: v = v.replace('.', '').replace(',', '.')
                elif v.count('.') > 1: v = v.replace('.', '')
                elif ',' in v:
                    # Si tiene 2 decimales tras la coma, es decimal (4,29)
                    parts = v.split(',')
                    if len(parts[-1]) == 2: v = v.replace(',', '.')
                    else: v = v.replace(',', '')
                
                try: return float(v)
                except: return 0.0

            ibc = limpiar_num(raw_ibc)
            semanas = limpiar_num(raw_semanas)
            
            # Filtros de cordura
            if semanas > 55: semanas = 0 # Probable error de lectura (Días en vez de Semanas)
            
            # Corrección Específica: A veces el IBC de 1980 es muy bajo (ej: 5000 pesos)
            # No lo filtramos por monto mínimo, solo que sea > 0
            
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
