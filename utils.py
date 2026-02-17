import pandas as pd
from datetime import datetime

# TABLA DE IPC HISTÓRICO EMPALMADA (DANE)
# Fuente: Serie histórica DANE (Base 2018 y empalmes anteriores)
# Cubre desde 1967 para liquidar historias laborales antiguas.
IPC_HISTORICO = {
    1967: 8.3, 1968: 6.8, 1969: 7.7, 1970: 6.7, 1971: 11.6, 1972: 13.6,
    1973: 20.3, 1974: 24.3, 1975: 23.3, 1976: 20.5, 1977: 33.7, 1978: 17.8,
    1979: 24.8, 1980: 26.5, 1981: 27.5, 1982: 24.5, 1983: 19.8, 1984: 16.3,
    1985: 24.0, 1986: 18.9, 1987: 23.3, 1988: 28.1, 1989: 25.8, 1990: 29.1,
    1991: 30.4, 1992: 27.0, 1993: 22.6, 1994: 22.6, 1995: 19.5, 1996: 21.6,
    1997: 17.7, 1998: 16.7, 1999: 9.2, 2000: 8.8, 2001: 7.7, 2002: 7.0,
    2003: 6.5, 2004: 5.5, 2005: 4.9, 2006: 4.5, 2007: 5.7, 2008: 7.7,
    2009: 2.0, 2010: 3.2, 2011: 3.7, 2012: 2.4, 2013: 1.9, 2014: 3.7,
    2015: 6.8, 2016: 5.8, 2017: 4.1, 2018: 3.2, 2019: 3.8, 2020: 1.6,
    2021: 5.6, 2022: 13.1, 2023: 9.3, 2024: 5.0, 2025: 4.0, 2026: 3.5
}

def obtener_ipc_acumulado(fecha_inicio, fecha_fin):
    """
    Calcula el factor multiplicador de IPC desde fecha_inicio hasta fecha_fin.
    """
    anio_inicio = fecha_inicio.year
    anio_fin = fecha_fin.year
    
    # Validar rangos
    min_anio_tabla = min(IPC_HISTORICO.keys())
    max_anio_tabla = max(IPC_HISTORICO.keys())
    
    # Si la cotización es anterior a 1967, arrancamos desde 1967
    if anio_inicio < min_anio_tabla: 
        anio_inicio = min_anio_tabla
    
    if anio_fin > max_anio_tabla: 
        anio_fin = max_anio_tabla

    ipc_acumulado = 1.0
    
    # Algoritmo de acumulación (Productoria)
    # Factor = (1+IPC_1) * (1+IPC_2) ...
    # Se toma hasta el año anterior a la fecha de corte (norma general de indexación anual)
    
    for anio in range(anio_inicio, anio_fin): 
        if anio in IPC_HISTORICO:
             ipc_acumulado *= (1 + (IPC_HISTORICO[anio] / 100.0))
             
    return ipc_acumulado

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
