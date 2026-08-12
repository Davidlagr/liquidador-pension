import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import date, datetime, timedelta
from io import BytesIO
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from data_processor import extraer_tabla_cruda, limpiar_y_estandarizar, aplicar_regla_simultaneidad
from logic import LiquidadorPension

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(page_title="Liquidador Pensional Pro", layout="wide", page_icon="⚖️")

# ==========================================
# 2. SISTEMA DE AUTENTICACIÓN
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("<h2 style='text-align: center;'>🔒 Acceso al Sistema Pensional</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form"):
            usuario = st.text_input("Usuario")
            clave = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Ingresar", use_container_width=True)
            
            if submit:
                if usuario == "80799289" and clave == "1808DV":
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas. Verifica tu usuario y contraseña.")
    st.stop()

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

    # 1. MARCO NORMATIVO
    doc.add_heading('1. MARCO NORMATIVO Y METODOLÓGICO', level=1)
    doc.add_paragraph(
        "El presente análisis técnico-jurídico se fundamenta en los parámetros de la Ley 100 de 1993, "
        "con las modificaciones introducidas por la Ley 797 de 2003.\n\n"
        "• Cálculo del Ingreso Base de Liquidación (IBL): Se realiza la actualización (indexación) "
        "de los Ingresos Base de Cotización (IBC) históricos utilizando el Índice de Precios al Consumidor (IPC) "
        "certificado por el DANE. En virtud del principio de favorabilidad y la jurisprudencia aplicable, se liquidan y comparan dos escenarios: "
        "el promedio de los últimos 10 años cotizados y el promedio de toda la vida laboral del afiliado. "
        "Se aplica el escenario que resulte más beneficioso."
    )

    # 2. INFORMACIÓN DEL AFILIADO
    doc.add_heading('2. ESTATUS JURÍDICO', level=1)
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

    # 3. LIQUIDACIÓN
    doc.add_heading('3. RESULTADO DE LA LIQUIDACIÓN ACTUAL', level=1)
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

    def agregar_tabla_soporte(df_sop):
        if not df_sop.empty:
            t = doc.add_table(rows=1, cols=3)
            t.style = 'Table Grid'
            h = t.rows[0].cells
            h[0].text = 'Periodo'; h[1].text = 'IBC Histórico'; h[2].text = 'IBC Actualizado'
            
            filas_mostrar = pd.concat([df_sop.head(50), df_sop.tail(10)]) if len(df_sop) > 60 else df_sop
            
            for _, row in filas_mostrar.iterrows():
                rc = t.add_row().cells
                rc[0].text = f"{row['Desde'].strftime('%m/%Y')} - {row['Hasta'].strftime('%m/%Y')}"
                rc[1].text = f"${row['IBC_Historico']:,.0f}"
                rc[2].text = f"${row['IBC_Actualizado']:,.0f}"

    # 4. TABLAS DE SOPORTE ACTUALES
    doc.add_page_break()
    doc.add_heading('ANEXO 1: DETALLE ÚLTIMOS 10 AÑOS (ACTUAL)', level=1)
    agregar_tabla_soporte(liq_data['df_soporte_10'])

    doc.add_heading('ANEXO 2: DETALLE TODA LA VIDA (ACTUAL)', level=1)
    agregar_tabla_soporte(liq_data['df_soporte_vida'])

    # 5. PROYECCIÓN (SOLO SI FUE APROBADA)
    if proyeccion:
        doc.add_page_break()
        doc.add_heading('4. PROYECCIÓN ESTRATÉGICA DE MEJORA PENSIONAL', level=1)
        doc.add_paragraph("Esquema de viabilidad financiera liquidando salud (12.5%) y pensión (16%) sobre el 100% del IBC proyectado, con incremento anual estimado del SMLMV:")
        
        t3 = doc.add_table(rows=1, cols=2)
        t3.style = 'Table Grid'
        datos_proy = [
            ("Estrategia / Tipo", proyeccion['estrategia']),
            ("Años Proyectados", f"{proyeccion['anios']} años"),
            ("INVERSIÓN TOTAL (Aprox)", f"${proyeccion['inversion']:,.0f}"),
            ("NUEVA MESADA PROYECTADA", f"${proyeccion['mesada_fut']:,.0f}"),
            ("Incremento de Mesada (Delta)", f"${proyeccion['delta']:,.0f} mensuales"),
            ("Tiempo de Retorno (ROI)", f"{proyeccion['roi']:.1f} Años tras pensionarse")
        ]
        for k, v in datos_proy:
            r = t3.add_row().cells
            r[0].text = k
            r[1].text = v
            
        doc.add_page_break()
        doc.add_heading('5. SOPORTES: CÁLCULO DE LA MESADA FUTURA', level=1)
        doc.add_paragraph(f"Para el cálculo de la mesada futura, el sistema determinó que el escenario más favorable es: {proyeccion['origen_ibl_fut']}.")
        
        doc.add_heading('5.1 DETALLE PROYECCIÓN: ÚLTIMOS 10 AÑOS', level=2)
        agregar_tabla_soporte(proyeccion['det_10_fut'])

        doc.add_heading('5.2 DETALLE PROYECCIÓN: TODA LA VIDA', level=2)
        agregar_tabla_soporte(proyeccion['det_vida_fut'])

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
    
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False
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

else:
    df = st.session_state.df_final
    liq = LiquidadorPension(df, genero, fecha_nac)
    
    fechas_clave = liq.determinar_fechas_clave()
    ibl_10, det_10 = liq.calcular_ibl_indexado(fechas_clave['fecha_corte'], "ultimos_10")
    ibl_vida, det_vida = liq.calcular_ibl_indexado(fechas_clave['fecha_corte'], "toda_vida")
    
    ibl_def = max(ibl_10, ibl_vida)
    origen_ibl = "Últimos 10 Años" if ibl_10 >= ibl_vida else "Toda la Vida"
    
    total_sem = df['Semanas'].sum()
    mesada, tasa, info = liq.calcular_tasa_reemplazo_797(
        ibl_def, total_sem, datetime.now().year, aplicar_tope
    )

    tab1, tab2 = st.tabs(["📊 DIAGNÓSTICO JURÍDICO", "📈 PROYECCIÓN DE MEJORA"])
    
    with tab1:
        st.subheader(f"Dictamen de Estatus: {nombre}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Semanas Totales", f"{total_sem:,.2f}")
        c2.metric("Mesada Pensional", f"${mesada:,.0f}")
        c3.metric("Tasa Reemplazo", f"{tasa:.2f}%")
        st.divider()

    # --- PESTAÑA 2: PROYECCIÓN Y ROI ---
    with tab2:
        st.subheader("Simulación Financiera de Mejora Pensional")
        c_conf, c_res = st.columns([1, 2])
        
        with c_conf:
            st.markdown("### Parámetros de Inversión")
            st.info("💡 **Criterio Técnico:** Para esta estrategia se asume el pago de Salud (12.5%) y Pensión (16%) sobre el **100% del IBC**, omitiendo la presunción del 40% para independientes, con el fin de maximizar los aportes a la historia laboral.")
            
            smlmv_actual = st.number_input("SMLMV Año Actual Base", value=1300000.0, step=100000.0)
            smlmv_deseados = st.number_input("IBC Deseado (En SMLMV)", min_value=1.0, max_value=25.0, value=5.0, step=0.5)
            anios_proy = st.slider("Años a realizar el aporte", 1, 15, 5)
            incremento_anual_smlmv = st.number_input("Est. Aumento Anual SMLMV (%)", value=5.0, step=0.5) / 100.0
            
            # Muestra costo referencial del primer año
            ibc_ref_ano_1 = smlmv_actual * smlmv_deseados
            costo_mes_ano_1 = ibc_ref_ano_1 * 0.285
            
            st.success(f"**Referencia Año 1:**\nIBC: ${ibc_ref_ano_1:,.0f}\nCosto Aporte Mensual: ${costo_mes_ano_1:,.0f}")

        with c_res:
            filas_fut = []
            cur = df['Hasta'].max() + timedelta(days=1)
            inversion_total = 0
            
            # Bucle para proyectar mes a mes incrementando el SMLMV año a año
            for m in range(anios_proy * 12):
                year_offset = m // 12
                # Interés compuesto para proyectar el SMLMV en el futuro
                smlmv_periodo = smlmv_actual * ((1 + incremento_anual_smlmv) ** year_offset)
                ibc_periodo = smlmv_deseados * smlmv_periodo
                
                # El costo es el 28.5% (16% pensión + 12.5% salud) sobre el 100% del IBC
                costo_mes = ibc_periodo * 0.285
                inversion_total += costo_mes
                
                filas_fut.append({
                    "Desde": cur, 
                    "Hasta": cur + timedelta(days=30), 
                    "IBC": ibc_periodo, 
                    "Semanas": 4.29
                })
                cur += timedelta(days=31)
            
            df_fut = pd.concat([df, pd.DataFrame(filas_fut)], ignore_index=True)
            liq_f = LiquidadorPension(df_fut, genero, fecha_nac)
            
            fechas_fut = liq_f.determinar_fechas_clave()
            
            # Obtención de ambos soportes futuros
            ibl_10_fut, det_10_fut = liq_f.calcular_ibl_indexado(fechas_fut['fecha_corte'], "ultimos_10")
            ibl_vida_fut, det_vida_fut = liq_f.calcular_ibl_indexado(fechas_fut['fecha_corte'], "toda_vida")
            
            ibl_f = max(ibl_10_fut, ibl_vida_fut)
            origen_ibl_fut = "Últimos 10 Años" if ibl_10_fut >= ibl_vida_fut else "Toda la Vida"
            
            mes_f, tasa_f, _ = liq_f.calcular_tasa_reemplazo_797(ibl_f, df_fut['Semanas'].sum(), datetime.now().year + anios_proy, aplicar_tope)
            
            delta = mes_f - mesada
            roi = (inversion_total / (delta * 12)) if delta > 0 else 0
            
            st.markdown("### Resultados de la Proyección")
            m1, m2, m3 = st.columns(3)
            m1.metric("Nueva Mesada", f"${mes_f:,.0f}", f"+ ${delta:,.0f} mes")
            m2.metric("Inversión Total", f"${inversion_total:,.0f}")
            if roi > 0: 
                m3.metric("Retorno (ROI)", f"{roi:.1f} años")
            else: 
                m3.error("Sin mejora")
                
            st.caption(f"**Escenario aplicado para liquidación futura:** {origen_ibl_fut}")

            t_d1, t_d2 = st.tabs(["📑 Detalle 10 Años (Proyectado)", "📑 Detalle Toda la Vida (Proyectado)"])
            with t_d1:
                st.dataframe(det_10_fut.style.format({'IBC_Historico': "${:,.0f}", 'IBC_Actualizado': "${:,.0f}"}))
            with t_d2:
                st.dataframe(det_vida_fut.style.format({'IBC_Historico': "${:,.0f}", 'IBC_Actualizado': "${:,.0f}"}))
            
            proyeccion_data = {
                "estrategia": f"Aporte sobre {smlmv_deseados} SMLMV (100% IBC)", 
                "anios": anios_proy,
                "inversion": inversion_total, 
                "mesada_fut": mes_f, 
                "delta": delta, 
                "roi": roi,
                "origen_ibl_fut": origen_ibl_fut,
                "det_10_fut": det_10_fut,
                "det_vida_fut": det_vida_fut
            }

    # --- BOTÓN WORD Y APROBACIÓN ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📄 Generación de Informe")
    
    incluir_proyeccion = st.sidebar.checkbox("✅ Aprobar e Incluir Proyección al Dictamen", value=False)
    
    liq_data = {
        "semanas": total_sem, "ibl": ibl_def, "origen_ibl": origen_ibl, 
        "tasa": tasa, "mesada": mesada, "ibl_10": ibl_10, "ibl_vida": ibl_vida,
        "df_soporte_10": det_10, "df_soporte_vida": det_vida 
    }
    perfil = {"nombre": nombre, "fecha_nac": fecha_nac.strftime('%d/%m/%Y')}
    
    docx = generar_reporte_completo(perfil, fechas_clave, liq_data, proyeccion_data if incluir_proyeccion else None)
    
    st.sidebar.download_button(
        label="📥 Descargar Dictamen Técnico (Word)", 
        data=docx, 
        file_name=f"Dictamen_{nombre}.docx", 
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
