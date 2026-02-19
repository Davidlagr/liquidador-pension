import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, datetime, timedelta  # <--- AQUÍ FALTABA TIMEDELTA
from io import BytesIO
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from data_processor import extraer_tabla_cruda, limpiar_y_estandarizar, aplicar_regla_simultaneidad
from logic import LiquidadorPension

st.set_page_config(page_title="Liquidador Pensional Pro", layout="wide", page_icon="⚖️")

# --- CSS ---
st.markdown("""
    <style>
    .info-box { background-color: #e8f6f3; padding: 15px; border-radius: 8px; border-left: 5px solid #1abc9c; }
    .status-ok { color: #27ae60; font-weight: bold; }
    .status-alert { color: #d35400; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("⚖️ Liquidador Pensional: Análisis Técnico & Jurídico")

# --- ESTADO ---
if 'df_crudo' not in st.session_state: st.session_state.df_crudo = None
if 'df_final' not in st.session_state: st.session_state.df_final = None

# ==========================================
# GENERADOR DE REPORTE WORD (AVANZADO)
# ==========================================
def generar_reporte_completo(perfil, fechas, liq_data, proyeccion=None):
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(10)

    # 1. TÍTULO
    tit = doc.add_heading('DICTAMEN TÉCNICO PENSIONAL', 0)
    tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Fecha de Emisión: {datetime.now().strftime('%d/%m/%Y')}")
    doc.add_paragraph("_" * 70)

    # 2. INFORMACIÓN DEL AFILIADO Y ESTATUS
    doc.add_heading('1. INFORMACIÓN JURÍDICA Y ESTATUS', level=1)
    
    # Tabla de Datos Clave
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    
    # Llenado de filas
    datos = [
        ("Afiliado", perfil['nombre']),
        ("Fecha Nacimiento", perfil['fecha_nac']),
        ("Fecha Cumplimiento Edad", fechas['fecha_cumple_edad'].strftime('%d/%m/%Y')),
        ("Fecha Cumplimiento Semanas", fechas['fecha_cumple_semanas'].strftime('%d/%m/%Y') if fechas['fecha_cumple_semanas'] else "No cumplido"),
        ("FECHA DE ESTATUS", fechas['fecha_estatus'].strftime('%d/%m/%Y') if fechas['tiene_estatus'] else "NO ADQUIRIDO"),
        ("Última Cotización", fechas['ultima_cotizacion'].strftime('%d/%m/%Y')),
        ("FECHA CORTE (INDEXACIÓN)", fechas['fecha_corte'].strftime('%d/%m/%Y')),
        ("FECHA EFECTIVIDAD", fechas['fecha_efectividad'].strftime('%d/%m/%Y')),
        ("Razón Jurídica Corte", fechas['razon_corte'])
    ]
    
    for k, v in datos:
        r = table.add_row().cells
        r[0].text = k
        r[0].paragraphs[0].runs[0].bold = True
        r[1].text = str(v)

    # 3. RESULTADOS DE LIQUIDACIÓN
    doc.add_paragraph()
    doc.add_heading('2. LIQUIDACIÓN DE LA PRESTACIÓN', level=1)
    
    t2 = doc.add_table(rows=1, cols=2)
    t2.style = 'Light Shading Accent 1'
    
    res_data = [
        ("Semanas Totales", f"{liq_data['semanas']:,.2f}"),
        ("IBL Aplicado", f"${liq_data['ibl']:,.0f} ({liq_data['origen_ibl']})"),
        ("Tasa de Reemplazo", f"{liq_data['tasa']:.2f}%"),
        ("MESADA PENSIONAL", f"${liq_data['mesada']:,.0f}")
    ]
    for k, v in res_data:
        r = t2.add_row().cells
        r[0].text = k
        r[1].text = v

    # 4. GRÁFICAS (Matplotlib -> Word)
    doc.add_heading('3. ANÁLISIS GRÁFICO', level=1)
    
    # Gráfico 1: Comparativo IBL
    fig1, ax1 = plt.subplots(figsize=(6, 3))
    ax1.bar(["Últimos 10", "Toda Vida"], [liq_data['ibl_10'], liq_data['ibl_vida']], color=['#3498db', '#2ecc71'])
    ax1.set_title("Comparativo Ingreso Base de Liquidación (IBL)")
    ax1.yaxis.set_major_formatter('${x:,.0f}')
    
    memfile1 = BytesIO()
    fig1.savefig(memfile1)
    doc.add_picture(memfile1, width=Inches(5))
    memfile1.close()
    
    # 5. DETALLE TÉCNICO (SOPORTES COMPLETOS)
    doc.add_page_break()
    doc.add_heading('ANEXO: SOPORTE TÉCNICO DE IBL', level=1)
    doc.add_paragraph(f"Detalle del cálculo: {liq_data['origen_ibl']}")
    doc.add_paragraph(f"Fecha de Indexación usada: {fechas['fecha_corte'].strftime('%d/%m/%Y')}")

    # Convertir DataFrame a Tabla Word
    df_soporte = liq_data['df_soporte']
    
    if not df_soporte.empty:
        # Tabla encabezados
        t3 = doc.add_table(rows=1, cols=5)
        t3.style = 'Table Grid'
        hdr = t3.rows[0].cells
        hdr[0].text = 'Desde'
        hdr[1].text = 'Hasta'
        hdr[2].text = 'IBC Histórico'
        hdr[3].text = 'Factor IPC'
        hdr[4].text = 'IBC Actualizado'
        
        # Filas
        for _, row in df_soporte.iterrows():
            rc = t3.add_row().cells
            rc[0].text = row['Desde'].strftime('%d/%m/%Y')
            rc[1].text = row['Hasta'].strftime('%d/%m/%Y')
            rc[2].text = f"${row['IBC_Historico']:,.0f}"
            rc[3].text = f"{row['Factor_IPC']:.4f}"
            rc[4].text = f"${row['IBC_Actualizado']:,.0f}"

    # 6. PROYECCIÓN (SI EXISTE)
    if proyeccion:
        doc.add_page_break()
        doc.add_heading('4. PROYECCIÓN DE MEJORA PENSIONAL', level=1)
        doc.add_paragraph(f"Estrategia: {proyeccion['estrategia']}")
        
        t4 = doc.add_table(rows=1, cols=2)
        t4.style = 'Medium Grid 1 Accent 2'
        
        proy_dat = [
            ("Inversión Total", f"${proyeccion['inversion']:,.0f}"),
            ("Nueva Mesada", f"${proyeccion['mesada_fut']:,.0f}"),
            ("Incremento Mensual", f"${proyeccion['delta']:,.0f}"),
            ("Tiempo Recuperación", f"{proyeccion['roi']:.1f} Años")
        ]
        for k, v in proy_dat:
            r = t4.add_row().cells
            r[0].text = k
            r[1].text = v
            
        # Gráfico ROI
        fig2, ax2 = plt.subplots(figsize=(6, 3))
        ax2.bar(["Hoy", "Futuro"], [liq_data['mesada'], proyeccion['mesada_fut']], color='#e67e22')
        ax2.set_title("Proyección de Mesada")
        
        memfile2 = BytesIO()
        fig2.savefig(memfile2)
        doc.add_picture(memfile2, width=Inches(5))
        memfile2.close()

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# ==========================================
# INTERFAZ (SIDEBAR)
# ==========================================
with st.sidebar:
    st.header("👤 Datos")
    nombre = st.text_input("Nombre", "Usuario")
    genero = st.radio("Género", ["Masculino", "Femenino"])
    
    # Rango de fechas corregido (1900 - Hoy)
    fecha_nac = st.date_input("Nacimiento", value=date(1975, 1, 1), min_value=date(1900,1,1), max_value=datetime.now().date())
    
    st.divider()
    aplicar_tope = st.checkbox("Tope 1800 Semanas", value=True)
    if st.button("🔄 Reiniciar"):
        st.session_state.df_crudo = None
        st.session_state.df_final = None
        st.rerun()

# ==========================================
# LÓGICA PRINCIPAL
# ==========================================
if st.session_state.df_final is None:
    st.info("📂 Carga el PDF de Historia Laboral")
    uploaded_file = st.file_uploader("Archivo PDF", type="pdf")

    if uploaded_file:
        if st.session_state.df_crudo is None:
            st.session_state.df_crudo = extraer_tabla_cruda(uploaded_file)
        
        df = st.session_state.df_crudo
        if df is not None and not df.empty:
            st.dataframe(df.head(3))
            cols = df.columns.tolist()
            c1, c2, c3, c4 = st.columns(4)
            cd = c1.selectbox("Desde", cols, index=2 if len(cols)>2 else 0)
            ch = c2.selectbox("Hasta", cols, index=3 if len(cols)>3 else 0)
            ci = c3.selectbox("IBC", cols, index=4 if len(cols)>4 else 0)
            cs = c4.selectbox("Semanas", cols, index=len(cols)-1)
            
            if st.button("Procesar"):
                clean = limpiar_y_estandarizar(df, cd, ch, ci, cs)
                if not clean.empty:
                    st.session_state.df_final = aplicar_regla_simultaneidad(clean)
                    st.rerun()
                else: st.error("Error columnas")

else:
    # --- CÁLCULOS TÉCNICOS ---
    df = st.session_state.df_final
    liq = LiquidadorPension(df, genero, fecha_nac)
    
    # 1. Determinar Fechas Clave (Estatus, Corte, etc.)
    fechas_clave = liq.determinar_fechas_clave()
    
    # 2. Calcular IBL usando la FECHA DE CORTE JURÍDICA
    ibl_10, det_10 = liq.calcular_ibl_indexado(fechas_clave['fecha_corte'], "ultimos_10")
    ibl_vida, det_vida = liq.calcular_ibl_indexado(fechas_clave['fecha_corte'], "toda_vida")
    ibl_def = max(ibl_10, ibl_vida)
    origen_ibl = "Últimos 10 Años" if ibl_10 >= ibl_vida else "Toda la Vida"
    
    # 3. Liquidar
    total_sem = df['Semanas'].sum()
    mesada, tasa, info = liq.calcular_tasa_reemplazo_797(
        ibl_def, total_sem, datetime.now().year, aplicar_tope
    )

    # --- PESTAÑAS VISUALES ---
    tab1, tab2 = st.tabs(["📊 DIAGNÓSTICO JURÍDICO", "💰 PROYECCIÓN"])
    
    with tab1:
        st.subheader(f"Dictamen de Estatus: {nombre}")
        
        # Bloque de Fechas Clave (Lo que pediste)
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.markdown(f"""
            <div class='info-box'>
                <b>Fecha Cumplimiento Edad:</b> {fechas_clave['fecha_cumple_edad'].strftime('%d/%m/%Y')}<br>
                <b>Fecha Cumplimiento Semanas:</b> {fechas_clave['fecha_cumple_semanas'].strftime('%d/%m/%Y') if fechas_clave['fecha_cumple_semanas'] else 'No cumplido'}<br>
                <b>FECHA DE ESTATUS:</b> {fechas_clave['fecha_estatus'].strftime('%d/%m/%Y') if fechas_clave['tiene_estatus'] else 'PENDIENTE'}
            </div>
            """, unsafe_allow_html=True)
            
        with col_f2:
            st.markdown(f"""
            <div class='info-box' style='border-color: #e67e22; background-color: #fcf3cf;'>
                <b>FECHA DE CORTE (INDEXACIÓN):</b> {fechas_clave['fecha_corte'].strftime('%d/%m/%Y')}<br>
                <b>Razón:</b> {fechas_clave['razon_corte']}<br>
                <b>FECHA EFECTIVIDAD:</b> {fechas_clave['fecha_efectividad'].strftime('%d/%m/%Y')}
            </div>
            """, unsafe_allow_html=True)
            
        st.divider()
        
        # Resultados
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Semanas Totales", f"{total_sem:,.2f}")
        c2.metric("IBL Calculado", f"${ibl_def:,.0f}")
        c3.metric("Mesada", f"${mesada:,.0f}")
        c4.metric("Tasa", f"{tasa:.2f}%")
        
        st.caption(f"IBL basado en: {origen_ibl}")
        
        with st.expander("Ver Detalle IBL Aplicado"):
            st.dataframe(det_10 if ibl_10 >= ibl_vida else det_vida)

    with tab2:
        st.subheader("Simulación")
        c_conf, c_res = st.columns([1, 2])
        
        # Config Proyección
        with c_conf:
            opcion = st.radio("Estrategia", ["Cotizar Indep.", "Extra"])
            ultimo = df['IBC'].iloc[-1]
            val = st.number_input("Valor", value=float(ultimo) if "Cotizar" in opcion else 1000000.0)
            anios = st.slider("Años", 1, 15, 5)
            
            nuevo_ibc = val if "Cotizar" in opcion else ultimo + val
            costo = (val if "Cotizar" in opcion else val) * 0.285
            inv = costo * anios * 12
            st.metric("Inversión Total", f"${inv:,.0f}")

        # Calc Proyección
        with c_res:
            filas = []
            cur = df['Hasta'].max() + timedelta(days=1)
            for _ in range(anios*12):
                filas.append({"Desde": cur, "Hasta": cur+timedelta(days=30), "IBC": nuevo_ibc, "Semanas": 4.29})
                cur += timedelta(days=31)
            
            df_fut = pd.concat([df, pd.DataFrame(filas)], ignore_index=True)
            liq_f = LiquidadorPension(df_fut, genero, fecha_nac)
            
            # Usamos fecha corte futura
            fechas_fut = liq_f.determinar_fechas_clave()
            ibl_f = max(liq_f.calcular_ibl_indexado(fechas_fut['fecha_corte'], "ultimos_10")[0], 
                        liq_f.calcular_ibl_indexado(fechas_fut['fecha_corte'], "toda_vida")[0])
            
            mes_f, tasa_f, _ = liq_f.calcular_tasa_reemplazo_797(ibl_f, df_fut['Semanas'].sum(), datetime.now().year+anios, aplicar_tope)
            
            delta = mes_f - mesada
            roi = (inv / delta / 12) if delta > 0 else 0
            
            m1, m2 = st.columns(2)
            m1.metric("Mesada Futura", f"${mes_f:,.0f}", f"+ ${delta:,.0f}")
            if roi > 0: st.success(f"Recuperación en {roi:.1f} años")
            else: st.error("Sin mejora financiera")
            
            proyeccion_data = {
                "estrategia": f"Aporte ${val:,.0f} por {anios} años",
                "inversion": inv, "mesada_fut": mes_f, "delta": delta, "roi": roi
            }

    # --- BOTÓN WORD ---
    st.sidebar.markdown("---")
    liq_data = {"semanas": total_sem, "ibl": ibl_def, "origen_ibl": origen_ibl, "tasa": tasa, "mesada": mesada, 
                "ibl_10": ibl_10, "ibl_vida": ibl_vida, "df_soporte": det_10 if ibl_10 >= ibl_vida else det_vida}
    
    perfil = {"nombre": nombre, "fecha_nac": fecha_nac.strftime('%d/%m/%Y')}
    
    # Generar Word
    docx = generar_reporte_completo(perfil, fechas_clave, liq_data, proyeccion_data if 'proyeccion_data' in locals() else None)
    
    st.sidebar.download_button("📥 Descargar Dictamen (Word)", docx, f"Dictamen_{nombre}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
