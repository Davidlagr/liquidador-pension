import pdfplumber
import pandas as pd
import re

def limpiar_moneda(valor_str):
    """
    Convierte textos financieros a float, manejando formatos mixtos (. o ,).
    Ej: '$ 1.253.156' -> 1253156.0
    Ej: '400.000' -> 400000.0
    """
    if not isinstance(valor_str, str): return 0.0
    clean = valor_str.replace('$', '').strip()
    # Eliminar puntos de miles (asumiendo formato col: 1.000.000)
    clean = clean.replace('.', '')
    # Reemplazar coma decimal
    clean = clean.replace(',', '.')
    try:
        return float(clean)
    except:
        return 0.0

def limpiar_semanas(valor_str):
    """
    Maneja la ambigüedad de decimales en semanas (124.29 vs 4,29).
    """
    if not isinstance(valor_str, str): return 0.0
    clean = valor_str.strip()
    
    # Caso 1: Formato con coma (4,29) -> Estándar Colombia
    if ',' in clean:
        clean = clean.replace('.', '') # Quitar puntos miles si los hubiera
        clean = clean.replace(',', '.') # Coma a punto
    # Caso 2: Formato con punto (124.29) -> Estándar US/PDF antiguo
    # Si tiene punto y son 2 decimales, es decimal.
    # Si tiene punto y son 3 decimales (ej 1.000), es mil (pero raro en semanas)
    
    try:
        return float(clean)
    except:
        return 0.0

def procesar_pdf_historia_laboral(archivo_pdf):
    datos = []
    
    # Expresión regular para capturar la estructura "CSV" oculta en el PDF
    # Captura 8 grupos entre comillas separados por comas
    regex_csv_row = re.compile(r'"(.*?)","(.*?)","(.*?)","(.*?)","(.*?)","(.*?)","(.*?)","(.*?)"', re.DOTALL)

    with pdfplumber.open(archivo_pdf) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue

            # Buscamos todas las coincidencias del patrón CSV
            matches = regex_csv_row.findall(text)
            
            for match in matches:
                # match es una tupla con las 8 columnas detectadas
                # Estructura típica:
                # 0: ID Aportante
                # 1: Nombre Aportante
                # 2: Desde
                # 3: Hasta
                # 4: Salario
                # 5: Semanas (Bloque sucio)
                # 6: Lic/Sim (Bloque sucio o ceros)
                # 7: Total Semanas (Bloque limpio, usualmente)
                
                # VERIFICACIÓN DE FILAS FUSIONADAS
                # A veces una celda contiene "Dato1\n\nDato2". Debemos dividirlo.
                # Tomamos la columna 'Desde' (idx 2) como referencia de cuántas filas reales hay.
                
                col_desde = match[2]
                sub_filas = col_desde.split('\n')
                num_sub_filas = len([x for x in sub_filas if x.strip()]) # Contar filas no vacías
                
                # Preparamos listas de datos separando por saltos de línea
                # Usamos una función lambda segura para hacer split o repetir el valor si no tiene split
                split_safe = lambda txt, n: txt.split('\n') if len(txt.split('\n')) >= n else [txt]*n
                
                # Extraemos todas las columnas expandidas
                ids = split_safe(match[0], num_sub_filas)
                nombres = split_safe(match[1], num_sub_filas)
                desdes = split_safe(match[2], num_sub_filas)
                hastas = split_safe(match[3], num_sub_filas)
                salarios = split_safe(match[4], num_sub_filas)
                
                # Para semanas, preferimos la columna 7 (la última, "Total") que suele estar más limpia
                # Si la 7 está vacía o es 0, miramos la 5
                semanas_raw = split_safe(match[7], num_sub_filas) 
                
                # Iteramos sobre las sub-filas detectadas
                for i in range(num_sub_filas):
                    try:
                        f_desde = desdes[i].strip()
                        f_hasta = hastas[i].strip()
                        
                        # Limpieza de fechas basura
                        if len(f_desde) < 8 or len(f_hasta) < 8: continue
                        
                        # Limpieza de valores numéricos
                        s_raw = semanas_raw[i].strip() if i < len(semanas_raw) else "0"
                        if not s_raw: # Si la columna total falla, intentar con la columna 5
                            col5_split = split_safe(match[5], num_sub_filas)
                            s_raw = col5_split[i].strip() if i < len(col5_split) else "0"
                            
                        val_semanas = limpiar_semanas(s_raw)
                        
                        salario_txt = salarios[i].strip() if i < len(salarios) else "0"
                        val_salario = limpiar_moneda(salario_txt)
                        
                        aportante = nombres[i].strip() if i < len(nombres) else "Desconocido"

                        # Guardar registro
                        datos.append({
                            "Aportante": aportante,
                            "Desde": pd.to_datetime(f_desde, dayfirst=True, errors='coerce'),
                            "Hasta": pd.to_datetime(f_hasta, dayfirst=True, errors='coerce'),
                            "IBC": val_salario,
                            "Semanas": val_semanas
                        })
                    except Exception as e:
                        continue # Si falla una sub-fila, intentar con la siguiente

    df = pd.DataFrame(datos)
    
    # Limpieza final
    if not df.empty:
        df = df.dropna(subset=['Desde', 'Hasta'])
        df = df[df['Semanas'] > 0] # Eliminar filas sin semanas cotizadas
        df = df.sort_values('Desde')
        
    return df

def aplicar_regla_simultaneidad(df):
    """
    Agrupa por mes (Periodo). Suma IBC, Máximo de Semanas.
    """
    if df.empty: return df
    
    df['Periodo'] = df['Desde'].dt.to_period('M')
    
    df_consolidado = df.groupby('Periodo').agg({
        'IBC': 'sum',
        'Semanas': 'max', # Regla: no sumar semanas en el mismo mes
        'Desde': 'min',
        'Hasta': 'max',
        'Aportante': lambda x: ' + '.join(set(x))
    }).reset_index()
    
    return df_consolidado.sort_values('Periodo')
