import pdfplumber
import pandas as pd
import re

def limpiar_moneda(valor_str):
    """
    Convierte textos como '$ 1.500.000', '1.500.000', '$200.000.' a float.
    Maneja el punto como separador de miles.
    """
    if not valor_str: return 0.0
    # Quitar símbolos y puntos finales extraños que a veces trae el PDF
    clean = valor_str.replace('$', '').replace(' ', '')
    if clean.endswith('.'): clean = clean[:-1]
    
    # Eliminar puntos de miles
    clean = clean.replace('.', '')
    # Reemplazar coma decimal por punto (si existe)
    clean = clean.replace(',', '.')
    
    try:
        return float(clean)
    except:
        return 0.0

def limpiar_semanas(valor_str):
    """Convierte '4,29', '4.29' o '12,86' a float"""
    if not valor_str: return 0.0
    clean = valor_str.replace(',', '.')
    try:
        return float(clean)
    except:
        return 0.0

def procesar_pdf_historia_laboral(archivo_pdf):
    datos = []
    
    # Expresión regular para fechas formato DD/MM/AAAA
    regex_fecha = r'(\d{2}/\d{2}/\d{4})'
    
    with pdfplumber.open(archivo_pdf) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            
            lines = text.split('\n')
            for line in lines:
                # 1. Buscar todas las fechas en la línea
                fechas = re.findall(regex_fecha, line)
                
                # Una línea válida de historia laboral debe tener al menos 2 fechas (Desde, Hasta)
                if len(fechas) >= 2:
                    fecha_desde = fechas[0]
                    fecha_hasta = fechas[1]
                    
                    try:
                        # --- ESTRATEGIA DE ANCLAJE ---
                        # Dividimos la línea usando las fechas como separadores
                        
                        # Todo lo que está ANTES de la primera fecha es ID + Nombre
                        parte_izquierda = line.split(fecha_desde)[0].strip()
                        
                        # Todo lo que está DESPUÉS de la segunda fecha son los valores (Salario, Semanas, etc.)
                        # Usamos split por la segunda fecha y tomamos lo que sigue
                        parte_derecha = line.split(fecha_hasta)[-1].strip()
                        
                        # --- PROCESAR NOMBRE (IZQUIERDA) ---
                        # Generalmente es: "ID NOMBRE"
                        # Intentamos separar el ID del nombre
                        partes_nombre = parte_izquierda.split()
                        if len(partes_nombre) > 1 and partes_nombre[0].isdigit():
                            aportante = " ".join(partes_nombre[1:]) # Todo menos el primero
                        else:
                            aportante = parte_izquierda # Si no hay ID claro, tomar todo
                            
                        # --- PROCESAR VALORES (DERECHA) ---
                        # La parte derecha suele verse así: "$ 1.500.000 4,29 0,00 0,00 4,29"
                        # A veces los números están pegados o separados por espacios múltiples
                        tokens = parte_derecha.split()
                        
                        ibc = 0.0
                        semanas = 0.0
                        
                        if tokens:
                            # El primer token suele ser el salario (Columna [5])
                            # A veces el PDF pega el signo peso: $213.000
                            raw_ibc = tokens[0]
                            ibc = limpiar_moneda(raw_ibc)
                            
                            # El último token suele ser el total de semanas (Columna [9])
                            # Ojo: A veces hay columnas vacías intermedias
                            raw_semanas = tokens[-1]
                            semanas = limpiar_semanas(raw_semanas)
                            
                            # VALIDACIÓN EXTRA:
                            # Si semanas > 55 (imposible por mes/periodo), algo salió mal, quizás tomó otro número.
                            # Si semanas es 0, intentar buscar el penúltimo token
                            if semanas > 54 or semanas == 0:
                                # Intento de rescate: buscar el valor numérico más razonable < 54
                                for t in reversed(tokens):
                                    v = limpiar_semanas(t)
                                    if 0 < v < 54:
                                        semanas = v
                                        break

                        datos.append({
                            "Aportante": aportante,
                            "Desde": pd.to_datetime(fecha_desde, dayfirst=True),
                            "Hasta": pd.to_datetime(fecha_hasta, dayfirst=True),
                            "IBC": ibc,
                            "Semanas": semanas,
                            "Origen": line # Guardamos la linea original por si acaso (debug)
                        })
                        
                    except Exception as e:
                        # Si falla una línea, la saltamos pero no rompemos todo
                        continue

    df = pd.DataFrame(datos)
    
    # Limpieza final de datos nulos o fechas invalidas
    if not df.empty:
        df = df.dropna(subset=['Desde', 'Hasta'])
        df = df[df['Semanas'] > 0] # Filtrar lineas que no sumaron semanas (info basura)
        
    return df

def aplicar_regla_simultaneidad(df):
    """
    Maneja periodos simultáneos agrupando por AÑO-MES.
    Regla: Sumar IBC, Maximizar Semanas (no sumar semanas).
    """
    if df.empty: return df
    
    # Crear columna Periodo para agrupar (YYYY-MM)
    df['Periodo'] = df['Desde'].dt.to_period('M')
    
    # Agrupar
    df_consolidado = df.groupby('Periodo').agg({
        'IBC': 'sum',           # Se suman los salarios de todos los empleadores ese mes
        'Semanas': 'max',       # Se toma el reporte de semanas más alto (usualmente 4.29)
        'Desde': 'min',         # Inicio del periodo
        'Hasta': 'max',         # Fin del periodo
        'Aportante': lambda x: ' + '.join(set(x)) # Mostrar nombres unicos
    }).reset_index()
    
    return df_consolidado.sort_values('Periodo')
