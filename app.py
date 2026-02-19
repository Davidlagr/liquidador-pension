import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, datetime, timedelta
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
    .ibl-box { background-color: #f4f6f7; padding: 10px; border-radius: 5px; border: 1px solid #d5dbdb; text-align: center; }
    .status-ok { color: #27ae60; font-weight: bold; }
    .status-alert { color: #d35400; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("⚖️ Liquidador Pensional: Análisis Técnico & Jurídico")

# --- ESTADO ---
if 'df_crudo' not in st.session_state: st.session_state.df_crudo = None
if 'df_final' not in st.session_state: st.session_state.df_final = None

# ==========================================
# GENERADOR DE REPORTE WORD
# ==========================================
def generar_reporte_completo(perfil, fechas, liq_data, proyeccion=None):
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(10)

    # TÍTULO
    tit = doc.add_heading('DICTAMEN TÉCNICO PENSIONAL', 0)
    tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Fecha de Emisión: {datetime.now().strftime('%d/%m/%Y')}")
    doc.add_paragraph("_" * 70)

    # 1. INFORMACIÓN
    doc.add_heading('1. ESTATUS JURÍDICO', level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    
    datos = [
        ("Afiliado", perfil['nombre']),
        ("Fecha Nacimiento", perfil['fecha_nac']),
        ("Cumplimiento Edad", fechas['fecha_cumple_edad'].strftime('%d/%m/%Y')),
        ("Cumplimiento Semanas", fechas['fecha_cumple_semanas'].strftime('%d/%m/%Y') if fechas['fecha_cumple_semanas'] else "No cumplido"),
        ("FECHA ESTATUS", fechas['fecha_estatus'].strftime('%d/%m/%Y') if fechas['tiene_estatus'] else "NO ADQUIRIDO"),
        ("FECHA CORTE (INDEXACIÓN)", fechas['fecha_corte'].strftime('%d/%m/%Y')),
    ]
    for k, v in datos:
        r = table.add_row().cells
        r[0].text = k
        r[1].text = str(v)

    # 2. LIQUIDACIÓN
    doc.add_heading('2. RESULTADO DE LA LIQUIDACIÓN', level=1)
    t2 = doc.add_table(rows=1, cols=2)
    t2.style = 'Light Shading Accent 1'
    
    res_data = [
        ("Semanas Totales", f"{liq_data['semanas']:,.2f}"),
        ("IBL 10 Años", f"${liq_data['ibl_10']:,.0f}"),
        ("IBL Toda la Vida", f"${liq_data['ibl_vida']:,.0f}"),
        ("IBL APLICADO", f"${liq_data['ibl']:,.0f} ({liq_data['origen_ibl']})"),
        ("Tasa Reemplazo", f"{liq_data['tasa']:.2f}%"),
        ("MESADA PENSIONAL", f"${liq_data['mesada']:,.0f}")
    ]
    for k, v in res_data:
        r = t2.add_row().cells
        r[0].text = k
        r[1].text = v

    # 3. GRÁFICA COMPARATIVA
    doc.add_heading('3. ANÁLISIS GRÁFICO', level=1)
    fig1, ax1 = plt.subplots(figsize=(6, 3))
    ax1.bar(["Últimos 10", "Toda Vida"], [liq_data['ibl_10'], liq_data['ibl_vida']], color=['#3498db', '#2ecc71'])
    ax1.set_title("Comparativo IBL")
    ax1.yaxis.set_major_formatter('${x:,.0f}')
    
    memfile1 = BytesIO()
    fig1.savefig(memfile1)
    doc.add_picture(memfile1, width=Inches(5))
    memfile1.close()
    
    # 4. TABLAS DE SOPORTE (AMBAS)
    doc.add_page_break()
    doc.add_heading('ANEXO 1: DETALLE ÚLTIMOS 10 AÑOS', level=1)
    
    def agregar_tabla_soporte(df_sop):
        if not df_sop.empty:
            t = doc.add_table(rows=1, cols=3)
            t.style = 'Table Grid'
            h = t.rows[0].cells
            h[0].text = 'Periodo'; h[1].text = 'IBC Histórico'; h[2].text = 'IBC Actualizado'
            
            # Limitamos a las primeras 50 y últimas 10 filas para no saturar el Word si es muy largo
            filas_mostrar = pd.concat([df_sop.head(50), df_sop.tail(10)]) if len(df_sop) > 60 else df_sop
            
            for _, row in filas_mostrar.iterrows():
                rc = t.add_row().cells
                rc[0].text = f"{row['Desde'].strftime('%m/%Y')} - {row['Hasta'].strftime('%m/%Y')}"
                rc[1].text = f"${row['IBC_Historico']:,.0f}"
                rc[2].text = f"${row['IBC_Actualizado']:,.0f}"

    agregar_tabla_soporte(liq_data['df_soporte_10'])

    doc.add_heading('ANEXO 2: DETALLE TODA LA VIDA', level=1)
    agregar_tabla_soporte(liq_data['df_soporte_vida'])

    # 5. PROYECCIÓN
    if proyeccion:
        doc.add_page_break()
        doc.add_heading('4. PROYECCIÓN FUTURA', level=1)
        doc.add_paragraph(f"Estrategia: {proyeccion['estrategia']}")
        doc.add_paragraph(f"Inversión: ${proyeccion['inversion']:,.0f}")
        doc.add_paragraph(f"Nueva Mesada: ${proyeccion['mesada_fut']:,.0f}")
        doc.add_paragraph(f"ROI: {proyeccion['roi']:.1f} Años")

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
    
    fechas_clave = liq.determinar_fechas_clave()
    
    # CALCULAMOS LOS DOS IBL POR SEPARADO
    ibl_10, det_10 = liq.calcular_ibl_indexado(fechas_clave['fecha_corte'], "ultimos_10")
    ibl_vida, det_vida = liq.calcular_ibl_indexado(fechas_clave['fecha_corte'], "toda_vida")
    
    ibl_def = max(ibl_10, ibl_vida)
    origen_ibl = "Últimos 10 Años" if ibl_10 >= ibl_vida else "Toda la Vida"
    
    total_sem = df['Semanas'].sum()
    mesada, tasa, info = liq.calcular_tasa_reemplazo_797(
        ibl_def, total_sem, datetime.now().year, aplicar_tope
    )

    # --- PESTAÑA 1: DIAGNÓSTICO DETALLADO ---
    tab1, tab2 = st.tabs(["📊 DIAGNÓSTICO JURÍDICO", "💰 PROYECCIÓN"])
    
    with tab1:
        st.subheader(f"Dictamen de Estatus: {nombre}")
        
        # 1. Fechas Clave
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
        
        # 2. Resumen Métricas Generales
        c1, c2, c3 = st.columns(3)
        c1.metric("Semanas Totales", f"{total_sem:,.2f}")
        c2.metric("Mesada Pensional", f"${mesada:,.0f}")
        c3.metric("Tasa Reemplazo", f"{tasa:.2f}%")

        st.divider()

        # 3. COMPARATIVO IBL (Lo que pediste restaurar)
        st.markdown("#### 🆚 Análisis Comparativo de Ingreso Base (IBL)")
        
        # Visualización Lado a Lado
        col_ibl_L, col_ibl_R = st.columns(2)
        with col_ibl_L:
            st.markdown(f"""
            <div class='ibl-box'>
                <h4>Últimos 10 Años</h4>
                <h2>${ibl_10:,.0f}</h2>
            </div>
            """, unsafe_allow_html=True)
        with col_ibl_R:
             st.markdown(f"""
            <div class='ibl-box'>
                <h4>Toda la Vida</h4>
                <h2>${ibl_vida:,.0f}</h2>
            </div>
            """, unsafe_allow_html=True)
            
        st.caption(f"El sistema aplicó automáticamente: **{origen_ibl}** por ser más favorable.")
        
        # Gráfica Comparativa Restaurada
        chart_data = pd.DataFrame({
            "Monto": [ibl_10, ibl_vida]
        }, index=["Últimos 10 Años", "Toda la Vida"])
        st.bar_chart(chart_data, color="#2E86C1")

        # 4. SOPORTES DETALLADOS (Ambos Visibles)
        st.markdown("#### 📄 Soportes Técnicos Detallados")
        st.write("Despliega las pestañas para auditar los periodos utilizados en cada cálculo.")
        
        col_det_1, col_det_2 = st.columns(2)
        
        with col_det_1:
            with st.expander("🔍 Ver Detalle Últimos 10 Años"):
                st.dataframe(det_10.style.format({
                    'IBC_Historico': "${:,.0f}", 'IBC_Actualizado': "${:,.0f}", 'Factor_IPC': "{:.4f}"
                }))
        
        with col_det_2:
            with st.expander("🌍 Ver Detalle Toda la Vida"):
                st.dataframe(det_vida.style.format({
                    'IBC_Historico': "${:,.0f}", 'IBC_Actualizado': "${:,.0f}", 'Factor_IPC': "{:.4f}"
                }))

    # --- PESTAÑA 2: PROYECCIÓN ---
    with tab2:
        st.subheader("Simulación Financiera")
        c_conf, c_res = st.columns([1, 2])
        
        with c_conf:
            opcion = st.radio("Estrategia", ["Cotizar Indep.", "Extra"])
            ultimo = df['IBC'].iloc[-1]
            val = st.number_input("Valor", value=float(ultimo) if "Cotizar" in opcion else 1000000.0)
            anios = st.slider("Años", 1, 15, 5)
            
            nuevo_ibc = val if "Cotizar" in opcion else ultimo + val
            costo = (val if "Cotizar" in opcion else val) * 0.285
            inv = costo * anios * 12
            st.metric("Inversión Total", f"${inv:,.0f}")

        with c_res:
            filas = []
            cur = df['Hasta'].max() + timedelta(days=1)
            for _ in range(anios*12):
                filas.append({"Desde": cur, "Hasta": cur+timedelta(days=30), "IBC": nuevo_ibc, "Semanas": 4.29})
                cur += timedelta(days=31)
            
            df_fut = pd.concat([df, pd.DataFrame(filas)], ignore_index=True)
            liq_f = LiquidadorPension(df_fut, genero, fecha_nac)
            
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
            
            # Gráfica Proyección
            st.bar_chart(pd.DataFrame({"Mesada": [mesada, mes_f]}, index=["Hoy", "Futuro"]), color="#27AE60")
            
            proyeccion_data = {
                "estrategia": f"Aporte ${val:,.0f} por {anios} años",
                "inversion": inv, "mesada_fut": mes_f, "delta": delta, "roi": roi
            }

    # --- BOTÓN WORD ---
    st.sidebar.markdown("---")
    
    # Empaquetar datos para el reporte
    liq_data = {
        "semanas": total_sem, "ibl": ibl_def, "origen_ibl": origen_ibl, 
        "tasa": tasa, "mesada": mesada, 
        "ibl_10": ibl_10, "ibl_vida": ibl_vida,
        "df_soporte_10": det_10, "df_soporte_vida": det_vida  # Enviamos AMBOS soportes
    }
    
    perfil = {"nombre": nombre, "fecha_nac": fecha_nac.strftime('%d/%m/%Y')}
    
    docx = generar_reporte_completo(perfil, fechas_clave, liq_data, proyeccion_data if 'proyeccion_data' in locals() else None)
    
    st.sidebar.download_button("📥 Descargar Dictamen (Word)", docx, f"Dictamen_{nombre}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
