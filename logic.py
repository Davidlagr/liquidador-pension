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
        Calcula el IBL y retorna también el DataFrame con el detalle de la indexación.
        """
        if self.df.empty: return 0.0, pd.DataFrame()
        
        df_calc = self.df.copy()
        
        # Listas para guardar el detalle del cálculo paso a paso
        factores = []
        ibcs_indexados = []
        dias_cotizados = []

        # Cálculo fila por fila para guardar el factor usado
        for index, row in df_calc.iterrows():
            if row['IBC'] <= 0:
                factores.append(0)
                ibcs_indexados.append(0)
                dias_cotizados.append(0)
                continue
                
            fecha_fin_periodo = row['Hasta']
            dias = (row['Hasta'] - row['Desde']).days + 1
            
            # Factor IPC
            factor = obtener_ipc_acumulado(fecha_fin_periodo, self.fecha_actual)
            valor_indexado = row['IBC'] * factor
            
            factores.append(factor)
            ibcs_indexados.append(valor_indexado)
            dias_cotizados.append(dias)

        df_calc['Días'] = dias_cotizados
        df_calc['Factor_IPC'] = factores
        df_calc['IBC_Indexado'] = ibcs_indexados
        
        # Filtros según método
        if metodo == "ultimos_10":
            fecha_maxima = df_calc['Hasta'].max()
            fecha_corte = fecha_maxima - pd.DateOffset(years=10)
            df_calc = df_calc[df_calc['Hasta'] >= fecha_corte]
            
        if df_calc.empty: return 0.0, pd.DataFrame()
            
        # IBL = Promedio de los salarios indexados
        ibl = df_calc['IBC_Indexado'].mean()
        
        # Retornamos el valor Y la tabla de detalle para mostrarla en el frontend
        return ibl, df_calc[['Desde', 'Hasta', 'IBC', 'Factor_IPC', 'IBC_Indexado']]

    def calcular_tasa_reemplazo_797(self, ibl, semanas, anio_pension):
        # Parametros
        smmlv_aprox = 1300000 
        
        if ibl <= 0: return 0, 0, 1300
        
        # Formula r = 65.5 - 0.5 * s
        r_inicial = 65.5 - (0.5 * (ibl / smmlv_aprox))
        
        # Semanas mínimas mujeres (Sentencia C-197)
        semanas_minimas = 1300
        if self.genero == 'Femenino':
            semanas_minimas = calcular_semanas_minimas_mujeres(anio_pension)
            
        # Bonificación por semanas extra
        semanas_extra = 0
        puntos_adicionales = 0
        if semanas > semanas_minimas:
            semanas_extra = semanas - semanas_minimas
            paquetes_50 = int(semanas_extra / 50)
            puntos_adicionales = paquetes_50 * 1.5
            
        r_final = r_inicial + puntos_adicionales
            
        # Topes Ley 797
        if r_final < 0: r_final = 0 
        if r_final > 80: r_final = 80
        
        mesada = ibl * (r_final / 100)
        
        if mesada < smmlv_aprox:
            mesada = smmlv_aprox
            
        # Retornamos diccionario con todo el detalle para la explicación gráfica
        detalle = {
            "r_inicial": r_inicial,
            "semanas_minimas": semanas_minimas,
            "semanas_extra": semanas_extra,
            "puntos_adicionales": puntos_adicionales,
            "tasa_final": r_final,
            "mesada": mesada
        }
            
        return mesada, r_final, detalle

    def verificar_regimen_transicion(self):
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
        if semanas < 500: return 0, 0 
        tasa = 0.45 
        if semanas >= 1000:
            tasa = 0.75
            if semanas > 1250:
                extras = int((semanas - 1250) / 50)
                tasa += (extras * 0.03)
        if tasa > 0.90: tasa = 0.90
        return ibl * tasa, tasa * 100
