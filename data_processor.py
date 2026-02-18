import pdfplumber
import pandas as pd
import re

def extraer_tabla_cruda(archivo_pdf):
    # (Código del turno 17 que alinea columnas de 1980 con las de 2022)
    # ... Si necesitas que te lo repita dímelo, pero es el mismo anterior.
    filas = []
    with pdfplumber.open(archivo_pdf) as pdf:
        txt = ""
        for p in pdf.pages: txt += (p.extract_text() or "") + "\n"
    
    for linea in txt.split('\n'):
        if not re.search(r'\d{2}/\d{2}/\d{4}', linea): continue
        
        if '","' in linea: # Moderno
            parts = linea.replace('","', '|||').strip('"').split('|||')
            filas.append([p.strip() for p in parts])
        else: # Antiguo
            fechas = re.findall(r'\d{2}/\d{2}/\d{4}', linea)
            if len(fechas)>=2:
                try:
                    p1 = linea.split(fechas[0], 1)[0].strip()
                    p2 = linea.split(fechas[1], 1)[1].strip().split()
                    # INYECTAR COLUMNA VACÍA AL INICIO PARA ALINEAR CON MODERNO (ID)
                    filas.append(["(Sin ID)", p1, fechas[0], fechas[1]] + p2)
                except: filas.append(linea.split())
            else: filas.append(linea.split())
            
    if not filas: return pd.DataFrame()
    mx = max(len(f) for f in filas)
    return pd.DataFrame([f + [None]*(mx-len(f)) for f in filas], columns=[f"Col {i}" for i in range(mx)])

def limpiar_y_estandarizar(df, cd, ch, ci, cs):
    # (El mismo código manual del turno 17)
    datos = []
    for _, r in df.iterrows():
        try:
            d = pd.to_datetime(re.search(r'\d{2}/\d{2}/\d{4}', str(r[cd])).group(0), dayfirst=True, errors='coerce')
            h = pd.to_datetime(re.search(r'\d{2}/\d{2}/\d{4}', str(r[ch])).group(0), dayfirst=True, errors='coerce')
            if pd.isna(d) or pd.isna(h): continue
            
            def cl(v):
                v = re.sub(r'[^\d\.,]', '', str(v))
                if ',' in v and '.' in v: v = v.replace('.','').replace(',','.')
                elif v.count('.')>1: v = v.replace('.','')
                elif ',' in v: v = v.replace(',','.') if len(v.split(',')[-1])==2 else v.replace(',','')
                try: return float(v)
                except: return 0.0
            
            i, s = cl(r[ci]), cl(r[cs])
            if s > 55: s = 0
            if s > 0: datos.append({"Desde":d, "Hasta":h, "IBC":i, "Semanas":s})
        except: continue
    return pd.DataFrame(datos).sort_values('Desde')

def aplicar_regla_simultaneidad(df):
    if df.empty: return df
    df['Periodo'] = df['Desde'].dt.to_period('M')
    return df.groupby('Periodo').agg({'IBC':'sum', 'Semanas':'max', 'Desde':'min', 'Hasta':'max'}).reset_index().sort_values('Periodo')
