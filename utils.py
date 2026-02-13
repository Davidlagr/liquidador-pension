import pandas as pd
from datetime import datetime

# IPC Histórico de Colombia (Ejemplo simplificado, se debe mantener actualizado)
# En producción, esto podría venir de una API o un CSV externo.
IPC_HISTORICO = {
    1990: 32.36, 1991: 26.82, 1992: 25.13, 1993: 22.60, 1994: 22.60,
    # ... (Se deben llenar todos los años intermedios) ...
    2022: 13.12, 2023: 9.28, 2024: 5.0, 2025: 3.5, 2026: 3.0 # Proyecciones
}

def obtener_valor_presente(valor_historico, fecha_origen, fecha_destino):
    """
    Actualiza un valor monetario usando el IPC acumulado entre dos fechas.
    Fórmula simplificada: Valor * (IPC_Final / IPC_Inicial) o multiplicatoria de (1+IPC)
    NOTA: Para pensiones en Colombia se usa la fórmula:
    VH = Vh * (IPC Final / IPC Inicial)
    Donde IPC Final es el del mes anterior a la liquidación.
    """
    # Esta es una implementación base. Se requiere una tabla mensual de IPC 
    # del DANE para precisión exacta de liquidación pensional.
    # Por ahora usaremos un factor dummy de actualización para el ejemplo.
    
    # Lógica simplificada: Aumentar un % anual promedio si no hay tabla exacta cargada
    dias = (fecha_destino - fecha_origen).days
    anios = dias / 365.25
    factor = (1 + 0.04) ** anios # 4% promedio anual (Placeholder)
    return valor_historico * factor

def obtener_semanas_requeridas_mujeres(anio_estudio):
    """
    Retorna las semanas requeridas para mujeres según sentencia C-197/23
    Reducción gradual a partir de 2026.
    """
    if anio_estudio < 2026:
        return 1300
    elif anio_estudio == 2026:
        return 1250 # Ejemplo de reducción
    # ... lógica de reducción hasta 1000 ...
    else:
        return 1000 # Mínimo estable
