import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from io import BytesIO
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from data_processor import extraer_tabla_cruda, limpiar_y_estandarizar, aplicar_regla_simultaneidad
from logic import LiquidadorPension
from utils import calcular_semanas_minimas_mujeres

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Liquidador & Proyector Pensional", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .metric-box { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-left: 5px solid #2E86C1; }
    .investment-card { background-color: #eaf2f8; padding: 15px; border-radius: 10px; border: 1px solid #d6eaf8; }
    .status-card-ok { background-color: #d4edda; padding: 15px; border-radius: 10px; border-left: 5px solid #28a745; color: #155724; }
    .status-card-warning { background-color: #fff3cd; padding: 15px; border-radius: 10px; border-left: 5px solid #ffc107; color: #856404; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 Planeación Pensional: Calculadora & Inversión")

# --- GESTIÓN DE ESTADO ---
if 'df_crudo' not in st.session_state: st.session_state.df_crudo = None
if 'df_final' not in st.session_state: st.session_state.df_final = None

# --- FUNCIÓN GENERADORA DE WORD ---
def generar_reporte_word(datos_usuario, estatus, liquidacion_actual, proyeccion=None):
    doc = Document()
    
    # Estilos básicos
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)
    
    # Título
    titulo = doc.add_heading('Informe de Proyección Pensional', 0)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph(f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y')}")
    doc.add_paragraph("---------------------------------------------------------------------------------------------------")

    # 1. PERFIL DEL AFILIADO
    doc.add_heading('1. Perfil del Afiliado', level=1)
    p = doc.add_paragraph()
    p.add_run("Nombre: ").bold = True
    p.add_run(f"{datos_usuario['nombre']}\n")
    p.add_run("Género: ").bold = True
    p.add_run(f"{datos_usuario['genero']}\n")
    p.add_run("Edad Actual: ").bold = True
    p.add_run(f"{datos_usuario['edad_texto']}")

    # 2. ESTATUS PENSIONAL (SEMÁFORO)
    doc.add_heading('2. Diagnóstico de Estatus Pensional', level=1)
    if estatus['cumple_todo']:
        p = doc.add_paragraph("ESTADO: DERECHO ADQUIRIDO")
        p.runs[0].bold = True
        p.runs[0].font.color.rgb = RGBColor(0, 128, 0) # Verde
        doc.add_paragraph("El afiliado CUMPLE con los requisitos de edad y semanas para pensionarse.")
    else:
        p = doc.add_paragraph("ESTADO: EN CONSTRUCCIÓN")
        p.runs[0].bold = True
        p.runs[0].font.color.rgb = RGBColor(255, 165, 0) # Naranja
        doc.add_paragraph("Requisitos pendientes:")
        if not estatus['cumple_edad']:
            doc.add_paragraph(f"- Faltan {estatus['falta_edad']} para la edad mínima.", style='List Bullet')
        if not estatus['cumple_semanas']:
            doc.add_paragraph(f"- Faltan {estatus['falta_semanas']:,.1f} semanas para el mínimo de ley.", style='List Bullet')

    # 3. LIQUIDACIÓN ACTUAL
    doc.add_heading('3. Liquidación Pensional (Escenario Hoy)', level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Light Grid Accent 1'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Concepto'
    hdr_cells[1].text = 'Valor'
    
    datos_liq = [
        ("Semanas Totales", f"{liquidacion_actual['semanas']:,.2f}"),
        ("IBL (Promedio Salarial)", f"${liquidacion_actual['ibl']:,.0f}"),
        ("Origen IBL", liquidacion_actual['origen_ibl']),
        ("Tasa de Reemplazo", f"{liquidacion_actual['tasa']:.2f}%"),
        ("MESADA PENSIONAL", f"${liquidacion_actual['mesada']:,.0f}")
    ]
    
    for concepto, valor in datos_liq:
        row_cells = table.add_row().cells
        row_cells[0].text = concepto
        row_cells[1].text = valor
        
    doc.add_paragraph("\nNota: Cálculo basado en Ley 797 de 2003 y sentencias vigentes.")

    # 4. PROYECCIÓN (SI EXISTE)
    if proyeccion:
        doc.add_heading('4. Proyección y Estrategia de Mejora', level=1)
        doc.add_paragraph(f"Estrategia: {proyeccion['estrategia']}")
        doc.add_paragraph(f"Tiempo de inversión: {proyeccion['anios']} años")
        
        # Tabla Comparativa
        table2 = doc.add_table(rows=1, cols=3)
        table2.style = 'Light Shading Accent 1'
        hdr2 = table2.rows[0].cells
        hdr2[0].text = 'Escenario'
        hdr2[1].text = 'Mesada'
        hdr2[2].text = 'Tasa %'
        
        row1 = table2.add_row().cells
        row1[0].text = "HOY"
        row1[1].text = f"${liquidacion_actual['mesada']:,.0f}"
        row1[2].text = f"{liquidacion_actual['tasa']:.2f}%"
        
        row2 = table2.add_row().cells
        row2[0].text = "FUTURO (Proyectado)"
        row2[1].text = f"${proyeccion['mesada_futura']:,.0f}"
        row2[2].text = f"{proyeccion['tasa_futura']:.2f}%"
        
        # Análisis Financiero
        doc.add_heading('4.1 Análisis Financiero (ROI)', level=2)
        p = doc.add_paragraph()
        p.add_run(f"Inversión Total Estimada: ${proyeccion['inversion_total']:,.0f}\n")
        p.add_run(f"Aumento en Mesada: ${proyeccion['delta_mesada']:,.0f}\n")
        
        if proyeccion['delta_mesada'] > 0:
            roi = proyeccion['anios_recuperacion']
            p.add_run(f"Tiempo de Recuperación de Inversión: {roi:.1f} Años").bold = True
            if roi < 5:
                doc.add_paragraph("CONCLUSIÓN: Inversión ALTAMENTE RENTABLE.", style='Intense Quote')
            else:
                doc.add_paragraph("CONCLUSIÓN: Inversión viable a largo plazo.", style='Quote')
        else:
             doc.add_paragraph("CONCLUSIÓN: La inversión no genera aumento en la mesada (Tope alcanzado).")

    # Guardar en memoria
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.header("👤 Perfil")
    nombre = st.text_input("Nombre", "Usuario")
    genero = st.radio("Género", ["Masculino", "Femenino"])
    fecha_nac = st.date_input("Fecha Nacimiento", value=date(1975, 1, 1))
    
    st.markdown("---")
    st.header("⚙️ Configuración")
    aplicar_tope = st.checkbox("Aplicar tope 1800 Semanas", value=True)
    
    st.markdown("---")
    if st.button("🔄 Reiniciar"):
        st.session_state.df_crudo = None
        st.session_state.df_final = None
        st.rerun()

# --- FASE 1: CARGA ---
if st.session_state.df_final is None:
    st.info("📂 Carga tu Historia Laboral (PDF).")
    uploaded_file = st.file_uploader("Subir PDF", type="pdf")

    if uploaded_file:
        if st.session_state.df_crudo is None:
            st.session_state.df_crudo = extraer_tabla_cruda(uploaded_file)
        
        df_disp = st.session_state.df_crudo
        if df_disp is not None and not df_disp.empty:
            st.dataframe(df_disp.head(3), use_container_width=True)
            cols = df_disp.columns.tolist()
            c1, c2, c3, c4 = st.columns(4)
            col_d = c1.selectbox("DESDE", cols, index=2 if len(cols)>2 else 0)
            col_h = c2.selectbox("HASTA", cols, index=3 if len(cols)>3 else 0)
            col_i = c3.selectbox("SALARIO", cols, index=4 if len(cols)>4 else 0)
            col_s = c4.selectbox("SEMANAS", cols, index=len(cols)-1)
            
            if st.button("🚀 Procesar"):
                df_clean = limpiar_y_estandarizar(df_disp, col_d, col_h, col_i, col_s)
                if not df_clean.empty:
                    st.session_state.df_final = aplicar_regla_simultaneidad(df_clean)
                    st.rerun()
                else: st.error("Sin datos válidos.")
        else: st.warning("PDF vacío.")

# --- FASE 2: RESULTADOS ---
else:
    df = st.session_state.df_final
    liq = LiquidadorPension(df, genero, fecha_nac)
    
    # CALCULOS GLOBALES PARA EL REPORTE
    hoy = datetime.now().date()
    edad_dias = (hoy - fecha_nac).days
    edad_anios = edad_dias / 365.25
    req_edad = 62 if genero == "Masculino" else 57
    req_semanas = 1300 if genero == "Masculino" else calcular_semanas_minimas_mujeres(hoy.year)
    total_sem = df['Semanas'].sum()
    
    # Objetos de datos para el reporte
    datos_usuario = {
        "nombre": nombre, "genero": genero, 
        "edad_texto": f"{int(edad_anios)} Años y {int((edad_anios%1)*12)} Meses"
    }
    
    estatus = {
        "cumple_todo": (edad_anios >= req_edad and total_sem >= req_semanas),
        "cumple_edad": edad_anios >= req_edad,
        "cumple_semanas": total_sem >= req_semanas,
        "falta_edad": f"{int(max(0, req_edad - edad_anios))} años",
        "falta_semanas": max(0, req_semanas - total_sem)
    }

    ibl_10, _ = liq.calcular_ibl_indexado("ultimos_10")
    ibl_vida, _ = liq.calcular_ibl_indexado("toda_vida")
    ibl_def = max(ibl_10, ibl_vida)
    
    mesada, tasa, info = liq.calcular_tasa_reemplazo_797(ibl_def, total_sem, datetime.now().year, aplicar_tope)
    
    datos_liq_actual = {
        "semanas": total_sem, "ibl": ibl_def, 
        "origen_ibl": "Últimos 10 Años" if ibl_10 >= ibl_vida else "Toda la Vida",
        "tasa": tasa, "mesada": mesada
    }
    
    # --- INTERFAZ GRÁFICA ---
    tab1, tab2 = st.tabs(["📊 DIAGNÓSTICO", "💰 PROYECCIÓN"])
    
    # Variable para guardar datos de proyección si se usa
    datos_proyeccion = None
    
    with tab1:
        # (Aquí va todo el código visual del Tab 1 que ya tenías)
        # Resumido para el bloque:
        st.markdown(f"### Situación de {nombre}")
        if estatus['cumple_todo']: st.success("✅ DERECHO ADQUIRIDO")
        else: st.warning(f"⚠️ EN CONSTRUCCIÓN. Faltan: {estatus['falta_semanas']} semanas.")
        
        c1, c2 = st.columns(2)
        c1.metric("Semanas", f"{total_sem:,.2f}")
        c1.metric("IBL Favorable", f"${ibl_def:,.0f}")
        c2.metric("Mesada Hoy", f"${mesada:,.0f}")
        c2.metric("Tasa", f"{tasa:.2f}%")

    with tab2:
        st.markdown("### 🔮 Proyección")
        col_conf, col_res = st.columns([1, 2])
        
        with col_conf:
            modo = st.radio("Estrategia:", ["Cotizar Independiente", "Aporte Extra"])
            ultimo_ibc = df['IBC'].iloc[-1]
            if modo.startswith("Cotizar"):
                nuevo_ibc = st.number_input("Nuevo IBC ($)", value=float(ultimo_ibc), step=100000.0)
                base_costo = nuevo_ibc
            else:
                extra = st.number_input("Extra ($)", value=1000000.0)
                nuevo_ibc = ultimo_ibc + extra
                base_costo = extra
            
            anios = st.slider("Años", 1, 15, 5)
            
            # Costos
            costo_mes = base_costo * 0.285
            if base_costo > (4*1423500): costo_mes += base_costo*0.01
            inv_total = costo_mes * anios * 12
            
            st.info(f"Inversión Total: ${inv_total:,.0f}")

        with col_res:
            # Calculo Futuro
            filas_fut = []
            cur = df['Hasta'].max() + timedelta(days=1)
            for _ in range(anios*12):
                fin = cur + timedelta(days=30)
                filas_fut.append({"Desde": cur, "Hasta": fin, "IBC": nuevo_ibc, "Semanas": 4.29})
                cur = fin + timedelta(days=1)
            
            df_fut = pd.concat([df, pd.DataFrame(filas_fut)], ignore_index=True)
            total_fut = df_fut['Semanas'].sum()
            liq_f = LiquidadorPension(df_fut, genero, fecha_nac)
            
            fi_def = max(liq_f.calcular_ibl_indexado("ultimos_10")[0], liq_f.calcular_ibl_indexado("toda_vida")[0])
            f_mes, f_tas, _ = liq_f.calcular_tasa_reemplazo_797(fi_def, total_fut, datetime.now().year+anios, aplicar_tope)
            
            delta = f_mes - mesada
            roi = (inv_total / delta / 12) if delta > 0 else 0
            
            st.metric("Nueva Mesada", f"${f_mes:,.0f}", f"+ ${delta:,.0f}")
            if roi > 0: st.success(f"Recuperación en {roi:.1f} años")
            else: st.error("No aumenta pensión")
            
            # Guardamos datos para el reporte
            datos_proyeccion = {
                "estrategia": f"{modo} durante {anios} años",
                "anios": anios,
                "inversion_total": inv_total,
                "mesada_futura": f_mes,
                "tasa_futura": f_tas,
                "delta_mesada": delta,
                "anios_recuperacion": roi
            }

    # --- BOTÓN DE DESCARGA (EN SIDEBAR PARA ESTAR SIEMPRE VISIBLE) ---
    st.sidebar.markdown("---")
    st.sidebar.header("📄 Informe")
    
    # Generamos el archivo en memoria
    archivo_word = generar_reporte_word(datos_usuario, estatus, datos_liq_actual, datos_proyeccion)
    
    st.sidebar.download_button(
        label="📥 Descargar Informe Completo (Word)",
        data=archivo_word,
        file_name=f"Estudio_Pensional_{nombre}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
