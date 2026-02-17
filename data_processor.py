import pdfplumber
import pandas as pd
import re

def extraer_tabla_cruda(archivo_pdf):
    """
    Extrae TODAS las columnas detectadas en formato CSV oculto sin filtrar.
    Retorna un DataFrame genérico con columnas 'Col_0', 'Col_1', etc.
    """
    filas_crudas = []
    
    # Regex para capturar filas que parecen CSV: "algo","algo","algo"...
    # Captura toda la línea que contenga al menos dos pares de comillas
    regex_linea_csv = re.compile(r'("[^"]*"(?:\s*,\s*"[^"]*")+)')
    
    with pdfplumber.open(archivo_pdf) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += "\n" + text

    # Buscar líneas que parecen datos
    matches = regex_linea_csv.findall(full_text)
    
    for m in matches:
        # Dividir la línea por la estructura "," (comilla coma comilla)
        # Usamos un split inteligente para no romper si hay comas dentro del texto
        # 1. Reemplazamos el separador de columnas por un token único
        token = "||SEP||"
        linea_segura = re.sub(r'"\s*,\s*"', token, m)
        # 2. Quitamos comillas de inicio y fin
        linea_segura = linea_segura.strip('"')
        # 3. Dividimos
        columnas = linea_segura.split(token)
        
        # Guardamos la fila limpia de espacios y saltos de línea
        columnas_limpias = [c.replace('\n', ' ').strip() for c in columnas]
        filas_crudas.append(columnas_limpias)

    if not filas_crudas:
        return pd.DataFrame()

    # Normalizar tamaño de filas (rellenar con None si faltan columnas)
    max_cols = max(len(row) for row in filas_crudas)
    header = [f"Columna_{i}" for i in range(max_cols)]
    
    # Crear DF, asegurando que todas las filas tengan el mismo largo
    filas_normalizadas = [row + [None]*(max_cols-len(row)) for row in filas_crudas]
    
    df = pd.DataFrame(filas_normalizadas, columns=header)
    return df

def limpiar_y_estandarizar(df_crudo, col_desde, col_hasta, col_ibc, col_semanas):
    """
    Toma la tabla cruda y las columnas elegidas por el usuario, y genera la tabla limpia.
    """
    datos = []
    
    for idx, row in df_crudo.iterrows():
        try:
            # 1. Obtener valores crudos según selección del usuario
            raw_desde = str(row[col_desde])
            raw_hasta = str(row[col_hasta])
            raw_ibc = str(row[col_ibc])
            raw_semanas = str(row[col_semanas])
            
            # 2. Limpieza FECHAS
            # Busca patrón DD/MM/AAAA
            match_d = re.search(r'\d{2}/\d{2}/\d{4}', raw_desde)
            match_h = re.search(r'\d{2}/\d{2}/\d{4}', raw_hasta)
            
            if not match_d or not match_h: continue # Si no hay fecha, es basura
            
            f_desde = pd.to_datetime(match_d.group(0), dayfirst=True, errors='coerce')
            f_hasta = pd.to_datetime(match_h.group(0), dayfirst=True, errors='coerce')
            
            if pd.isna(f_desde) or pd.isna(f_hasta): continue

            # 3. Limpieza IBC (Moneda)
            # Quitar $, letras, espacios. Dejar solo numeros, puntos y comas.
            clean_ibc = re.sub(r'[^\d\.,]', '', raw_ibc)
            # Resolver ambigüedad punto/coma
            if ',' in clean_ibc and '.' in clean_ibc: 
                clean_ibc = clean_ibc.replace('.', '').replace(',', '.')
            elif clean_ibc.count('.') > 1: # 1.500.000
                clean_ibc = clean_ibc.replace('.', '')
            elif ',' in clean_ibc: # 1,500 o 4,20
                if len(clean_ibc.split(',')[1]) == 2: clean_ibc = clean_ibc.replace(',', '.')
                else: clean_ibc = clean_ibc.replace(',', '')
            
            val_ibc = float(clean_ibc) if clean_ibc else 0.0

            # 4. Limpieza SEMANAS
            clean_sem = re.sub(r'[^\d\.,]', '', raw_semanas)
            # Semanas suele usar coma decimal en Colombia (4,29)
            clean_sem = clean_sem.replace(',', '.')
            
            # A veces pegan "30 4.29". Tomar el último número válido
            # Pero aquí asumimos que el usuario eligió la columna correcta
            val_semanas = float(clean_sem) if clean_sem else 0.0
            
            # Filtro básico anti-error
            if val_semanas > 54: val_semanas = 0 # Probablemente leyó un día o salario
            
            if val_semanas > 0:
                datos.append({
                    "Desde": f_desde,
                    "Hasta": f_hasta,
                    "IBC": val_ibc,
                    "Semanas": val_semanas,
                    "Aportante": "Manual" # No es crítico para el cálculo
                })
                
        except Exception as e:
            continue
            
    df_final = pd.DataFrame(datos)
    return df_final.sort_values('Desde') if not df_final.empty else df_final

def aplicar_regla_simultaneidad(df):
    if df.empty: return df
    df['Periodo'] = df['Desde'].dt.to_period('M')
    df_consolidado = df.groupby('Periodo').agg({
        'IBC': 'sum',
        'Semanas': 'max',
        'Desde': 'min',
        'Hasta': 'max'
    }).reset_index()
    return df_consolidado.sort_values('Periodo')
