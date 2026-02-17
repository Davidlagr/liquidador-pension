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
        Calcula el IBL y retorna también el DataFrame con el detalle.
        """
        if self.df.empty: return 0.0, pd.DataFrame()
        
        df_calc = self.df.copy()
        
        # Listas para guardar el detalle
        factores = []
        ibcs_indexados = []
        dias_cotizados = []

        # Recorremos fila por fila
        for index, row in df_calc.iterrows():
            # Filtro de seguridad: Salario > 0
            # NOTA: En 1980 el salario mínimo era bajo ($5000), así que aceptamos cualquier positivo
            if row['IBC'] <= 0:
                factores.append(1.0)
                ibcs_indexados.append(0)
                dias_cotizados.append(0)
                continue
                
            fecha_fin_periodo = row['Hasta']
            
            # --- CÁLCULO DE INDEXACIÓN ---
            # Obtenemos factor desde la fecha del salario hasta hoy
            factor = obtener_ipc_acumulado(fecha_fin_periodo, self.fecha_actual)
            
            valor_indexado = row['IBC'] * factor
            
            # Cálculo de días (aprox) para ponderar si fuera necesario
            dias = (row['Hasta'] - row['Desde']).days + 1
            
            factores.append(factor)
            ibcs_indexados.append(valor_indexado)
            dias_cotizados.append(dias)

        df_calc['Días'] = dias_cotizados
        df_calc['Factor_IPC'] = factores
        df_calc['IBC_Indexado'] = ibcs_indexados
        
        # --- FILTRADO SEGÚN MÉTODO ---
        if metodo == "ultimos_10":
            # Tomamos la fecha de la ÚLTIMA cotización registrada
            fecha_maxima = df_calc['Hasta'].max()
            # Retrocedemos 10 años exactos
            fecha_corte = fecha_maxima - pd.DateOffset(years=10)
            df_calc = df_calc[df_calc['Hasta'] >= fecha_corte]
            
        elif metodo == "toda_vida":
            # NO APLICAMOS NINGÚN FILTRO DE FECHA
            pass
            
        if df_calc.empty: return 0.0, pd.DataFrame()
            
        # Promedio Aritmético del IBL Indexado (Estándar Ley 100/797)
        ibl = df_calc['IBC_Indexado'].mean()
        
        # Retorno: Valor IBL y Tabla Detallada para el usuario
        return ibl, df_calc[['Desde', 'Hasta', 'IBC', 'Factor_IPC', 'IBC_Indexado']]

    def calcular_tasa_reemplazo_797(self, ibl, semanas, anio_pension):
        # Salario mínimo referencial actual (2025/2026)
        smmlv_aprox = 1423500 
        
        if ibl <= 0: return 0, 0, {}
        
        # r = 65.5 - 0.5 * s
        r_inicial = 65.5 - (0.5 * (ibl / smmlv_aprox))
        
        semanas_minimas = 1300
        if self.genero == 'Femenino':
            semanas_minimas = calcular_semanas_minimas_mujeres(anio_pension)
            
        semanas_extra = 0
        puntos_adicionales = 0
        
        if semanas > semanas_minimas:
            semanas_extra = semanas - semanas_minimas
            # 1.5% por cada 50 semanas
            paquetes_50 = int(semanas_extra / 50)
            puntos_adicionales = paquetes_50 * 1.5
            
        r_final = r_inicial + puntos_adicionales
            
        # Topes
        if r_final < 0: r_final = 0 
        if r_final > 80: r_final = 80
        
        mesada = ibl * (r_final / 100)
        if mesada < smmlv_aprox: mesada = smmlv_aprox
            
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
        # Requisito: Tener 15 años (750 semanas) cotizados a 1 de Abril de 1994
        # O tener 35/40 años de edad a esa fecha.
        fecha_1994 = pd.Timestamp("1994-04-01")
        
        # Filtramos semanas anteriores a 1994
        df_trans = self.df[self.df['Hasta'] <= fecha_1994]
        semanas_a_1994 = df_trans['Semanas'].sum()
        
        edad_en_1994 = (fecha_1994 - self.fecha_nacimiento).days / 365.25
        
        condicion_edad = (self.genero == "Femenino" and edad_en_1994 >= 35) or \
                         (self.genero == "Masculino" and edad_en_1994 >= 40)
                         
        condicion_tiempo = semanas_a_1994 >= 750
        
        return condicion_edad or condicion_tiempo

    def calcular_decreto_758(self, ibl, semanas):
        # Tasa de reemplazo básica Dec 758
        if semanas < 500: return 0, 0
        
        tasa = 0.45 
        if semanas >= 1000:
            tasa = 0.75
            # Incremento del 3% por cada 50 semanas adicionales a las 1250
            if semanas > 1250:
                extras = int((semanas - 1250) / 50)
                tasa += (extras * 0.03)
                
        if tasa > 0.90: tasa = 0.90
        
        return ibl * tasa, tasa * 100
