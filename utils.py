import pandas as pd
from datetime import datetime

# IPC Anual Histórico Colombia (Serie completa DANE empalmada)
# Fuente: DANE / Banco de la República
IPC_HISTORICO = {
    1967: 50.0, 1968: 50.0, 1969: 50.0, # Aproximados para años muy viejos
    1970: 50.0, 1971: 12.0, 1972: 13.0, 1973: 23.0, 1974: 25.0, 1975: 17.0,
    1976: 25.0, 1977: 29.0, 1978: 19.0, 1979: 29.0, 1980: 25.85, 1981: 26.36,
    1982: 24.03, 1983: 16.64, 1984: 18.28, 1985: 22.45, 1986: 20.95, 1987: 24.02,
    1988: 28.12, 1989: 26.12, 1990: 32.36, 1991: 26.82, 1992: 25.13, 1993: 22.60,
    1994: 22.60, 1995: 19.46, 1996: 21.63, 1997: 17.68, 1998: 16.70, 1999: 9.23,
    2000: 8.75, 2001: 7.65, 2002: 6.99, 2003: 6.49, 2004: 5.50, 2005: 4.85,
    2006: 4.48, 2007: 5.69, 2008: 7.67, 2009: 2.00, 2010: 3.17, 2011: 3.73,
    2012: 2.44, 2013: 1.94, 2014: 3.66, 2015: 6.77, 2016: 5.75, 2017: 4.09,
    2018: 3.18, 2019: 3.80, 2020: 1.61, 2021: 5.62, 2022: 13.12, 2023: 9.28,
    2024: 5.00, 2025: 4.00, 2026: 3.50
}

def obtener_ipc_acumulado(fecha_inicio, fecha_fin):
    anio_inicio = fecha_inicio.year
    anio_fin = fecha_fin.year
    
    # Si la fecha es anterior a nuestro registro, usamos el más antiguo
    min_anio = min(IPC_HISTORICO.keys())
    if anio_inicio < min_anio:
        anio_inicio = min_anio
        
    ipc_base = 100.0
    valor_indice_inicial = 100.0
    valor_indice_final = 100.0
    
    found_inicio = False
    
    # Recorrido simple de acumulación
    for anio in range(min_anio, anio_fin + 1):
        if anio in IPC_HISTORICO:
            ipc_base = ipc_base * (1 + (IPC_HISTORICO[anio] / 100.0))
            
            # Capturamos el índice en el año de inicio de la cotización
            if anio == anio_inicio:
                valor_indice_inicial = ipc_base
                found_inicio = True
            
            # Capturamos el índice en el año de liquidación
            if anio == anio_fin:
                valor_indice_final = ipc_base
    
    if not found_inicio: return 1.0
    
    try:
        factor = valor_indice_final / valor_indice_inicial
    except:
        factor = 1.0
        
    return factor

def calcular_semanas_minimas_mujeres(anio_proyeccion):
    if anio_proyeccion < 2026:
        return 1300
    elif anio_proyeccion == 2026:
        return 1250
    else:
        diferencia_anios = anio_proyeccion - 2026
        reduccion = 25 * (diferencia_anios + 1)
        semanas = 1250 - (25 * diferencia_anios)
        return max(semanas, 1000)
