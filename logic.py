import pandas as pd
import numpy as np
from datetime import datetime

class LiquidadorPension:
    def __init__(self, historia_laboral, genero, fecha_nacimiento):
        self.df = historia_laboral
        self.genero = genero
        self.fecha_nacimiento = pd.to_datetime(fecha_nacimiento)
        self.fecha_actual = datetime.now()
        
        # TABLA IPC HISTÓRICO (1967 - 2026)
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

    def obtener_factor_ipc(self, fecha_inicio, fecha_fin):
        anio_inicio = fecha_inicio.year
        anio_fin = fecha_fin.year
        
        min_anio = min(self.ipc_historico.keys())
        max_anio = max(self.ipc_historico.keys())
        
        if anio_inicio < min_anio: anio_inicio = min_anio
        if anio_fin > max_anio: anio_fin = max_anio
        
        factor = 1.0
        for anio in range(anio_inicio, anio_fin):
            if anio in self.ipc_historico:
                factor *= (1 + (self.ipc_historico[anio] / 100.0))
        return factor

    def calcular_ibl_indexado(self, metodo="toda_vida"):
        if self.df.empty: return 0.0, pd.DataFrame()
        
        df_calc = self.df.copy()
        
        if metodo == "ultimos_10":
            fecha_maxima = df_calc['Hasta'].max()
            fecha_corte = fecha_maxima - pd.DateOffset(years=10)
            df_calc = df_calc[df_calc['Hasta'] >= fecha_corte]

        detalles = []
        for _, row in df_calc.iterrows():
            ibc_hist = row['IBC']
            if ibc_hist <= 0: ibc_hist = 0
            
            factor = self.obtener_factor_ipc(row['Hasta'], self.fecha_actual)
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
        """
        limitar_semanas_cotizadas: 
            True = Aplica tope de 1800 semanas (Standard Colpensiones).
            False = Usa todas las semanas disponibles para intentar llegar al 80%.
        """
        smmlv = 1423500 
        if ibl <= 0: return 0, 0, {}
        
        # r = 65.5 - 0.5 * s
        r_inicial = 65.5 - (0.5 * (ibl / smmlv))
        
        # Semanas mínimas
        semanas_minimas = 1300
        if self.genero == 'Femenino':
            if anio_pension < 2026: semanas_minimas = 1300
            elif anio_pension == 2026: semanas_minimas = 1250
            else:
                diff = anio_pension - 2026
                semanas_minimas = max(1000, 1250 - (25 * diff))
        
        # --- LÓGICA DEL TOPE 1800 ---
        semanas_computables = semanas
        
        if limitar_semanas_cotizadas:
            if semanas_computables > 1800:
                semanas_computables = 1800
        
        puntos_extra = 0
        semanas_extra = 0
        
        if semanas_computables > semanas_minimas:
            semanas_extra = semanas_computables - semanas_minimas
            # 1.5% por cada 50 semanas
            puntos_extra = int(semanas_extra / 50) * 1.5
            
        tasa = r_inicial + puntos_extra
        
        # Límites Finales (El 80% es Ley, no se puede saltar, pero podemos llegar a él con más semanas)
        if tasa > 80: tasa = 80
        if tasa < 0: tasa = 0
        
        mesada = ibl * (tasa / 100)
        if mesada < smmlv: mesada = smmlv
        
        # Garantía Pensión Mínima
        if tasa < 0 and mesada == smmlv: tasa = (smmlv/ibl)*100
        
        detalle = {
            "r_inicial": r_inicial,
            "semanas_totales": semanas,
            "semanas_usadas": semanas_computables, # Para mostrar si se recortó
            "semanas_minimas": semanas_minimas,
            "semanas_extra": semanas_extra,
            "puntos_adicionales": puntos_extra,
            "tasa_final": tasa
        }
        return mesada, tasa, detalle
        
    def verificar_regimen_transicion(self):
        corte_1994 = pd.Timestamp("1994-04-01")
        semanas_1994 = self.df[self.df['Hasta'] <= corte_1994]['Semanas'].sum()
        return semanas_1994 >= 750
