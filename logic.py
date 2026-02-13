import pandas as pd
import numpy as np
from datetime import datetime
from utils import obtener_valor_presente, obtener_semanas_requeridas_mujeres

class LiquidadorPension:
    def __init__(self, historia_laboral, genero, fecha_nacimiento):
        self.df = historia_laboral
        self.genero = genero
        self.fecha_nacimiento = pd.to_datetime(fecha_nacimiento)
        self.fecha_actual = datetime.now()
        
    def calcular_ibl(self, metodo="toda_vida"):
        """
        Calcula el Ingreso Base de Liquidación indexado.
        Metodos: 'toda_vida' o 'ultimos_10'.
        """
        df_calc = self.df.copy()
        
        # Indexar salarios a fecha actual (IPC)
        df_calc['IBC_Indexado'] = df_calc.apply(
            lambda x: obtener_valor_presente(x['IBC'], x['Hasta'], self.fecha_actual), axis=1
        )
        
        if metodo == "ultimos_10":
            # Filtrar últimos 10 años desde la última cotización o fecha actual
            fecha_corte = df_calc['Hasta'].max() - pd.DateOffset(years=10)
            df_calc = df_calc[df_calc['Hasta'] >= fecha_corte]
            
        ibl = df_calc['IBC_Indexado'].mean()
        return ibl

    def calcular_tasa_reemplazo_ley797(self, ibl, semanas_total):
        """
        Fórmula decreciente Ley 797 de 2003:
        r = 65.5 - 0.5 * s
        """
        # Validar salario mínimo vigente (simulado 1.3M)
        smmlv = 1300000 
        promedio_salarios = ibl / smmlv
        
        r = 65.5 - (0.5 * promedio_salarios)
        
        # Ajuste por semanas adicionales a las mínimas (1300)
        # Por cada 50 semanas adicionales, suma 1.5%
        semanas_minimas = 1300 # Ojo: ajustar si es mujer post-2026
        
        # Ajuste genero
        if self.genero == 'Femenino':
            semanas_minimas = obtener_semanas_requeridas_mujeres(self.fecha_actual.year)

        if semanas_total > semanas_minimas:
            semanas_extra = (semanas_total - semanas_minimas) // 50
            r += (semanas_extra * 1.5)
            
        # Límites de ley
        if r < 0: r = 0 # No puede ser negativo logicamente
        if r > 80: r = 80
        
        monto = ibl * (r / 100)
        return monto, r

    def verificar_transicion(self):
        """
        Verifica si cumple requisitos para régimen de transición.
        (Lógica simplificada basada en edad a 2014 o 2003 según corresponda)
        """
        # Aquí iría la lógica de fechas estricta.
        # Por ahora retornamos False para forzar Ley 797 en el ejemplo.
        return False 

    def simulacion_mejora(self, tipo_simulacion, valor_extra=0):
        """
        tipo 1: Dependiente agrega cotización independiente.
        tipo 2: Independiente aumenta su base.
        """
        df_simulado = self.df.copy()
        
        # Proyectar a futuro (simplificado: clonar ultimo año con nuevo valor)
        ultimo_periodo = df_simulado.iloc[-1]
        
        nuevo_ibc = ultimo_periodo['IBC'] + valor_extra
        
        return nuevo_ibc # Retornamos el nuevo IBL proyectado (simplificado)
