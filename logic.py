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
        
    def calcular_ibl_indexado(self, metodo="toda_vida", fecha_corte_proyeccion=None):
        """
        Calcula el IBL actualizando cada salario con IPC.
        metodo: 'toda_vida' o 'ultimos_10'.
        fecha_corte_proyeccion: Para proyectar IPC a futuro si es necesario.
        """
        df_calc = self.df.copy()
        fecha_final_calculo = fecha_corte_proyeccion if fecha_corte_proyeccion else self.fecha_actual
        
        # Actualización de IPC fila por fila
        def indexar(row):
            fecha_salario = row['Hasta']
            if pd.isna(fecha_salario): return row['IBC']
            
            factor = obtener_ipc_acumulado(fecha_salario, fecha_final_calculo)
            return row['IBC'] * factor

        df_calc['IBC_Indexado'] = df_calc.apply(indexar, axis=1)
        
        if metodo == "ultimos_10":
            # Filtrar los últimos 10 años de cotización real
            fecha_max = df_calc['Hasta'].max()
            fecha_limite = fecha_max - pd.DateOffset(years=10)
            df_calc = df_calc[df_calc['Hasta'] >= fecha_limite]
        
        # Promedio aritmético simple del IBL indexado
        if len(df_calc) == 0: return 0
        ibl = df_calc['IBC_Indexado'].mean()
        return ibl

    def calcular_tasa_reemplazo_797(self, ibl, semanas, anio_pension):
        """
        Fórmula decreciente Ley 797/2003: r = 65.5 - 0.5/s
        Ajuste automático de semanas mínimas para mujeres.
        """
        smmlv_aprox = 1300000 # Debería ser parametrizable
        if ibl == 0: return 0, 0
        
        r = 65.5 - (0.5 * (ibl / smmlv_aprox))
        
        # Determinar piso de semanas según género y año
        semanas_base = 1300
        if self.genero == 'Femenino':
            semanas_base = calcular_semanas_minimas_mujeres(anio_pension)
            
        if semanas > semanas_base:
            # +1.5% por cada 50 semanas adicionales
            paquetes_50 = int((semanas - semanas_base) / 50)
            r += (paquetes_50 * 1.5)
            
        # Topes de ley
        r = max(r, 0)
        r = min(r, 80) # Tope máximo 80%
        
        mesada = ibl * (r / 100)
        return mesada, r, semanas_base

    def verificar_regimen_transicion(self):
        """
        Estudio simple de transición. 
        Requisito: 35 años (mujer) o 40 (hombre) o 15 años cotizados a 1 de abril de 1994.
        """
        # Calcular edad a 1 de abril de 1994
        fecha_limite = pd.Timestamp("1994-04-01")
        edad_en_1994 = (fecha_limite - self.fecha_nacimiento).days / 365.25
        
        # Calcular semanas a 1994
        semanas_a_1994 = self.df[self.df['Hasta'] <= fecha_limite]['Semanas'].sum()
        
        cumple_edad = (self.genero == "Femenino" and edad_en_1994 >= 35) or \
                      (self.genero == "Masculino" and edad_en_1994 >= 40)
        cumple_tiempo = semanas_a_1994 >= 750 # 15 años aprox
        
        return cumple_edad or cumple_tiempo

    def calcular_decreto_758(self, ibl_promedio, semanas_total):
        """
        Régimen de Transición (ISS):
        Si tiene > 1000 semanas -> 75%
        Si tiene > 1250 semanas -> +2% por cada 50 hasta max 90%
        """
        tasa = 0
        if semanas_total >= 1000:
            tasa = 75
            if semanas_total > 1250:
                extras = int((semanas_total - 1250) / 50)
                tasa += (extras * 3) # Dec 758 da incrementos diferentes, simplificado a 3% aqui segun tabla
                
        tasa = min(tasa, 90) # Tope 90% en transición
        return ibl_promedio * (tasa / 100), tasa
