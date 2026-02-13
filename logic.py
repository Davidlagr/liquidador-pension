import pandas as pd
import numpy as np
from datetime import datetime, date
from utils import obtener_ipc_acumulado, calcular_semanas_minimas_mujeres

class LiquidadorPension:
    def __init__(self, historia_laboral, genero, fecha_nacimiento):
        self.df = historia_laboral
        self.genero = genero
        self.fecha_nacimiento = pd.to_datetime(fecha_nacimiento)
        self.fecha_actual = datetime.now()
        
    def calcular_ibl_indexado(self, metodo="toda_vida"):
        """
        Calcula el IBL indexado.
        """
        if self.df.empty: return 0.0
        
        df_calc = self.df.copy()
        
        # Función interna para indexar fila por fila
        def indexar(row):
            if row['IBC'] <= 0: return 0
            fecha_fin_periodo = row['Hasta']
            # Traer a valor presente (al mes pasado para ser exactos, aquí usamos fecha actual simplificada)
            factor = obtener_ipc_acumulado(fecha_fin_periodo, self.fecha_actual)
            return row['IBC'] * factor

        df_calc['IBC_Indexado'] = df_calc.apply(indexar, axis=1)
        
        # Filtros según método
        if metodo == "ultimos_10":
            fecha_maxima = df_calc['Hasta'].max()
            fecha_corte = fecha_maxima - pd.DateOffset(years=10)
            df_calc = df_calc[df_calc['Hasta'] >= fecha_corte]
            
        if df_calc.empty: return 0.0
            
        # El IBL es el promedio de los salarios indexados
        # OJO: Es promedio ponderado por días o promedio simple mensual? 
        # Ley 100 art 21: Promedio de los salarios sobre los cuales ha cotizado.
        # Dado que ya consolidamos por mes en data_processor, es un promedio simple de los meses.
        ibl = df_calc['IBC_Indexado'].mean()
        
        return ibl

    def calcular_tasa_reemplazo_797(self, ibl, semanas, anio_pension):
        # Parametros
        smmlv_aprox = 1300000 
        
        if ibl <= 0: return 0, 0, 1300
        
        # Formula r = 65.5 - 0.5 * s
        r = 65.5 - (0.5 * (ibl / smmlv_aprox))
        
        # Semanas mínimas mujeres (Sentencia C-197)
        semanas_minimas = 1300
        if self.genero == 'Femenino':
            semanas_minimas = calcular_semanas_minimas_mujeres(anio_pension)
            
        # Bonificación por semanas extra
        if semanas > semanas_minimas:
            # Por cada 50 semanas adicionales a las mínimas
            semanas_extra = semanas - semanas_minimas
            paquetes_50 = int(semanas_extra / 50)
            r += (paquetes_50 * 1.5)
            
        # Topes Ley 797
        if r < 0: r = 0 # Matemáticamente posible con salarios muy altos, pero la ley tiene pisos
        if r > 80: r = 80
        
        mesada = ibl * (r / 100)
        
        # Garantía de pensión mínima (un salario mínimo)
        if mesada < smmlv_aprox:
            mesada = smmlv_aprox
            
        return mesada, r, semanas_minimas

    def verificar_regimen_transicion(self):
        # Lógica simplificada Transición
        fecha_limite = pd.Timestamp("1994-04-01")
        if self.fecha_nacimiento:
            edad_en_1994 = (fecha_limite - self.fecha_nacimiento).days / 365.25
            semanas_a_1994 = self.df[self.df['Hasta'] <= fecha_limite]['Semanas'].sum()
            
            condicion_edad = (self.genero == "Femenino" and edad_en_1994 >= 35) or \
                             (self.genero == "Masculino" and edad_en_1994 >= 40)
            condicion_tiempo = semanas_a_1994 >= 750
            
            return condicion_edad or condicion_tiempo
        return False

    def calcular_decreto_758(self, ibl, semanas):
        # Acuerdo 049 de 1990
        if semanas < 500: return 0, 0 # Requisito mínimo básico de 500 en 20 años anteriores o 1000 total
        
        tasa = 0.45 # Base arranca diferente en 758 pero simplifiquemos a la tabla visual
        # Si tiene > 1000 semanas y cumple requisitos:
        if semanas >= 1000:
            tasa = 0.75
            if semanas > 1250:
                extras = int((semanas - 1250) / 50)
                tasa += (extras * 0.03)
                
        if tasa > 0.90: tasa = 0.90
        
        return ibl * tasa, tasa * 100
