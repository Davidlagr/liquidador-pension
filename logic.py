import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from utils import calcular_semanas_minimas_mujeres

class LiquidadorPension:
    def __init__(self, historia_laboral, genero, fecha_nacimiento):
        self.df = historia_laboral
        self.genero = genero
        self.fecha_nacimiento = pd.to_datetime(fecha_nacimiento)
        self.fecha_actual = datetime.now()
        
        # IPC HISTÓRICO (1967 - 2026)
        self.ipc_historico = {
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

    def obtener_factor_ipc(self, fecha_inicio, fecha_corte):
        """Calcula inflación acumulada hasta una fecha de corte específica"""
        anio_inicio = fecha_inicio.year
        anio_fin = fecha_corte.year
        
        min_anio = min(self.ipc_historico.keys())
        max_anio = max(self.ipc_historico.keys())
        
        if anio_inicio < min_anio: anio_inicio = min_anio
        if anio_fin > max_anio: anio_fin = max_anio
        
        factor = 1.0
        # Se indexa hasta el año anterior a la fecha de corte
        for anio in range(anio_inicio, anio_fin):
            if anio in self.ipc_historico:
                factor *= (1 + (self.ipc_historico[anio] / 100.0))
        return factor

    def determinar_fechas_clave(self):
        """
        Determina: Fecha Cumplimiento Edad, Fecha Cumplimiento Semanas,
        Fecha Estatus y Fecha de Indexación (Corte).
        """
        # 1. FECHA EDAD
        req_edad = 62 if self.genero == "Masculino" else 57
        fecha_cumple_edad = self.fecha_nacimiento + relativedelta(years=req_edad)
        
        # 2. FECHA SEMANAS (Iterar hasta encontrar la semana 1300/req)
        # Requisito base
        req_sem = 1300
        if self.genero == "Femenino":
            # Usamos el año actual para definir el requisito, o el año de cumplimiento edad si es menor
            req_sem = calcular_semanas_minimas_mujeres(datetime.now().year)
            
        df_sort = self.df.sort_values('Hasta')
        acumulado = 0
        fecha_cumple_semanas = None
        
        for _, row in df_sort.iterrows():
            acumulado += row['Semanas']
            if acumulado >= req_sem:
                fecha_cumple_semanas = row['Hasta']
                break
        
        # 3. ESTATUS JURÍDICO
        tiene_estatus = (fecha_cumple_semanas is not None) and (acumulado >= req_sem)
        fecha_estatus = None
        
        if tiene_estatus:
            # El estatus se adquiere cuando se cumplen AMBOS requisitos (la fecha mayor)
            fecha_estatus = max(fecha_cumple_edad, fecha_cumple_semanas)
            
            # Si cumplió semanas antes de la edad, el estatus es la fecha de cumpleaños
            # Si cumplió edad pero le faltaban semanas, el estatus es la fecha de la semana 1300
        
        # 4. FECHA DE CORTE (INDEXACIÓN) Y REGLAS
        # Regla 1: Si no tiene estatus -> A la fecha de hoy (año de estudio)
        # Regla 2: Si tiene estatus:
        #    A. Si NO hay cotizaciones posteriores al estatus -> Fecha Estatus
        #    B. Si HAY cotizaciones posteriores -> Fecha Última Cotización
        
        ultima_cotizacion = df_sort['Hasta'].max()
        razon_corte = ""
        fecha_corte = datetime.now() # Default
        
        if not tiene_estatus:
            fecha_corte = datetime.now()
            razon_corte = "Año de Estudio (No acredita estatus)"
        else:
            # Verificar si hay cotizaciones posteriores a la fecha de estatus
            # Damos un margen de 30 días para no contar el mismo mes
            cotizaciones_posteriores = df_sort[df_sort['Hasta'] > (fecha_estatus + timedelta(days=30))]
            
            if cotizaciones_posteriores.empty:
                fecha_corte = fecha_estatus
                razon_corte = "Fecha de Estatus (Sin semanas posteriores)"
            else:
                fecha_corte = ultima_cotizacion
                razon_corte = "Última Cotización (Con semanas posteriores al estatus)"

        # Fecha Efectividad (Teórica: día siguiente al corte)
        fecha_efectividad = fecha_corte + timedelta(days=1)

        return {
            "fecha_cumple_edad": fecha_cumple_edad,
            "fecha_cumple_semanas": fecha_cumple_semanas,
            "fecha_estatus": fecha_estatus,
            "tiene_estatus": tiene_estatus,
            "fecha_corte": fecha_corte,
            "razon_corte": razon_corte,
            "fecha_efectividad": fecha_efectividad,
            "ultima_cotizacion": ultima_cotizacion
        }

    def calcular_ibl_indexado(self, fecha_corte_personalizada=None, metodo="toda_vida"):
        if self.df.empty: return 0.0, pd.DataFrame()
        
        # Si no mandan fecha, usamos hoy, pero idealmente se debe mandar la calculada
        f_corte = fecha_corte_personalizada if fecha_corte_personalizada else self.fecha_actual
        
        df_calc = self.df.copy()
        
        # Filtro Últimos 10 años (Desde la fecha de corte hacia atrás)
        if metodo == "ultimos_10":
            # La norma dice últimos 10 años cotizados. 
            # Tomamos la fecha fin del último registro válido y restamos 10 años.
            fecha_max_cot = df_calc['Hasta'].max()
            fecha_inicio_10 = fecha_max_cot - relativedelta(years=10)
            df_calc = df_calc[df_calc['Hasta'] >= fecha_inicio_10]

        detalles = []
        for _, row in df_calc.iterrows():
            ibc_hist = row['IBC']
            if ibc_hist <= 0: ibc_hist = 0
            
            # Indexamos hasta la FECHA DE CORTE determinada por las reglas
            factor = self.obtener_factor_ipc(row['Hasta'], f_corte)
            ibc_act = ibc_hist * factor
            
            detalles.append({
                'Desde': row['Desde'],
                'Hasta': row['Hasta'],
                'IBC_Historico': ibc_hist,
                'Factor_IPC': factor,
                'IBC_Actualizado': ibc_act,
                'Semanas': row['Semanas']
            })
            
        df_detalles = pd.DataFrame(detalles)
        if df_detalles.empty: return 0.0, pd.DataFrame()
        
        ibl = df_detalles['IBC_Actualizado'].mean()
        return ibl, df_detalles

    def calcular_tasa_reemplazo_797(self, ibl, semanas, anio_pension, limitar_semanas_cotizadas=True):
        smmlv = 1423500 
        if ibl <= 0: return 0, 0, {}
        
        r_inicial = 65.5 - (0.5 * (ibl / smmlv))
        
        semanas_minimas = 1300
        if self.genero == 'Femenino':
            if anio_pension < 2026: semanas_minimas = 1300
            elif anio_pension == 2026: semanas_minimas = 1250
            else:
                diff = anio_pension - 2026
                semanas_minimas = max(1000, 1250 - (25 * diff))
        
        semanas_computables = semanas
        if limitar_semanas_cotizadas and semanas_computables > 1800:
            semanas_computables = 1800
        
        puntos_extra = 0
        semanas_extra = 0
        if semanas_computables > semanas_minimas:
            semanas_extra = semanas_computables - semanas_minimas
            puntos_extra = int(semanas_extra / 50) * 1.5
            
        tasa = r_inicial + puntos_extra
        if tasa > 80: tasa = 80
        if tasa < 0: tasa = 0
        
        mesada = ibl * (tasa / 100)
        if mesada < smmlv: mesada = smmlv
        if tasa < 0 and mesada == smmlv: tasa = (smmlv/ibl)*100
        
        detalle = {
            "semanas_usadas": semanas_computables,
            "tasa_final": tasa
        }
        return mesada, tasa, detalle
