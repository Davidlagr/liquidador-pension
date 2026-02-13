import pandas as pd
from datetime import datetime

# IPC Anual de Colombia (Simplificado para el ejercicio - Debe ser mensual para precisión total)
# Fuente: DANE (Base 2018 o empalmes históricos)
IPC_HISTORICO = {
    1990: 32.36, 1991: 26.82, 1992: 25.13, 1993: 22.60, 1994: 22.60, 1995: 19.46,
    1996: 21.63, 1997: 17.68, 1998: 16.70, 1999: 9.23, 2000: 8.75, 2001: 7.65,
    2002: 6.99, 2003: 6.49, 2004: 5.50, 2005: 4.85, 2006: 4.48, 2007: 5.69,
    2008: 7.67, 2009: 2.00, 2010: 3.17, 2011: 3.73, 2012: 2.44, 2013: 1.94,
    2014: 3.66, 2015: 6.77, 2016: 5.75, 2017: 4.09, 2018: 3.18, 2019: 3.80,
    2020: 1.61, 2021: 5.62, 2022: 13.12, 2023: 9.28, 2024: 5.00, 2025: 4.00, # Proyectados
    2026: 3.50
}

def obtener_ipc_acumulado(fecha_inicio, fecha_fin):
    """
    Calcula el factor de actualización basado en IPC entre dos fechas (años).
    Formula: (IPC Final / IPC Inicial)
    """
    anio_inicio = fecha_inicio.year
    anio_fin = fecha_fin.year
    
    # Si la fecha es muy antigua, usar el IPC más antiguo que tengamos
    if anio_inicio < min(IPC_HISTORICO.keys()):
        anio_inicio = min(IPC_HISTORICO.keys())
    
    # Construir el índice (simplificado usando IPC final del año anterior al corte)
    # En liquidación real se usa la tabla mensual de IPC del DANE.
    # Aquí simulamos el crecimiento acumulado.
    
    ipc_base = 100
    for anio in range(min(IPC_HISTORICO.keys()), anio_fin + 1):
        if anio in IPC_HISTORICO:
            ipc_base = ipc_base * (1 + (IPC_HISTORICO[anio] / 100))
            if anio == anio_inicio:
                valor_indice_inicial = ipc_base
            if anio == anio_fin:
                valor_indice_final = ipc_base
    
    try:
        factor = valor_indice_final / valor_indice_inicial
    except:
        factor = 1.0
        
    return factor

def calcular_semanas_minimas_mujeres(anio_proyeccion):
    """
    Retorna semanas mínimas para mujeres según Sentencia C-197 de 2023.
    1300 hasta 2025.
    1250 en 2026.
    Disminuye 25 semanas cada año hasta llegar a 1000 en 2036.
    """
    if anio_proyeccion < 2026:
        return 1300
    elif anio_proyeccion == 2026:
        return 1250
    else:
        diferencia_anios = anio_proyeccion - 2026
        reduccion = 25 * (diferencia_anios + 1) # +1 porque 2027 baja a 1225, etc.
        semanas = 1250 - (25 * diferencia_anios)
        return max(semanas, 1000) # El piso es 1000
