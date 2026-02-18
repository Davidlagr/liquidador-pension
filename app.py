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

# Estilos CSS
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

# ==========================================
# 1. FUNCIÓN GENERADORA DE REPORTES (WORD)
# ==========================================
def generar_reporte_word(datos_usuario, estatus, liquidacion_actual, proyeccion=None):
    doc = Document()
    
    # Estilos
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)
    
    # Título
    titulo = doc.add_heading('Informe de Proyección Pensional', 0)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    doc.add_paragraph("_" * 70)

    # 1. PERFIL
    doc.add_heading('1. Perfil del Afiliado', level=1)
    p = doc.add_paragraph()
    p.add_run(f"Nombre: {datos_usuario['nombre']}\n").bold = True
    p.add_run(f"Género: {datos_usuario['genero']}\n")
    p.add_run(f"Edad: {datos_usuario['edad_texto']}")

    # 2. ESTATUS
    doc.add_heading('2. Diagnóstico de Estatus Pensional', level=1)
    if estatus['cumple_todo']:
        p = doc.add_paragraph("ESTADO: DERECHO ADQUIRIDO")
        p.runs[0].font.color.rgb = RGBColor(0, 128, 0)
        p.runs[0].bold = True
        doc.add_paragraph("Cumple con edad y semanas.")
    else:
        p = doc.add_paragraph("ESTADO: EN CONSTRUCCIÓN")
        p.runs[0].font.color.rgb = RGBColor(255, 165, 0)
        p.runs[0].bold = True
        if not estatus['cumple_edad']: doc.add_paragraph(f"- Falta edad: {estatus['falta_edad']}")
        if not estatus['cumple_semanas']: doc.add_paragraph(f"- Faltan semanas: {estatus['falta_semanas']:,.1f}")

    # 3. LIQUIDACIÓN ACTUAL
    doc.add_heading('3. Escenario Actual', level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Light Grid Accent 1'
    hdr = table.rows[0].cells
    hdr[0].text = 'Concepto'
    hdr[1].text = 'Valor'
    
    filas = [
        ("Semanas Totales", f"{liquidacion_actual['semanas']:,.2f}"),
        ("IBL (Promedio)", f"${liquidacion_actual['ibl']:,.0f}"),
        ("Origen IBL", liquidacion_actual['origen_ibl']),
        ("Mesada Pensional", f"${liquidacion_actual['mesada']:,.0f}"),
        ("Tasa Reemplazo", f"{liquidacion_actual['tasa']:.2f}%")
    ]
    for k, v in filas:
        row = table.add_row().cells
        row[0].text = k
        row[1].text = v

    # 4. PROYECCIÓN
    if proyeccion:
        doc.add_heading('4. Proyección Futura', level=1)
        doc.add_paragraph(f"Estrategia: {proyeccion['estrategia']}")
        
        # Tabla Comparativa
        t2 = doc.add_table(rows=1, cols=3)
        t2.style = 'Light Shading Accent 1'
        h2 = t2.rows[0].cells
        h2[0].text = 'Escenario'
        h2[1].text = 'Mesada'
        h2[2].text = 'Tasa'
        
        r1 = t2.add_row().cells; r1[0].text="HOY"; r1[1].text=f"${liquidacion_actual['mesada']:,.0f}"; r1[2].text=f"{liquidacion_actual['tasa']:.2f}%"
        r2 = t2.add_row().cells; r2[0].text="FUTURO"; r2[1].text=f"${proyeccion['mesada_futura']:,.0f}"; r2[2].text=f"{proyeccion['tasa_futura']:.2f}%"
        
        doc.add_heading('4.1 Análisis Financiero', level=2)
        doc.add_paragraph(f"Inversión Total: ${proyeccion['inversion_total']:,.0f}")
        doc.add_paragraph(f"Aumento Mensual: ${proyeccion['delta_mesada']:,.0f}")
        
        if proyeccion['delta_mesada'] > 0:
            p = doc.add_paragraph(f"Recuperación de Inversión: {proyeccion['anios_recuperacion']:.1f} Años")
            p.runs[0].bold = True

    # Buffer
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# ==========================================
# 2. INTERFAZ DE USUARIO (SIDEBAR)
# ==========================================
with st.sidebar:
    st.header("👤 Perfil")
    nombre = st.text_input("Nombre", "Usuario")
    genero = st.radio("Género", ["Masculino", "Femenino"])
    fecha_nac = st.date_input("Fecha Nacimiento", value=date(1975, 1, 1))
    
    st.markdown("---")
    st.header("⚙️ Configuración")
    aplicar_tope = st.checkbox("Aplicar tope 1800 Semanas", value=True, help="Límite legal estándar. Desmarcar para buscar 80% con más semanas.")
    
    st.markdown("---")
    if st.button("🔄 Reiniciar"):
        st.session_state.df_crudo = None
        st.session_state.df_final = None
        st.rerun()

# ==========================================
# 3. LÓGICA PRINCIPAL
# ==========================================

# FASE 1: CARGA
if st.session_state.df_final is None:
    st.info("📂 Carga tu Historia Laboral (PDF).")
    uploaded_file = st.file_uploader("Subir PDF Colpensiones", type="pdf")

    if uploaded_file:
        if st.session_state.df_crudo is None:
            st.session_state.df_crudo = extraer_tabla_cruda(uploaded_file)
        
        df_disp = st.session_state.df_crudo
        if df_disp is not None and not df_disp.empty:
            st.success("✅ Archivo leído.")
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
        else: st.warning("PDF vacío/Imagen.")

# FASE 2: VISUALIZACIÓN COMPLETA
else:
    df = st.session_state.df_final
    liq = LiquidadorPension(df, genero, fecha_nac)
    
    # --- CÁLCULOS GLOBALES PREVIOS ---
    hoy = datetime.now().date()
    edad_dias = (hoy - fecha_nac).days
    edad_anios = edad_dias / 365.25
    req_edad = 62 if genero == "Masculino" else 57
    req_semanas = 1300 if genero == "Masculino" else calcular_semanas_minimas_mujeres(hoy.year)
    total_sem = df['Semanas'].sum()
    ultimo_ibc = df['IBC'].iloc[-1]
    
    # Diccionarios para el reporte
    datos_usuario = {
        "nombre": nombre, "genero": genero, 
        "edad_texto": f"{int(edad_anios)} Años y {int((edad_anios%1)*12)} Meses"
    }
    
    estatus_dict = {
        "cumple_todo": (edad_anios >= req_edad and total_sem >= req_semanas),
        "cumple_edad": edad_anios >= req_edad,
        "cumple_semanas": total_sem >= req_semanas,
        "falta_edad": f"{int(max(0, req_edad - edad_anios))} años",
        "falta_semanas": max(0, req_semanas - total_sem)
    }

    # IBL
    ibl_10, det_10 = liq.calcular_ibl_indexado("ultimos_10")
    ibl_vida, det_vida = liq.calcular_ibl_indexado("toda_vida")
    ibl_def = max(ibl_10, ibl_vida)
    origen_ibl = "Últimos 10 Años" if ibl_10 >= ibl_vida else "Toda la Vida"
    
    # Mesada Actual
    mesada, tasa, info = liq.calcular_tasa_reemplazo_797(ibl_def, total_sem, datetime.now().year, aplicar_tope)
    
    liq_actual_dict = {
        "semanas": total_sem, "ibl": ibl_def, "origen_ibl": origen_ibl,
        "tasa": tasa, "mesada": mesada
    }
    
    # Variable placeholder para proyección
    proyeccion_dict = None

    # --- PESTAÑAS VISUALES ---
    tab1, tab2 = st.tabs(["📊 DIAGNÓSTICO ACTUAL", "💰 PROYECCIÓN & INVERSIÓN"])
    
    # === PESTAÑA 1: DIAGNÓSTICO ===
    with tab1:
        st.markdown(f"### Análisis de {nombre}")
        
        # 1. Semáforo
        if estatus_dict['cumple_todo']:
            st.markdown(f"""<div class="status-card-ok"><h3>✅ DERECHO ADQUIRIDO</h3>Edad: {datos_usuario['edad_texto']} | Semanas: {total_sem:,.0f}</div>""", unsafe_allow_html=True)
        else:
            msg = f"Faltan: {estatus_dict['falta_edad']} edad" if not estatus_dict['cumple_edad'] else "Edad OK"
            msg += f" | {estatus_dict['falta_semanas']:,.0f} semanas" if not estatus_dict['cumple_semanas'] else " | Semanas OK"
            st.markdown(f"""<div class="status-card-warning"><h3>⚠️ EN CONSTRUCCIÓN</h3>{msg}</div>""", unsafe_allow_html=True)

        st.divider()

        # 2. Resumen Métricas
        c1, c2, c3 = st.columns(3)
        c1.metric("Semanas Totales", f"{total_sem:,.2f}")
        c2.metric("Último Salario", f"${ultimo_ibc:,.0f}")
        c3.metric("Requisito Semanas", f"{int(req_semanas)}")
        
        # 3. IBL y Soportes (AQUÍ ESTÁ LO QUE FALTABA)
        st.divider()
        colL, colR = st.columns(2)
        with colL:
            st.markdown("#### Base de Liquidación (IBL)")
            st.info(f"IBL Favorable: **{origen_ibl}** (${ibl_def:,.0f})")
            st.bar_chart(pd.DataFrame({"Monto":[ibl_10, ibl_vida]}, index=["10 Años", "Toda Vida"]), color="#2E86C1")
        
        with colR:
            st.markdown("#### 📄 Soportes Técnicos")
            # Estos expander son los que restauramos
            with st.expander(f"Ver Detalle Últimos 10 Años (${ibl_10:,.0f})"):
                st.dataframe(det_10)
            with st.expander(f"Ver Detalle Toda la Vida (${ibl_vida:,.0f})"):
                st.dataframe(det_vida)

        # 4. Resultado Final Hoy
        st.markdown("---")
        st.markdown(f"### 💵 Pensión Hoy: <span style='color:green'>${mesada:,.0f}</span>", unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        m1.metric("Tasa Reemplazo", f"{tasa:.2f}%")
        m2.metric("Semanas Computadas", f"{info['semanas_usadas']:,.2f}", delta="Tope 1800 Activo" if aplicar_tope and total_sem>1800 else "Sin Tope")

    # === PESTAÑA 2: PROYECCIÓN ===
    with tab2:
        st.markdown("### 🔮 Simulador de Futuro")
        col_conf, col_res = st.columns([1, 2])
        
        # Configuración Proyección
        with col_conf:
            st.markdown("#### Estrategia")
            modo = st.radio("Opción:", ["Cotizar Independiente", "Aporte Extra"])
            if modo.startswith("Cotizar"):
                nuevo_ibc = st.number_input("Nuevo IBC ($)", value=float(ultimo_ibc), step=100000.0)
                base_costo = nuevo_ibc
            else:
                extra = st.number_input("Extra ($)", value=1000000.0, step=100000.0)
                nuevo_ibc = ultimo_ibc + extra
                base_costo = extra
            
            anios = st.slider("Años a cotizar", 1, 15, 5)
            
            # Cálculo de Costos (Visual)
            costo_mes = base_costo * 0.285
            if base_costo > (4 * 1423500): costo_mes += base_costo*0.01
            inv_total = costo_mes * anios * 12
            
            st.markdown(f"""
            <div class="investment-card">
                <b>Costo Mensual:</b> ${costo_mes:,.0f}<br>
                <b>Inversión Total:</b> ${inv_total:,.0f}
            </div>
            """, unsafe_allow_html=True)

        # Resultados Proyección
        with col_res:
            st.markdown("#### Resultado")
            # Generar datos futuros
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
            
            f_mes, f_tas, _ = liq_f.calcular_tasa_reemplazo_797(fi_def, total_fut, datetime.now().year + anios, aplicar_tope)
            
            delta = f_mes - mesada
            roi = (inv_total / delta / 12) if delta > 0 else 0
            
            # Métricas Visuales
            k1, k2, k3 = st.columns(3)
            k1.metric("Nueva Mesada", f"${f_mes:,.0f}", f"+ ${delta:,.0f}")
            k2.metric("Nueva Tasa", f"{f_tas:.2f}%")
            k3.metric("Semanas Futuras", f"{total_fut:,.0f}")
            
            st.markdown("#### Rentabilidad (ROI)")
            if roi > 0:
                st.success(f"✅ Recuperas la inversión en **{roi:.1f} años** de pensionado.")
                st.bar_chart(pd.DataFrame({"Valor": [mesada, f_mes]}, index=["Hoy", "Futuro"]), color="#27AE60")
            else:
                st.error("⚠️ La inversión no aumenta la mesada (posible tope).")

            # Guardar datos para el reporte Word
            proyeccion_dict = {
                "estrategia": f"{modo} por {anios} años (IBC Ref: ${nuevo_ibc:,.0f})",
                "anios": anios,
                "inversion_total": inv_total,
                "mesada_futura": f_mes,
                "tasa_futura": f_tas,
                "delta_mesada": delta,
                "anios_recuperacion": roi
            }

    # --- BOTÓN DE DESCARGA (SIDEBAR) ---
    st.sidebar.markdown("---")
    st.sidebar.header("📄 Informe")
    
    # Se genera el documento con los datos recopilados en tiempo real
    archivo_word = generar_reporte_word(datos_usuario, estatus_dict, liq_actual_dict, proyeccion_dict)
    
    st.sidebar.download_button(
        label="📥 Descargar Reporte (Word)",
        data=archivo_word,
        file_name=f"Estudio_Pensional_{nombre}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
