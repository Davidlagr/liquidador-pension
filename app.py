import pandas as pd
import pdfplumber
import re
from datetime import datetime
import openpyxl 
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
import os

# --- CONFIGURACIÓN DINÁMICA 2026 ---
def obtener_smmlv_actual():
    anio_actual = datetime.now().year
    # Valores oficiales Colombia
    historico_smmlv = {
        2024: 1300000,
        2025: 1423500,
        2026: 1750905 
    }
    return historico_smmlv.get(anio_actual, max(historico_smmlv.values()))

ARCHIVO_PDF = "historia_laboral.pdf"
ARCHIVO_INTERMEDIO = "historia_en_excel.xlsx"
ARCHIVO_SALIDA = "Liquidacion_Final_Pensional.xlsx"
ARCHIVO_IPC = "ipc_colombia.csv"

SMMLV_ACTUAL = obtener_smmlv_actual()
MAX_SMMLV = 25 * SMMLV_ACTUAL 

# Índices de Columnas (D=3, G=6, L=11)
IDX_PERIODO = 3 
IDX_SALARIO = 6 
IDX_DIAS = 11   

# --- EXTRACCIÓN DE METADATOS ---
def extraer_metadatos_directos(ruta_pdf):
    datos = {"Nombre": "No detectado", "Fecha Nacimiento": None, "Fecha Afiliacion": None, "Edad": 0}
    if not os.path.exists(ruta_pdf): return datos
    try:
        texto_completo = ""
        with pdfplumber.open(ruta_pdf) as pdf:
            if len(pdf.pages) > 0:
                texto_completo = pdf.pages[0].extract_text()
        
        match_nombre = re.search(r"Nombre:\s*\n?(.+?)(?=\n|Dirección:|Estado)", texto_completo, re.IGNORECASE)
        if match_nombre:
            nombre_sucio = match_nombre.group(1).strip()
            datos["Nombre"] = re.sub(r"[^\w\sÑñ]", "", nombre_sucio).strip().upper()

        regex_fecha = r"(\d{2}/\d{2}/\d{4})"
        match_nac = re.search(r"Nacimiento:.*?" + regex_fecha, texto_completo, re.DOTALL)
        if match_nac:
            datos["Fecha Nacimiento"] = match_nac.group(1)
            try:
                fnac = datetime.strptime(match_nac.group(1), '%d/%m/%Y')
                hoy = datetime.now()
                datos["Edad"] = hoy.year - fnac.year - ((hoy.month, hoy.day) < (fnac.month, fnac.day))
            except: pass

        match_afil = re.search(r"Afiliación:.*?" + regex_fecha, texto_completo, re.DOTALL)
        if match_afil: datos["Fecha Afiliacion"] = match_afil.group(1)
    except: pass
    return datos

# --- PASO 1: CONVERTIR PDF A EXCEL (TABLAS) ---
def actualizar_desde_pdf():
    if not os.path.exists(ARCHIVO_PDF): return
    try:
        todas_las_filas = []
        with pdfplumber.open(ARCHIVO_PDF) as pdf:
            for pagina in pdf.pages:
                tablas = pagina.extract_tables()
                for tabla in tablas:
                    for fila in tabla:
                        fila_limpia = [str(c).replace('\n', ' ') if c else '' for c in fila]
                        todas_las_filas.append(fila_limpia)
        if todas_las_filas:
            df = pd.DataFrame(todas_las_filas)
            df.to_excel(ARCHIVO_INTERMEDIO, index=False, header=False)
    except Exception as e:
        print(f"❌ Error leyendo tablas: {e}")

# --- FUNCIONES DE SOPORTE ---
def cargar_ipc():
    if not os.path.exists(ARCHIVO_IPC):
        # Generar IPC base si no existe para evitar errores en GitHub
        data = [{"anio": 2026, "mes": 1, "indice": 135.0}]
        pd.DataFrame(data).to_csv(ARCHIVO_IPC, index=False)
    return pd.read_csv(ARCHIVO_IPC)

def obtener_ipc_mes(df_ipc, anio, mes):
    fila = df_ipc[(df_ipc['anio'] == anio) & (df_ipc['mes'] == mes)]
    return fila.iloc[0]['indice'] if not fila.empty else None

def limpiar_numero(valor):
    if pd.isna(valor): return 0
    texto = re.sub(r'[^\d]', '', str(valor).split(',')[0].split('.')[0].strip())
    try: return float(texto)
    except: return 0

def extraer_fecha_segura(texto_raw):
    texto = str(texto_raw).strip()
    m = re.search(r'(\d{4})[-/](\d{1,2})|(\d{1,2})/(\d{1,2})/(\d{4})', texto)
    if m:
        if m.group(1): return int(m.group(1)), int(m.group(2))
        else: return int(m.group(5)), int(m.group(4))
    return None, None

def calcular_costo_independiente(ibc):
    ibc = max(min(ibc, MAX_SMMLV), SMMLV_ACTUAL)
    tasa = 0.16 # Tasa estándar pensión
    sol = 0.01 if ibc >= 4*SMMLV_ACTUAL else 0.0
    return ibc * (tasa + sol)

# --- PROYECCIONES AUTOMÁTICAS (SOPORTE GITHUB) ---
def generar_proyecciones_auto(ibl_actual, semanas_actuales, anios_extra=5):
    try:
        semanas_extra = anios_extra * 51.42
        total_semanas_futuro = semanas_actuales + semanas_extra
        
        escenarios = [
            {"tipo": "Conservador (+15%)", "factor": 1.15},
            {"tipo": "Moderado (+30%)", "factor": 1.30},
            {"tipo": "Agresivo (+50%)", "factor": 1.50}
        ]
        
        data_proyeccion = []
        for esc in escenarios:
            nuevo_ibl = ibl_actual * esc["factor"]
            s = nuevo_ibl / SMMLV_ACTUAL
            tasa_base = 65.5 - (0.5 * s)
            puntos = ((total_semanas_futuro - 1300)//50)*1.5 if total_semanas_futuro > 1300 else 0
            tasa_f = max(min(tasa_base + puntos, 80.0), 55.0)
            mesada_p = max(nuevo_ibl * (tasa_f/100), SMMLV_ACTUAL)
            
            costo = calcular_costo_independiente(nuevo_ibl)
            
            data_proyeccion.append({
                "Escenario": esc["tipo"],
                "Años Extra": anios_extra,
                "Nuevo IBL": nuevo_ibl,
                "Mesada Proyectada": mesada_p,
                "Diferencia": mesada_p - (ibl_actual * 0.65), # Estimación diferencia
                "Costo PILA Estimado": costo
            })
        return pd.DataFrame(data_proyeccion)
    except: return None

# --- LIQUIDACIÓN ---
def liquidar():
    actualizar_desde_pdf()
    info_cliente = extraer_metadatos_directos(ARCHIVO_PDF)
    
    try:
        df_raw = pd.read_excel(ARCHIVO_INTERMEDIO, header=None)
        df_ipc = cargar_ipc()
        
        datos = []
        u_anio, u_mes = 0, 0
        
        for i, fila in df_raw.iterrows():
            if len(fila) > IDX_DIAS:
                anio, mes = extraer_fecha_segura(fila[IDX_PERIODO])
                sal, dias = limpiar_numero(fila[IDX_SALARIO]), limpiar_numero(fila[IDX_DIAS])
                if anio and mes and sal > 0:
                    if anio > u_anio or (anio == u_anio and mes > u_mes):
                        u_anio, u_mes = anio, mes
                    
                    ipc_ini = obtener_ipc_mes(df_ipc, anio, mes)
                    if ipc_ini:
                        datos.append({
                            "Fecha": datetime(anio, mes, 1),
                            "Periodo": f"{anio}-{mes:02d}",
                            "Semanas": dias/7,
                            "IBC": sal,
                            "IPC_I": ipc_ini
                        })

        df_res = pd.DataFrame(datos).sort_values("Fecha")
        ipc_f = obtener_ipc_mes(df_ipc, u_anio, u_mes) or df_ipc.iloc[-1]['indice']
        df_res["IBL_Ind"] = df_res["IBC"] * (ipc_f / df_res["IPC_I"])

        total_semanas = df_res["Semanas"].sum()
        ibl_vida = df_res["IBL_Ind"].mean()
        fecha_10y = datetime(u_anio, u_mes, 1).replace(year=u_anio-10)
        ibl_10y = df_res[df_res["Fecha"] >= fecha_10y]["IBL_Ind"].mean()
        ibl_final = max(ibl_vida, ibl_10y)

        s = ibl_final / SMMLV_ACTUAL
        tasa = 65.5 - (0.5 * s)
        pts = ((total_semanas - 1300)//50)*1.5 if total_semanas > 1300 else 0
        tasa_f = max(min(tasa + pts, 80.0), 55.0 if total_semanas >= 1300 else 0)
        mesada_hoy = max(ibl_final * (tasa_f/100), SMMLV_ACTUAL)

        df_proy = generar_proyecciones_auto(ibl_final, total_semanas)

        with pd.ExcelWriter(ARCHIVO_SALIDA, engine='openpyxl') as writer:
            resumen = [
                ("Nombre", info_cliente["Nombre"]),
                ("Semanas Totales", round(total_semanas, 2)),
                ("IBL Seleccionado", ibl_final),
                ("Tasa Reemplazo", f"{tasa_f:.2f}%"),
                ("MESADA ESTIMADA", mesada_hoy),
                ("SMMLV 2026", SMMLV_ACTUAL)
            ]
            pd.DataFrame(resumen, columns=["Concepto", "Valor"]).to_excel(writer, sheet_name="1. Resumen", index=False)
            if df_proy is not None: df_proy.to_excel(writer, sheet_name="2. Proyecciones", index=False)
            df_res[["Periodo", "Semanas", "IBC", "IBL_Ind"]].to_excel(writer, sheet_name="3. Soporte", index=False)

        print(f"✅ Proceso terminado exitosamente.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    liquidar()
