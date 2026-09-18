# Agregar al final de data_processor.py

def extraer_tabla_porvenir(archivo_pdf):
    """
    NUEVA FUNCIONALIDAD: Extrae la historia laboral de Porvenir.
    Devuelve un DataFrame con la misma estructura (6 columnas) que espera la UI
    para que la integración con limpiar_y_estandarizar sea transparente.
    """
    filas_crudas = []
    
    with pdfplumber.open(archivo_pdf) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += "\n" + (page.extract_text() or "")
            
    # Limpiar saltos de línea extraños antes de los separadores '|' típicos de Porvenir
    text_cleaned = re.sub(r'\n\s*\|', ' |', full_text)
    
    # Patrón robusto para detectar: YYYY/MM | Días | $ IBC (con o sin pipes)
    patron = r'(\d{4}/\d{2})\s*(?:\|)?\s*(\d+)\s*(?:\|)?\s*\$\s*([\d\.,]+)'
    matches = re.finditer(patron, text_cleaned)
    
    for m in matches:
        mes_str = m.group(1) # Ej: 2011/11
        dias = int(m.group(2))
        ibc_str = m.group(3).replace('.', '') # Limpiar puntos de miles
        
        anio, mes = mes_str.split('/')
        
        # Estandarizar fechas al formato DD/MM/YYYY que requiere limpiar_y_estandarizar
        desde_str = f"01/{mes}/{anio}"
        
        # Limitar días a 30 (mes pensional) y controlar los cierres de febrero
        dia_fin = dias if 1 <= dias <= 30 else 30
        if mes == '02' and dia_fin > 28:
            dia_fin = 28
            
        hasta_str = f"{dia_fin:02d}/{mes}/{anio}"
        semanas = dias / 7.0
        
        # Formato dummy con 6 columnas para alinear exactamente con 
        # los índices por defecto de los selectbox en app.py:
        # Columna 0 (ID), Columna 1 (Empleador), Col 2 (Desde), Col 3 (Hasta), Col 4 (IBC), Col 5 (Semanas)
        filas_crudas.append(["(Sin ID)", "Fondo Privado", desde_str, hasta_str, ibc_str, str(semanas)])
        
    if not filas_crudas:
        return pd.DataFrame()
        
    # Asignar nombres genéricos idénticos al extractor original
    header = [f"Columna {i}" for i in range(6)]
    return pd.DataFrame(filas_crudas, columns=header)
