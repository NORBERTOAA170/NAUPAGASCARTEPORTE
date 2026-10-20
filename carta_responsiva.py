from datetime import datetime, time, date
import time as time_module
from zoneinfo import ZoneInfo
import os
import json
import requests
import uuid
import tempfile
import streamlit as st
from PIL import Image

# Librerías de mapas, QR y PDF
try:
    from geopy.geocoders import Nominatim
    from geopy.distance import geodesic
    GEOPY_DISPONIBLE = True
except ImportError:
    GEOPY_DISPONIBLE = False

try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    FPDF_DISPONIBLE = False

try:
    import qrcode
    QRCODE_DISPONIBLE = True
except ImportError:
    QRCODE_DISPONIBLE = False

# ================= CONFIGURACIÓN DE LA PÁGINA =================
st.set_page_config(
    page_title="NAUPAGAS - Módulo Carta Porte 3.1",
    page_icon="logo.jpg",
    layout="wide"
)

MASTER_PASSWORD = "NAUPA2026"
ARCHIVO_HISTORIAL_JSON = "historial_naupagas.json"
ARCHIVO_FOLIO_JSON = "folio_naupagas.json"

# ================= FUNCIONES DE PERSISTENCIA Y FOLIOS =================
def cargar_historial_disco():
    if os.path.exists(ARCHIVO_HISTORIAL_JSON):
        try:
            with open(ARCHIVO_HISTORIAL_JSON, "r", encoding="utf-8") as f:
                datos = json.load(f)
                for item in datos:
                    if "fecha_dt" in item and isinstance(item["fecha_dt"], str):
                        try:
                            item["fecha_dt"] = datetime.strptime(item["fecha_dt"], "%Y-%m-%d").date()
                        except:
                            item["fecha_dt"] = datetime.now().date()
                return datos
        except Exception:
            return []
    return []

def guardar_historial_disco(historial):
    try:
        datos_serializables = []
        for item in historial:
            item_copia = item.copy()
            if "fecha_dt" in item_copia and isinstance(item_copia["fecha_dt"], date):
                item_copia["fecha_dt"] = item_copia["fecha_dt"].strftime("%Y-%m-%d")
            datos_serializables.append(item_copia)
        
        with open(ARCHIVO_HISTORIAL_JSON, "w", encoding="utf-8") as f:
            json.dump(datos_serializables, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error al guardar historial: {e}")

def obtener_siguiente_folio():
    folio_num = 1
    if os.path.exists(ARCHIVO_FOLIO_JSON):
        try:
            with open(ARCHIVO_FOLIO_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                folio_num = data.get("ultimo_folio", 0) + 1
        except:
            folio_num = 1
    try:
        with open(ARCHIVO_FOLIO_JSON, "w", encoding="utf-8") as f:
            json.dump({"ultimo_folio": folio_num}, f)
    except:
        pass
    return f"{folio_num:07d}"

# Inicializar estados en la sesión
if "auth_naupagas" not in st.session_state:
    st.session_state.auth_naupagas = False

if "historial_naupagas" not in st.session_state:
    st.session_state.historial_naupagas = cargar_historial_disco()

if "ultimo_registro_hash_naupagas" not in st.session_state:
    st.session_state.ultimo_registro_hash_naupagas = None

if "registro_bloqueado_naupagas" not in st.session_state:
    st.session_state.registro_bloqueado_naupagas = False

# ================= CATÁLOGO LOCAL DE C.P. VERIFICADO (MÉXICO) =================
CATALOGO_LOCAL_CP = {
    "91400": {"colonia": "Perote Centro", "municipio": "Perote", "estado": "Veracruz", "pais": "México"},
    "91403": {"colonia": "El Sabinal", "municipio": "Perote", "estado": "Veracruz", "pais": "México"},
    "91405": {"colonia": "Fovissste", "municipio": "Perote", "estado": "Veracruz", "pais": "México"},
    "91285": {"colonia": "Tenextepec", "municipio": "Perote", "estado": "Veracruz", "pais": "México"},
    "91000": {"colonia": "Xalapa Enríquez Centro", "municipio": "Xalapa", "estado": "Veracruz", "pais": "México"},
    "91190": {"colonia": "Ánimas", "municipio": "Xalapa", "estado": "Veracruz", "pais": "México"},
    "91110": {"colonia": "Badillo", "municipio": "Xalapa", "estado": "Veracruz", "pais": "México"},
    "91700": {"colonia": "Veracruz Centro", "municipio": "Veracruz", "estado": "Veracruz", "pais": "México"},
    "72000": {"colonia": "Puebla Centro", "municipio": "Puebla", "estado": "Puebla", "pais": "México"},
    "72100": {"colonia": "La Paz", "municipio": "Puebla", "estado": "Puebla", "pais": "México"},
    "90000": {"colonia": "Tlaxcala de Xicohténcatl Centro", "municipio": "Tlaxcala", "estado": "Tlaxcala", "pais": "México"},
    "90300": {"colonia": "Tlaxco Centro", "municipio": "Tlaxco", "estado": "Tlaxcala", "pais": "México"},
    "54680": {"colonia": "Teoloyucan Centro", "municipio": "Teoloyucan", "estado": "Estado de México", "pais": "México"},
    "54789": {"colonia": "Santa Cruz", "municipio": "Tepotzotlán", "estado": "Estado de México", "pais": "México"},
    "54600": {"colonia": "Tepotzotlán Centro", "municipio": "Tepotzotlán", "estado": "Estado de México", "pais": "México"},
    "54000": {"colonia": "Tlalnepantla Centro", "municipio": "Tlalnepantla de Baz", "estado": "Estado de México", "pais": "México"},
    "55000": {"colonia": "Ecatepec de Morelos Centro", "municipio": "Ecatepec de Morelos", "estado": "Estado de México", "pais": "México"},
    "54900": {"colonia": "Tultitlán de Ocampo Centro", "municipio": "Tultitlán", "estado": "Estado de México", "pais": "México"},
    "01000": {"colonia": "San Ángel", "municipio": "Álvaro Obregón", "estado": "Ciudad de México", "pais": "México"},
    "06000": {"colonia": "Centro", "municipio": "Cuauhtémoc", "estado": "Ciudad de México", "pais": "México"},
    "15000": {"colonia": "Federal", "municipio": "Venustiano Carranza", "estado": "Ciudad de México", "pais": "México"},
    "42000": {"colonia": "Pachuca de Soto Centro", "municipio": "Pachuca de Soto", "estado": "Hidalgo", "pais": "México"},
    "42188": {"colonia": "San Antonio El Desmonte", "municipio": "Pachuca de Soto", "estado": "Hidalgo", "pais": "México"},
    "43960": {"colonia": "Apan Centro", "municipio": "Apan", "estado": "Hidalgo", "pais": "México"}
}

@st.cache_data(show_spinner=False)
def consultar_cp_mexico(cp):
    cp = str(cp).strip()
    if not cp or len(cp) != 5 or not cp.isdigit():
        return {"colonia": "", "municipio": "", "estado": "", "pais": "México"}
    
    if cp in CATALOGO_LOCAL_CP:
        return CATALOGO_LOCAL_CP[cp]
    
    try:
        url = f"https://api.zippopotam.us/MX/{cp}"
        resp = requests.get(url, timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            places = data.get("places", [])
            if places:
                colonia = places[0].get("place name", "")
                estado = places[0].get("state", "")
                return {
                    "colonia": colonia,
                    "municipio": estado,
                    "estado": estado,
                    "pais": "México"
                }
    except Exception:
        pass

    return {"colonia": "", "municipio": "", "estado": "", "pais": "México"}

def calcular_distancia_km(origen_str, destino_str):
    if not GEOPY_DISPONIBLE:
        return None
    try:
        geolocator = Nominatim(user_agent="naupagas_carta_porte_app")
        loc_origen = geolocator.geocode(f"{origen_str}, Mexico")
        loc_destino = geolocator.geocode(f"{destino_str}, Mexico")
        
        if loc_origen and loc_destino:
            coords_origen = (loc_origen.latitude, loc_origen.longitude)
            coords_destino = (loc_destino.latitude, loc_destino.longitude)
            distancia_recta = geodesic(coords_origen, coords_destino).km
            distancia_carretera = round(distancia_recta * 1.27, 1)
            return distancia_carretera
    except:
        return None
    return None

def safe_str(val):
    if val is None:
        return ""
    return str(val).encode('latin-1', 'replace').decode('latin-1')

def generar_qr_tempfile(contenido):
    if not QRCODE_DISPONIBLE:
        return None
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=3,
            border=1,
        )
        qr.add_data(contenido)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(tmp.name, format='PNG')
        tmp.close()
        return tmp.name
    except Exception:
        return None

def generar_pdf(d):
    qr_path = None
    try:
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        
        if os.path.exists("logo.jpg"):
            try:
                pdf.image("logo.jpg", 10, 10, 25)
            except:
                pass
                
        pdf.set_font("helvetica", "B", 14)
        pdf.cell(0, 8, safe_str("NAUPAGAS S.A. DE C.V."), align="C", ln=True)
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 6, safe_str("COMPLEMENTO CARTA PORTE 3.1 - TRÁNSITO FEDERAL"), align="C", ln=True)
        pdf.set_font("helvetica", "", 8)
        
        folio_val = d.get('folio', '0000001')
        pdf.cell(0, 5, safe_str(f"FOLIO: {folio_val} | Fecha de Emisión: {d.get('fecha_registro', '')} | IDCCP: {d.get('idccp', '')}"), align="C", ln=True)
        pdf.ln(4)

        def seccion_pdf(titulo):
            pdf.set_fill_color(220, 225, 230)
            pdf.set_font("helvetica", "B", 9)
            pdf.cell(0, 6, safe_str(f"  {titulo}"), fill=True, ln=True)
            pdf.ln(2)

        # 1. Datos del Emisor
        seccion_pdf("1. DATOS DEL EMISOR Y PERMISOS SCT")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(95, 5, safe_str(f"Empresa / Razón Social: {d.get('nombre_emisor', '')}"), ln=0)
        pdf.cell(95, 5, safe_str(f"RFC Emisor: {d.get('rfc_emisor', '')}"), ln=1)
        pdf.cell(95, 5, safe_str(f"Tipo Permiso SCT: {d.get('tipo_permiso_sct', '')}"), ln=0)
        pdf.cell(95, 5, safe_str(f"Número Permiso SCT: {d.get('num_permiso_sct', '')}"), ln=1)
        pdf.ln(3)

        # 2. Datos del Operador / Chofer
        seccion_pdf("2. DATOS DEL OPERADOR / CHOFER (FIGURA TRANSPORTE)")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(95, 5, safe_str(f"Chofer: {d.get('nombre_chofer', '')}"), ln=0)
        pdf.cell(95, 5, safe_str(f"RFC Chofer: {d.get('rfc_chofer', '')}"), ln=1)
        pdf.cell(95, 5, safe_str(f"Tipo de Licencia: {d.get('tipo_licencia', '')}"), ln=0)
        pdf.cell(95, 5, safe_str(f"Número de Licencia: {d.get('num_licencia', '')}"), ln=1)
        pdf.ln(3)

        # 3. Unidad y Seguro
        seccion_pdf("3. DATOS DE LA UNIDAD Y SEGURO DE RESPONSABILIDAD")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(95, 5, safe_str(f"Unidad: {d.get('tipo_unidad', '')} - Eco: {d.get('eco_unidad', '')}"), ln=0)
        pdf.cell(95, 5, safe_str(f"Placas: {d.get('placas', '')}"), ln=1)
        pdf.cell(95, 5, safe_str(f"Marca/Modelo: {d.get('marca_modelo', '')} (Cap: {d.get('capacidad', '')})"), ln=0)
        pdf.cell(95, 5, safe_str(f"Aseguradora: {d.get('aseguradora', '')} | Póliza: {d.get('num_poliza', '')}"), ln=1)
        pdf.ln(3)

        # 4. Origen y Destino
        seccion_pdf("4. RUTA DE TRÁNSITO (ORIGEN Y DESTINO)")
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(18, 5, safe_str("ORIGEN:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(100, 5, safe_str(f"{d.get('nombre_origen', '')}"), ln=0)
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(12, 5, safe_str("RFC:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, safe_str(f"{d.get('rfc_origen', '')}"), ln=1)
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(28, 5, safe_str("Fecha de Salida:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, safe_str(f"{d.get('fecha_salida', '')}"), ln=1)
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(18, 5, safe_str("Dirección:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.multi_cell(0, 5, safe_str(f"{d.get('dir_origen', '')}"))
        pdf.ln(2)

        pdf.set_font("helvetica", "B", 8)
        pdf.cell(18, 5, safe_str("DESTINO:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(100, 5, safe_str(f"{d.get('nombre_destino', '')}"), ln=0)
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(12, 5, safe_str("RFC:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        rfc_dest_val = d.get('rfc_destino', '') if d.get('rfc_destino', '').strip() else "S/N (Público General)"
        pdf.cell(0, 5, safe_str(f"{rfc_dest_val}"), ln=1)
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(28, 5, safe_str("Llegada Estimada:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, safe_str(f"{d.get('fecha_llegada', '')}"), ln=1)
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(18, 5, safe_str("Dirección:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.multi_cell(0, 5, safe_str(f"{d.get('dir_destino', '')}"))
        pdf.ln(2)

        pdf.set_font("helvetica", "B", 8)
        pdf.cell(42, 5, safe_str("Distancia Total Estimada:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, safe_str(f"{d.get('distancia_km', '')}"), ln=1)
        pdf.ln(3)

        # 5. Mercancía SAT
        seccion_pdf("5. DESCRIPCIÓN Y CLAVES SAT DE LA MERCANCÍA")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, safe_str(f"Producto: {d.get('desc_mercancia', '')} | Clave SAT: {d.get('clave_prod_sat', '')}"), ln=1)
        pdf.cell(95, 5, safe_str(f"Cantidad: {d.get('cantidad_mercancia', '')} {d.get('clave_unidad_sat', '')}"), ln=0)
        pdf.cell(95, 5, safe_str(f"Peso Total: {d.get('peso_mercancia', '')}"), ln=1)
        pdf.ln(4)

        # 6. SECCIÓN DE VALIDACIÓN Y CÓDIGO QR
        seccion_pdf("6. VALIDACIÓN Y VERIFICACIÓN OPERATIVA")
        
        enlace_qr = "https://loginda.siat.sat.gob.mx/nidp/app/login?id=ciec&sid=0&option=credential&sid=0&target=https%3A%2F%2Fverificacfdi.facturaelectronica.sat.gob.mx%2Foauth2%2Fcallback%26scope%3Dmscontribuyente%26code_challenge%3DOfkQhIkHLKEVoxtqW3F3RnIR-cUvRqWF3NEUPFGPvDA%26code_challenge_method%3DS256%26state%3Dg9GL1UZNuFOWSrNeAdEUDRF0RATmkhaCjnz2YOldQ1ZgPIAx8nxrxm6gYV5G1eBLVRAx7nBtdUo9q96KfBfMWfdiXOKoG7l3HcjW78km4jpb7puSzBmW0gYKHClUT5op93de%2BGqEUdwbQXvy%2Bq%2B%2FR08agJatdq5sWNUI6A%2B9qQfRrIcsV6DW5LBStnxqskw4icV%2Fo52LwkOgjZ%2FZHQP46N2Jvxk01CXpItNYWoFSnug9voK72sLWEjiqxv8L6LRvz0Vym3cltWNSE%2FXA%2BzROnWevc0wtsaE5cqW1%2FqvEYcxD5az6nsdVasiSWl%2BeD7bCgZ%2FiFPeFIZhNocmdgS70YS1UQjhlKGue%2B%2BflJAB3XYoQcA0cNDL1QkrNTzd7J0OY8DEiqQBJyoAyC4w62vdIw1AiLzS9THpXuVm6Hd%2FBq56zyLRi9IGBxXn3NyWd0ns9DDGTslm2WAnS2YlAs8rU4Q2Ocu837Vf1T4r3mwOw0ppA6ZpsaAtARRh%2BNjf49BmiCBY%2BVJjbu2fJ60vLdEorUmbkyd7y4DUDqYMK6%2FF3WWs6QFHpX4Thuw2sPvVj8U4duCVgNp6CMkHBkOS2J1zG%2FKFuMNLlJSOeg%2FYSJ%2BgSwyn55wCqlPzpZCqIHwxAFh3gm4wHFWgpOArJZB1hMcrO9T98YF7GQ2uLZNm4vFjxgaU%3D"
        
        qr_path = generar_qr_tempfile(enlace_qr)
        
        if qr_path and os.path.exists(qr_path):
            y_inicial = pdf.get_y()
            try:
                pdf.image(qr_path, x=15, y=y_inicial, w=38)
            except:
                pass
            pdf.set_x(56)
            pdf.set_font("helvetica", "B", 8)
            pdf.cell(0, 4, safe_str(f"Folio: {folio_val} | IDCCP: {d.get('idccp', '')}"), ln=1)
            pdf.set_x(56)
            pdf.set_font("helvetica", "", 7)
            pdf.cell(0, 4, safe_str(f"Estatus de Verificación: ACCESO AL PORTAL DE ACCESO / SAT"), ln=1)
            pdf.set_x(56)
            pdf.cell(0, 4, safe_str(f"Permiso SCT: {d.get('tipo_permiso_sct', '')} - {d.get('num_permiso_sct', '')}"), ln=1)
            pdf.set_x(56)
            pdf.multi_cell(0, 4, safe_str("Este documento ampara el traslado operado con las especificaciones técnicas del catálogo SCT / SAT versión 3.1."))

        y_actual = pdf.get_y()
        y_limite_qr = y_inicial + 40
        if y_actual < y_limite_qr:
            pdf.set_y(y_limite_qr)

        pdf.ln(4)
        pdf.set_font("helvetica", "B", 8)
        pdf.multi_cell(0, 4, safe_str("SI USTED TIENE UNA DUDA O PREGUNTA SOBRE ESTA CARTA PORTE, FAVOR DE CONTACTARNOS AL NÚMERO 282 - 103 - 3534"), align="C")

        out = pdf.output(dest='S')
        if isinstance(out, str):
            return out.encode('latin1')
        return bytes(out)
    except Exception as e:
        pdf_err = FPDF()
        pdf_err.add_page()
        pdf_err.set_font("helvetica", "B", 12)
        pdf_err.cell(0, 10, safe_str(f"Error técnico PDF: {str(e)[:45]}"), ln=True)
        out_err = pdf_err.output(dest='S')
        if isinstance(out_err, str):
            return out_err.encode('latin1')
        return bytes(out_err)
    finally:
        if qr_path and os.path.exists(qr_path):
            try:
                os.remove(qr_path)
            except:
                pass


# ================= AUTENTICACIÓN RÁPIDA =================
if not st.session_state.auth_naupagas:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        if os.path.exists("logo.jpg"):
            st.image("logo.jpg", use_container_width=True)
        else:
            st.markdown("<h1 style='text-align: center;'>🚚</h1>", unsafe_allow_html=True)
            
    st.markdown("<h2 style='text-align: center; color: #004080;'>NAUPAGAS S.A. DE C.V.</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Módulo de Generación de Carta Porte 3.1</p>", unsafe_allow_html=True)
    
    col_a1, col_a2, col_a3 = st.columns([1, 1.2, 1])
    with col_a2:
        pass_input = st.text_input("Contraseña de Acceso", type="password")
        if st.button("Ingresar al Módulo", type="primary", use_container_width=True):
            if pass_input == MASTER_PASSWORD:
                st.session_state.auth_naupagas = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    st.stop()

# ================= MENÚ PRINCIPAL DEL MÓDULO =================
with st.sidebar:
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", use_container_width=True)
    st.markdown("---")
    st.markdown("### 🎛️ Menú de Navegación")
    accion = st.radio("Selecciona una opción:", ["Nueva Carta Porte", "Historial de Documentos"])
    st.markdown("---")
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.auth_naupagas = False
        st.rerun()

ahora_mx = datetime.now(ZoneInfo("America/Mexico_City"))

# ================= FORMULARIO PRINCIPAL =================
if accion == "Nueva Carta Porte":
    st.title("📄 NAUPAGAS - Generador de Carta Porte 3.1")
    st.write("Complete los campos oficiales requeridos para el tránsito seguro de la unidad.")
    st.markdown("---")

    # --- PARTE 1: DATOS DE LA EMPRESA Y REGISTRO SCT ---
    with st.container(border=True):
        st.subheader("1. 🏢 Datos del Emisor y Registro SCT")
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            nombre_emisor = st.text_input("Razón Social / Empresa Emisora", value="NAUPAGAS S.A. de C.V.")
            tipo_permiso_sct = st.selectbox("Tipo de Permiso SCT", ["TPXX00 - Permiso no contemplado", "AUTR02 - Autotransporte Carga Federal", "AUTR01 - Autotransporte Cargas Específicas"])
        with col_e2:
            rfc_emisor = st.text_input("RFC del Emisor", value="NAU1205188P5")
            num_permiso_sct = st.text_input("Número de Permiso SCT", value="TPXX00-NAUPA-2026")

    # --- PARTE 2: DATOS DEL CHOFER ---
    with st.container(border=True):
        st.subheader("2. 👤 Datos del Operador / Chofer (Figura Transporte)")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            nombre_chofer = st.text_input("Nombre Completo del Chofer", placeholder="Juan Pérez Gómez")
            rfc_chofer = st.text_input("RFC del Chofer", placeholder="XAXX010101000")
        with col_c2:
            tipo_licencia = st.selectbox("Tipo de Licencia", ["Federal", "Estatal", "Chofer / Vendedor"])
            num_licencia = st.text_input("Número de Licencia", placeholder="Número oficial")

    # --- PARTE 3: DATOS DE LA UNIDAD ---
    with st.container(border=True):
        st.subheader("3. ⛽ Datos de la Unidad")
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            tipo_unidad = st.selectbox("Tipo de Unidad", ["Autotanque (Pipa)", "Vehículo Repartidor (Cilindrera)"])
            eco_unidad = st.text_input("Número Económico", placeholder="Ej. PIPA-01 o CIL-05")
            placas = st.text_input("Placas", placeholder="Ej. XX-00-XXX")
        with col_u2:
            marca_modelo = st.text_input("Marca / Modelo", placeholder="Ej. Ford F-350 2020")
            if tipo_unidad == "Autotanque (Pipa)":
                capacidad = st.text_input("Capacidad descriptiva de la unidad", value="12,900 Litros", placeholder="Ej. 12,900 Litros")
            else:
                capacidad = st.text_input("Capacidad descriptiva de la unidad", value="Vehículo Repartidor Cilindros", placeholder="Ej. Cilindros 20kg y 30kg")

    # --- PARTE 4: DATOS DE SEGUROS ---
    with st.container(border=True):
        st.subheader("4. 🛡️ Póliza de Seguro")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            aseguradora = st.text_input("Compañía Aseguradora", placeholder="Ej. GNP, Qualitas, AXA")
        with col_s2:
            num_poliza = st.text_input("Número de Póliza", placeholder="Ej. POL-987654321")

    # --- PARTE 5: ORIGEN Y DESTINO (CON OPCIÓN DE VARIOS CLIENTES) ---
    with st.container(border=True):
        st.subheader("5. 📍 Ruta de Tránsito (Origen y Destino)")
        col_origen, col_destino = st.columns(2)

        with col_origen:
            st.markdown("#### 🛫 ORIGEN")
            rfc_origen = st.text_input("RFC Salida / Planta", placeholder="RFC de origen")
            nombre_origen = st.text_input("Nombre / Empresa de Salida", placeholder="Ej. NAUPAGAS Planta Perote")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                f_salida_date = st.date_input("Fecha de Salida", value=ahora_mx.date())
            with col_f2:
                f_salida_time = st.time_input("Hora de Salida", value=ahora_mx.time())
            
            cp_origen = st.text_input("CP Origen", max_chars=5, placeholder="Ej. 91400, 42188")
            info_o = consultar_cp_mexico(cp_origen)
            
            col_o1, col_o2 = st.columns(2)
            with col_o1:
                colonia_origen = st.text_input("Colonia Origen", value=info_o["colonia"], placeholder="Colonia")
                municipio_origen = st.text_input("Municipio Origen", value=info_o["municipio"], placeholder="Municipio")
            with col_o2:
                estado_origen = st.text_input("Estado Origen", value=info_o["estado"], placeholder="Estado")
                pais_origen = st.text_input("País Origen", value=info_o["pais"])
                
            calle_origen = st.text_input("Calle y Número de Salida", placeholder="Ej. Carretera Principal Km 2")

        with col_destino:
            st.markdown("#### 🛬 DESTINO")
            
            # Selector para elegir entre Cliente Específico o Varios Clientes / Ruta General
            tipo_modo_destino = st.radio("Modalidad de Destino:", ["Cliente Específico (C.P. / Domicilio)", "Varios Clientes (Ruta General / Zona Libre)"], horizontal=False)
            
            rfc_destino = st.text_input("RFC Llegada / Cliente (Opcional)", placeholder="RFC de destino (Vacío si es público general)")
            nombre_destino = st.text_input("Nombre / Empresa de Llegada", placeholder="Ej. Cliente Destino o Ruta Múltiple")
            
            col_f3, col_f4 = st.columns(2)
            with col_f3:
                f_llegada_date = st.date_input("Fecha Estimada Llegada", value=ahora_mx.date())
            with col_f4:
                f_llegada_time = st.time_input("Hora Estimada Llegada", value=time(18, 0))

            if tipo_modo_destino == "Cliente Específico (C.P. / Domicilio)":
                cp_destino = st.text_input("CP Destino", max_chars=5, placeholder="Ej. 54680, 91000")
                info_d = consultar_cp_mexico(cp_destino)
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    colonia_destino = st.text_input("Colonia Destino", value=info_d["colonia"], placeholder="Colonia")
                    municipio_destino = st.text_input("Municipio Destino", value=info_d["municipio"], placeholder="Municipio")
                with col_d2:
                    estado_destino = st.text_input("Estado Destino", value=info_d["estado"], placeholder="Estado")
                    pais_destino = st.text_input("País Destino", value=info_d["pais"])
                    
                calle_destino = st.text_input("Calle y Número de Llegada", placeholder="Ej. Av. Principal #10")
                dir_destino_final = f"{calle_destino}, Col. {colonia_destino}, C.P. {cp_destino}, {municipio_destino}, {estado_destino}"
            else:
                # Opción de varios clientes / ruta libre
                zona_libre_destino = st.text_input("Destinos / Zona de Reparto", placeholder="Ej. Banderilla, Xalapa, Las Vigas")
                estado_libre_destino = st.text_input("Estado / Región", placeholder="Ej. Veracruz")
                dir_destino_final = f"Ruta multi-cliente / Zona de entrega: {zona_libre_destino}, {estado_libre_destino}"
                municipio_destino = zona_libre_destino
                estado_destino = estado_libre_destino

    # --- PARTE 6: MERCANCÍA Y CLAVES SAT (DINÁMICA: PIPA O CILINDRERA 20 Y 30 KG) ---
    with st.container(border=True):
        st.subheader("6. 📦 Descripción y Claves SAT de la Mercancía")
        
        if tipo_unidad == "Autotanque (Pipa)":
            st.markdown("#### ⛽ Configuración para Pipa (Medidor Magnetel)")
            opciones_capacidades = [4000.0, 4400.0, 4500.0, 5000.0, 12900.0, 13900.0, 24000.0, "Otra (Personalizada)"]
            
            col_calc1, col_calc2 = st.columns(2)
            with col_calc1:
                capacidad_seleccionada = st.selectbox("Capacidad Total de la Pipa (Litros)", options=opciones_capacidades, index=4)
                if capacidad_seleccionada == "Otra (Personalizada)":
                    capacidad_total_num = st.number_input("Especifique capacidad (Litros)", min_value=0.0, value=10000.0, step=100.0)
                else:
                    capacidad_total_num = float(capacidad_seleccionada)
            with col_calc2:
                porcentaje_magnetel = st.number_input("Porcentaje de Llenado (%) - Magnetel", min_value=0.0, max_value=100.0, value=70.0, step=0.5)

            volumen_calculado_lts = capacidad_total_num * (porcentaje_magnetel / 100.0)
            peso_calculado_kg = volumen_calculado_lts * 0.54

            st.info(f"📊 **Resultado Automático Pipa:** {volumen_calculado_lts:,.2f} Litros | **Peso calculado:** {peso_calculado_kg:,.2f} KG (Factor 0.54)")

            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                cantidad_texto = f"{volumen_calculado_lts:,.2f} Litros"
                st.text_input("Cantidad Calculada", value=cantidad_texto, disabled=True)
                clave_unidad_sat = "LTR - Litros"
            with col_m2:
                desc_mercancia = st.text_input("Descripción / Producto", value="Gas Licuado de Petróleo (Gas LP)")
                clave_prod_sat = st.text_input("Clave Producto SAT", value="15111510 (Gas LP)")
            with col_m3:
                peso_texto = f"{peso_calculado_kg:,.2f} KG"
                st.text_input("Peso Total Calculado", value=peso_texto, disabled=True)

        else:
            st.markdown("#### 🛢️ Configuración para Vehículo Repartidor (Cilindros de 20 kg y 30 kg)")
            
            col_cil1, col_cil2 = st.columns(2)
            with col_cil1:
                cant_cil_20 = st.number_input("Cantidad de Cilindros de 20 KG", min_value=0, value=20, step=1)
            with col_cil2:
                cant_cil_30 = st.number_input("Cantidad de Cilindros de 30 KG", min_value=0, value=15, step=1)

            total_piezas = cant_cil_20 + cant_cil_30
            peso_neto_gas = (cant_cil_20 * 20.0) + (cant_cil_30 * 30.0)

            st.info(f"📊 **Total Envases:** {total_piezas} Cilindros ({cant_cil_20} de 20kg, {cant_cil_30} de 30kg) | **Peso Neto de Gas:** {peso_neto_gas:,.2f} KG")

            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                cantidad_texto = f"{total_piezas} Piezas (Cilindros)"
                st.text_input("Cantidad Calculada", value=cantidad_texto, disabled=True)
                clave_unidad_sat = "H87 - Pieza"
            with col_m2:
                desc_mercancia = st.text_input("Descripción / Producto", value="Gas Licuado de Petróleo (Gas LP en Cilindros)")
                clave_prod_sat = st.text_input("Clave Producto SAT", value="15111510 (Gas LP)")
            with col_m3:
                peso_texto = f"{peso_neto_gas:,.2f} KG"
                st.text_input("Peso Total Neto Gas", value=peso_texto, disabled=True)

    # --- CAMPO DE DISTANCIA ---
    with st.container(border=True):
        st.subheader("📏 Distancia del Viaje")
        km_input = st.text_input("Distancia Estimada (KM)", placeholder="Ej. 275 km (Automático si dejas vacío)")

    st.markdown("---")
    
    str_salida_check = f"{f_salida_date.strftime('%d/%m/%Y')} {f_salida_time.strftime('%H:%M')}"
    actual_hash = f"{eco_unidad.strip().upper()}-{nombre_chofer.strip().upper()}-{str_salida_check}"

    if st.session_state.get("ultimo_registro_hash_naupagas") != actual_hash:
        st.session_state.registro_bloqueado_naupagas = False

    if st.session_state.registro_bloqueado_naupagas:
        st.success("✅ Esta carta ya fue registrada con éxito en el Historial. Modifica la información si deseas generar una nueva.")
        submitted_carta = False
    else:
        submitted_carta = st.button("Generar y Registrar Carta Porte", type="primary", use_container_width=True)

    if submitted_carta:
        if not nombre_chofer or not rfc_chofer or not num_poliza or not desc_mercancia:
            st.warning("⚠️ Por favor completa los datos obligatorios del chofer, póliza y mercancía.")
        else:
            distancia_final = km_input
            if not distancia_final and municipio_origen and municipio_destino:
                km_calculados = calcular_distancia_km(f"{municipio_origen}, {estado_origen}", f"{municipio_destino}, {estado_destino}")
                if km_calculados:
                    distancia_final = f"{km_calculados} km (Aprox.)"
                else:
                    distancia_final = "No calculada"

            str_salida = f"{f_salida_date.strftime('%d/%m/%Y')} {f_salida_time.strftime('%H:%M')}"
            str_llegada = f"{f_llegada_date.strftime('%d/%m/%Y')} {f_llegada_time.strftime('%H:%M')}"

            idccp_generado = f"CCC{str(uuid.uuid4()).upper()[:20]}"
            folio_generado = obtener_siguiente_folio()

            datos_nueva_carta = {
                "folio": folio_generado,
                "idccp": idccp_generado,
                "nombre_emisor": nombre_emisor,
                "rfc_emisor": rfc_emisor,
                "tipo_permiso_sct": tipo_permiso_sct,
                "num_permiso_sct": num_permiso_sct,
                "nombre_chofer": nombre_chofer,
                "rfc_chofer": rfc_chofer,
                "tipo_licencia": tipo_licencia,
                "num_licencia": num_licencia,
                "tipo_unidad": tipo_unidad,
                "eco_unidad": eco_unidad or "S/N",
                "placas": placas,
                "marca_modelo": marca_modelo,
                "capacidad": capacidad,
                "aseguradora": aseguradora,
                "num_poliza": num_poliza,
                "rfc_origen": rfc_origen,
                "nombre_origen": nombre_origen,
                "fecha_salida": str_salida,
                "dir_origen": f"{calle_origen}, Col. {colonia_origen}, C.P. {cp_origen}, {municipio_origen}, {estado_origen}",
                "rfc_destino": rfc_destino,
                "nombre_destino": nombre_destino,
                "fecha_llegada": str_llegada,
                "dir_destino": dir_destino_final,
                "cantidad_mercancia": cantidad_texto,
                "clave_unidad_sat": clave_unidad_sat,
                "desc_mercancia": desc_mercancia,
                "clave_prod_sat": clave_prod_sat,
                "peso_mercancia": peso_texto,
                "distancia_km": distancia_final,
                "fecha_registro": ahora_mx.strftime("%d/%m/%Y %H:%M"),
                "fecha_dt": ahora_mx.date()
            }

            st.session_state.ultimo_registro_hash_naupagas = actual_hash
            st.session_state.registro_bloqueado_naupagas = True
            st.session_state.historial_naupagas.insert(0, datos_nueva_carta)
            guardar_historial_disco(st.session_state.historial_naupagas)
            st.rerun()

elif accion == "Historial de Documentos":
    st.title("📁 NAUPAGAS - Historial de Cartas Generadas")
    st.write("Consulta, filtra por fecha, descarga o elimina registros individuales.")
    st.markdown("---")

    if not st.session_state.historial_naupagas:
        st.info("No hay cartas registradas todavía. Genera una nueva en el menú de la izquierda.")
    else:
        with st.container(border=True):
            st.markdown("### 📅 Filtrar por Rango de Fechas")
            col_f_inicio, col_f_fin = st.columns(2)
            with col_f_inicio:
                fecha_inicio = st.date_input("Desde", value=ahora_mx.date())
            with col_f_fin:
                fecha_fin = st.date_input("Hasta", value=ahora_mx.date())

        if "modo_borrado_naupagas" not in st.session_state:
            st.session_state.modo_borrado_naupagas = False

        with st.expander("🔑 Habilitar Botones de Borrado"):
            pass_del = st.text_input("Ingresa la contraseña para permitir eliminar registros", type="password", key="pass_individual_naupagas")
            if pass_del == MASTER_PASSWORD:
                st.session_state.modo_borrado_naupagas = True
                st.success("Modo borrado activo. Ahora puedes eliminar registros uno por uno.")
            elif pass_del:
                st.error("Contraseña incorrecta.")
                st.session_state.modo_borrado_naupagas = False

        st.markdown("---")
        
        streams_visibles = []
        for idx, carta in enumerate(st.session_state.historial_naupagas):
            f_carta = carta.get("fecha_dt", ahora_mx.date())
            if isinstance(f_carta, str):
                try:
                    f_carta = datetime.strptime(f_carta, "%Y-%m-%d").date()
                except:
                    f_carta = ahora_mx.date()
            if fecha_inicio <= f_carta <= fecha_fin:
                streams_visibles.append((idx, carta))

        if not streams_visibles:
            st.warning(f"No se encontraron cartas registradas entre el {fecha_inicio.strftime('%d/%m/%Y')} y el {fecha_fin.strftime('%d/%m/%Y')}.")
        else:
            indices_a_borrar = None
            for idx, carta in streams_visibles:
                with st.container(border=True):
                    col_h1, col_h2, col_h3 = st.columns([2.5, 3, 2.5])
                    with col_h1:
                        st.write(f"🔢 **Folio:** {carta.get('folio', 'N/A')}")
                        st.write(f"📅 **Fecha:** {carta['fecha_registro']}")
                        st.write(f"⛽ **Unidad:** {carta['tipo_unidad']} ({carta['eco_unidad']})")
                    with col_h2:
                        st.write(f"👤 **Chofer:** {carta['nombre_chofer']}")
                        st.write(f"🛣️ **Ruta:** {carta['nombre_origen']} ➔ {carta['nombre_destino']}")
                        st.write(f"🆔 **IDCCP:** `{carta.get('idccp', 'N/A')}`")
                    with col_h3:
                        pdf_hist_bytes = generar_pdf(carta)
                        st.download_button(
                            label="📄 Descargar PDF SAT",
                            data=pdf_hist_bytes,
                            file_name=f"Naupagas_Folio_{carta.get('folio', '0000001')}.pdf",
                            mime="application/pdf",
                            key=f"dl_naupagas_{idx}"
                        )
                        if st.session_state.modo_borrado_naupagas:
                            if st.button("🗑️ Eliminar Registro", key=f"del_naupagas_{idx}"):
                                indices_a_borrar = idx

            if indices_a_borrar is not None:
                st.session_state.historial_naupagas.pop(indices_a_borrar)
                guardar_historial_disco(st.session_state.historial_naupagas)
                st.rerun()
