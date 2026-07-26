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
# 1. CONFIGURACIÓN DE PÁGINA (DEBE IR PRIMERO)
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

# ==========================================
# EL RESTO DE TU APLICACIÓN
# ==========================================

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
        "Se aplica el escenario que resulte más beneficioso.\n\n"
        "• Tasa de Reemplazo: Se aplica la fórmula decreciente establecida en el artículo 34 de la Ley 100 "
        "(modificado por el art. 10 de la Ley 797/2003), la cual otorga un porcentaje que varía entre el 65% y el 80% "
        "dependiendo del nivel de ingresos (en SMLMV) y se incrementa un 1.5% por cada 50 semanas adicionales "
        "a las mínimas requeridas, hasta llegar al tope legal máximo."
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

    # 4. GRÁFICA COMPARATIVA IBL
    doc.add_heading('4. ANÁLISIS GRÁFICO IBL', level=1)
    fig1, ax1 = plt.subplots(figsize=(6, 3))
    ax1.bar(["Últimos 10", "Toda Vida"], [liq_data['ibl_10'], liq_data['ibl_vida']], color=['#3498db', '#2ecc71'])
    ax1.set_title("Comparativo Ingreso Base de Liquidación (IBL)")
    ax1.yaxis.set_major_formatter('${x:,.0f}')
    
    memfile1 = BytesIO()
    fig1.savefig(memfile1, format='png', bbox_inches='tight')
    doc.add_picture(memfile1, width=Inches(5))
    memfile1.close()
    plt.close(fig1)
    
    # 5. TABLAS DE SOPORTE (AMBAS)
    doc.add_page_break()
    doc.add_heading('ANEXO 1: DETALLE ÚLTIMOS 10 AÑOS', level=1)
    
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

    agregar_tabla_soporte(liq_data['df_soporte_10'])

    doc.add_heading('ANEXO 2: DETALLE TODA LA VIDA', level=1)
    agregar_tabla_soporte(liq_data['df_soporte_vida'])

    # 6. PROYECCIÓN (SOLO SI FUE APROBADA)
    if proyeccion:
        doc.add_page_break()
        doc.add_heading('5. PROYECCIÓN ESTRATÉGICA DE MEJORA', level=1)
        doc.add_paragraph("A continuación, se detalla el esquema de viabilidad financiera en caso de optar por realizar cotizaciones proyectadas para mejorar la mesada pensional:")
        
        t3 = doc.add_table(rows=1, cols=2)
        t3.style = 'Table Grid'
        datos_proy = [
            ("Estrategia / Tipo", proyeccion['estrategia']),
            ("Años Proyectados", f"{proyeccion['anios']} años"),
            ("Costo Promedio Anual (Solo Indep.)", f"${proyeccion['costo_anual']:,.0f}"),
            ("INVERSIÓN TOTAL", f"${proyeccion['inversion']:,.0f}"),
            ("NUEVA MESADA PROYECTADA", f"${proyeccion['mesada_fut']:,.0f}"),
            ("Incremento de Mesada (Delta)", f"${proyeccion['delta']:,.0f} mensuales"),
            ("Tiempo de Retorno de Inversión (ROI)", f"{proyeccion['roi']:.1f} Años tras pensionarse")
        ]
        for k, v in datos_proy:
            r = t3.add_row().cells
            r[0].text = k
            r[1].text = v

        doc.add_paragraph("\nAnálisis Gráfico de Retorno de Inversión (ROI):")
        
        # Gráfica Comparativa Mesadas
        fig_p1, ax_p1 = plt.subplots(figsize=(6, 3))
        ax_p1.bar(["Mesada Actual", "Mesada Proyectada"], [liq_data['mesada'], proyeccion['mesada_fut']], color=['#e74c3c', '#27ae60'])
        ax_p1.set_title("Incremento de Mesada Pensional")
        ax_p1.yaxis.set_major_formatter('${x:,.0f}')
        mem_p1 = BytesIO()
        fig_p1.savefig(mem_p1, format='png', bbox_inches='tight')
        doc.add_picture(mem_p1, width=Inches(5))
        mem_p1.close()
        plt.close(fig_p1)
        
        # Gráfica Punto de Equilibrio (ROI)
        fig_p2, ax_p2 = plt.subplots(figsize=(6, 3))
        anios_max = int(np.ceil(proyeccion['roi'])) + 3 if proyeccion['roi'] > 0 else 10
        x_anios = np.arange(0, anios_max + 1)
        y_retorno = x_anios * proyeccion['delta'] * 12
        
        ax_p2.plot(x_anios, y_retorno, label='Retorno Acumulado', color='green', marker='o')
        ax_p2.axhline(y=proyeccion['inversion'], color='red', linestyle='--', label='Costo Total de Inversión')
        ax_p2.set_title("Línea de Tiempo - Retorno de Inversión (ROI)")
        ax_p2.set_xlabel("Años tras obtener la pensión")
        ax_p2.set_ylabel("Capital ($)")
        ax_p2.yaxis.set_major_formatter('${x:,.0f}')
        ax_p2.legend()
        ax_p2.grid(True, linestyle='--', alpha=0.6)
        
        mem_p2 = BytesIO()
        fig_p2.savefig(mem_p2, format='png', bbox_inches='tight')
        doc.add_picture(mem_p2, width=Inches(5.5))
        mem_p2.close()
        plt.close(fig_p2)

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
        
    if st.button("🔄 Reiniciar App"):
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
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Semanas Totales", f"{total_sem:,.2f}")
        c2.metric("Mesada Pensional", f"${mesada:,.0f}")
        c3.metric("Tasa Reemplazo", f"{tasa:.2f}%")

        st.divider()

        st.markdown("#### 🆚 Análisis Comparativo de Ingreso Base (IBL)")
        col_ibl_L, col_ibl_R = st.columns(2)
        with col_ibl_L:
            st.markdown(f"""<div class='ibl-box'><h4>Últimos 10 Años</h4><h2>${ibl_10:,.0f}</h2></div>""", unsafe_allow_html=True)
        with col_ibl_R:
             st.markdown(f"""<div class='ibl-box'><h4>Toda la Vida</h4><h2>${ibl_vida:,.0f}</h2></div>""", unsafe_allow_html=True)
            
        st.caption(f"El sistema aplicó automáticamente: **{origen_ibl}** por ser más favorable.")
        chart_data = pd.DataFrame({"Monto": [ibl_10, ibl_vida]}, index=["Últimos 10 Años", "Toda la Vida"])
        st.bar_chart(chart_data, color="#2E86C1")

        st.markdown("#### 📄 Soportes Técnicos Detallados")
        col_det_1, col_det_2 = st.columns(2)
        with col_det_1:
            with st.expander("🔍 Ver Detalle Últimos 10 Años"):
                st.dataframe(det_10.style.format({'IBC_Historico': "${:,.0f}", 'IBC_Actualizado': "${:,.0f}", 'Factor_IPC': "{:.4f}"}))
        with col_det_2:
            with st.expander("🌍 Ver Detalle Toda la Vida"):
                st.dataframe(det_vida.style.format({'IBC_Historico': "${:,.0f}", 'IBC_Actualizado': "${:,.0f}", 'Factor_IPC': "{:.4f}"}))

    # --- PESTAÑA 2: PROYECCIÓN Y ROI ---
    with tab2:
        st.subheader("Simulación Financiera y Retorno de Inversión (ROI)")
        c_conf, c_res = st.columns([1, 2])
        
        with c_conf:
            st.markdown("**Configuración del Escenario**")
            opcion = st.radio("Modalidad de Cotización", ["Cotizante Independiente", "Dependiente + Extra Independiente"])
            ultimo_ibc = float(df['IBC'].iloc[-1]) if not df.empty else 1300000.0
            
            if opcion == "Cotizante Independiente":
                val_ibc = st.number_input("Ingreso Base de Cotización (IBC) Mensual", value=ultimo_ibc, step=100000.0)
                ibc_proyeccion = val_ibc
                costo_mensual = val_ibc * 0.16
                estrategia_texto = f"Independiente (IBC: ${val_ibc:,.0f})"
            else:
                st.info(f"**IBC Actual como Dependiente:** ${ultimo_ibc:,.0f}\n\n*(El empleador asume la cotización sobre este valor)*")
                val_extra = st.number_input("IBC Extra como Independiente", value=1000000.0, step=100000.0)
                ibc_proyeccion = ultimo_ibc + val_extra
                costo_mensual = val_extra * 0.16
                estrategia_texto = f"Dependiente (${ultimo_ibc:,.0f}) + Extra Indep. (${val_extra:,.0f})"

            anios = st.slider("Años proyectados a cotizar", 1, 15, 5)
            
            costo_anual = costo_mensual * 12
            inv = costo_anual * anios
            
            st.success(f"Costo Mensual del Aporte (16%): **${costo_mensual:,.0f}**")
            st.warning(f"Costo Anual de la Inversión: **${costo_anual:,.0f}**")
            st.metric("INVERSIÓN TOTAL", f"${inv:,.0f}")

        with c_res:
            filas = []
            cur = df['Hasta'].max() + timedelta(days=1)
            
            for _ in range(anios*12):
                filas.append({"Desde": cur, "Hasta": cur+timedelta(days=30), "IBC": ibc_proyeccion, "Semanas": 4.29})
                cur += timedelta(days=31)
            
            df_fut = pd.concat([df, pd.DataFrame(filas)], ignore_index=True)
            liq_f = LiquidadorPension(df_fut, genero, fecha_nac)
            
            fechas_fut = liq_f.determinar_fechas_clave()
            ibl_f = max(liq_f.calcular_ibl_indexado(fechas_fut['fecha_corte'], "ultimos_10")[0], 
                        liq_f.calcular_ibl_indexado(fechas_fut['fecha_corte'], "toda_vida")[0])
            
            mes_f, tasa_f, _ = liq_f.calcular_tasa_reemplazo_797(ibl_f, df_fut['Semanas'].sum(), datetime.now().year+anios, aplicar_tope)
            
            delta = mes_f - mesada
            roi = (inv / (delta * 12)) if delta > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Nueva Mesada", f"${mes_f:,.0f}", f"+ ${delta:,.0f} mes")
            if roi > 0: 
                m2.metric("Retorno (ROI)", f"{roi:.1f} años")
                m3.success("Viable")
            else: 
                m2.metric("Retorno (ROI)", "N/A")
                m3.error("Sin mejora")
            
            t_g1, t_g2 = st.tabs(["📊 Comparativo Mesadas", "📈 Punto de Equilibrio (ROI)"])
            with t_g1:
                st.bar_chart(pd.DataFrame({"Mesada": [mesada, mes_f]}, index=["Situación Actual", "Con Proyección"]), color="#27AE60")
            with t_g2:
                if roi > 0:
                    anios_graf = int(np.ceil(roi)) + 3
                    x_arr = np.arange(0, anios_graf + 1)
                    y_arr = x_arr * delta * 12
                    df_roi = pd.DataFrame({
                        "Años": x_arr,
                        "Retorno Acumulado ($)": y_arr,
                        "Costo Inversión ($)": [inv] * len(x_arr)
                    }).set_index("Años")
                    st.line_chart(df_roi)
                else:
                    st.info("No aplica gráfica de retorno porque la mesada proyectada no supera la mesada actual.")
            
            proyeccion_data = {
                "estrategia": estrategia_texto, "costo_anual": costo_anual, "anios": anios,
                "inversion": inv, "mesada_fut": mes_f, "delta": delta, "roi": roi
            }

    # --- BOTÓN WORD Y APROBACIÓN ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📄 Generación de Informe")
    
    incluir_proyeccion = st.sidebar.checkbox("✅ Aprobar e Incluir Proyección de Mejora al Dictamen", value=False)
    
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
