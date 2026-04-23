from io import BytesIO
from pathlib import Path
import tempfile
import unicodedata

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
import pdfplumber
import csv
import re
import pypdfium2 as pdfium
import os
import io
import aiofiles

from database import SessionLocal, Documento, RegistroTarifario, ParametrosOperador, CargosGlobales, DocumentoEnerbit, RegistroTarifarioEnerbit
from pydantic import BaseModel
from typing import Optional
from routes.invoices import router as invoices_router

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PRESENTATION_PDF = BASE_DIR / "presentacion.pdf"
LOGOS_DIR = BASE_DIR / "logos_or"
PDF_RENDER_SCALE = 2
VALID_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
TEXT_FONT_CANDIDATES = [
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf"),
]
TEXT_FONT_BOLD_CANDIDATES = [
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
]
PLACEHOLDER_STYLES = {
    "logo": {
        "type": "image",
        "padding": (-40, -20, 40, 55),
        "background": (255, 255, 255),
    },
    "or": {
        "type": "text",
        "padding": (-4, -3, 56, 3),
        "background": (255, 255, 255),
        "color": (89, 63, 145),
        "max_font_size": 24,
        "vertical_align": "top",
    },
    "med_d": {
        "type": "text",
        "padding": (-2, -2, 2, 2),
        "background": (255, 255, 255),
        "color": (96, 96, 96),
        "font_size": 50,
    },
    "med_si": {
        "type": "text",
        "padding": (-2, -2, 2, 2),
        "background": (255, 255, 255),
        "color": (96, 96, 96),
        "font_size": 50,
    },
    "gc_value": {
        "type": "text",
        "padding": (-60, -24, 80, 24),
        "background": (255, 255, 255),
        "color": (107, 63, 160),
        "font_size": 90,
        "align": "center",
        "font_weight": "bold",
        "text_offset_y": -25,
    },
    "porcentaje_value": {
        "type": "text",
        "padding": (-20, -12, 20, 12),
        "background": (83, 53, 128),
        "color": (255, 255, 255),
        "font_size": 90,
        "align": "center",
        "font_weight": "bold",
    },
    "ahorro_value": {
        "type": "text",
        "padding": (-18, -16, 18, 16),
        "background": (83, 53, 128),
        "color": (255, 255, 255),
        "font_size": 90,
        "align": "center",
        "font_weight": "bold",
    },
    "simulacion_image": {
        "type": "image",
        "background": None,
        "padding": (-360, -180, 520, 260),
        "radius": 0,
        "inner_padding": 0,
    },
}

class ParametrosOperadorBase(BaseModel):
    operador_red: str
    anio: int
    fijabit_hogar: Optional[float] = None
    fijabit_comercial: Optional[float] = None

class CargosGlobalesBase(BaseModel):
    anio: int
    medida_directa_hogar: Optional[float] = None
    medida_directa_zc: Optional[float] = None
    medida_semi_indirecta_zc: Optional[float] = None
    medida_directa_comercial: Optional[float] = None
    medida_semi_indirecta_comercial: Optional[float] = None

app = FastAPI()

app.include_router(invoices_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/presentacion/reemplazar")
async def reemplazar_presentacion(
    file: Optional[UploadFile] = File(None),
    simulacion: UploadFile = File(...),
    logo: str = Form(...),
    med_d: str = Form(...),
    med_si: str = Form(...),
    gc_value: str = Form(...),
    porcentaje_value: str = Form(...),
    ahorro_value: str = Form(...),
):
    temp_file_path: Optional[Path] = None

    if file is not None:
        filename = file.filename or "presentacion.pdf"
        if file.content_type not in {"application/pdf", "application/octet-stream"} and not filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="El archivo enviado debe ser un PDF.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file_path = Path(temp_file.name)

        async with aiofiles.open(temp_file_path, "wb") as temp_pdf:
            await temp_pdf.write(await file.read())

        pdf_path = temp_file_path
        source_name = Path(filename).stem
    else:
        pdf_path = DEFAULT_PRESENTATION_PDF
        source_name = DEFAULT_PRESENTATION_PDF.stem

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="No se encontro el PDF base para reemplazar.")

    simulacion_filename = simulacion.filename or "simulacion"
    simulacion_suffix = Path(simulacion_filename).suffix.lower()
    simulacion_content_type = simulacion.content_type or ""
    if not simulacion_content_type.startswith("image/") and simulacion_suffix not in VALID_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="El campo simulacion debe ser una imagen valida.")

    simulacion_bytes = await simulacion.read()
    if not simulacion_bytes:
        raise HTTPException(status_code=400, detail="La imagen de simulacion no puede estar vacia.")

    logo_path = find_logo_path(logo)

    try:
        output_pdf = build_presentacion_pdf(
            pdf_path=pdf_path,
            replacements={
                "med_d": med_d,
                "med_si": med_si,
                "gc_value": gc_value,
                "porcentaje_value": porcentaje_value,
                "ahorro_value": ahorro_value,
            },
            logo_path=logo_path,
            simulacion_bytes=simulacion_bytes,
        )
    finally:
        if temp_file_path is not None and temp_file_path.exists():
            temp_file_path.unlink()

    response_filename = f"{source_name}_reemplazado.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{response_filename}"'}
    return StreamingResponse(output_pdf, media_type="application/pdf", headers=headers)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def parse_decimal(text):
    if text is None: return None
    text = text.strip()
    if text.upper() == 'N/A': return 0.0
    try:
        return float(text.replace(',', '.').replace('$', '').strip())
    except (ValueError, TypeError, AttributeError):
        return None

def format_number_with_thousands(text: str) -> str:
    cleaned_text = re.sub(r'(?i)\+\s*iva', '', text or '')
    cleaned_text = cleaned_text.replace('$', '').strip()
    cleaned_text = re.sub(r'\s+', '', cleaned_text)
    if not cleaned_text:
        return ""

    normalized_text = cleaned_text
    if ',' in normalized_text and '.' in normalized_text:
        if normalized_text.rfind(',') > normalized_text.rfind('.'):
            normalized_text = normalized_text.replace('.', '').replace(',', '.')
        else:
            normalized_text = normalized_text.replace(',', '')
    elif normalized_text.count('.') > 1:
        normalized_text = normalized_text.replace('.', '')
    elif normalized_text.count(',') > 1:
        normalized_text = normalized_text.replace(',', '')
    elif ',' in normalized_text:
        whole_part, decimal_part = normalized_text.split(',', 1)
        if decimal_part.isdigit() and len(decimal_part) == 3 and whole_part.isdigit():
            normalized_text = f"{whole_part}{decimal_part}"
        else:
            normalized_text = normalized_text.replace(',', '.')
    elif '.' in normalized_text:
        whole_part, decimal_part = normalized_text.split('.', 1)
        if decimal_part.isdigit() and len(decimal_part) == 3 and whole_part.isdigit():
            normalized_text = f"{whole_part}{decimal_part}"

    try:
        number = float(normalized_text)
    except ValueError:
        return cleaned_text

    if number.is_integer():
        return f"{int(number):,}".replace(',', '.')

    formatted_number = f"{number:,.2f}"
    return formatted_number.replace(',', '_').replace('.', ',').replace('_', '.')

def normalize_placeholder_name(text: str) -> str:
    normalized_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r'[^a-z0-9_]+', '', normalized_text.lower())

def resolve_font_path(candidates: list[Path]) -> Optional[Path]:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None

FONT_PATH = resolve_font_path(TEXT_FONT_CANDIDATES)
BOLD_FONT_PATH = resolve_font_path(TEXT_FONT_BOLD_CANDIDATES)

def get_font(size: int, weight: str = "regular"):
    font_path = BOLD_FONT_PATH if weight == "bold" and BOLD_FONT_PATH is not None else FONT_PATH
    if font_path is None:
        return ImageFont.load_default()
    return ImageFont.truetype(str(font_path), size=size)

def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_height: int, max_size: int):
    if FONT_PATH is None:
        return ImageFont.load_default()

    for size in range(max_size, 9, -1):
        font = get_font(size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        if (right - left) <= max_width and (bottom - top) <= max_height:
            return font

    return get_font(10)

def find_logo_path(logo_name: str) -> Path:
    if not LOGOS_DIR.exists():
        raise HTTPException(status_code=500, detail="La carpeta logos_or no existe.")

    normalized_logo_name = logo_name.strip().lower()
    for candidate in sorted(LOGOS_DIR.iterdir()):
        if not candidate.is_file():
            continue
        if candidate.name.lower() == normalized_logo_name or candidate.stem.lower() == normalized_logo_name:
            return candidate

    raise HTTPException(
        status_code=404,
        detail=f"No se encontro un logo para '{logo_name}' dentro de logos_or.",
    )

def locate_placeholders(pdf_path: Path, placeholders: set[str]) -> dict[str, list[dict]]:
    found_placeholders = {placeholder: [] for placeholder in placeholders}
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            for word in page.extract_words():
                normalized_word = normalize_placeholder_name(word["text"])
                if normalized_word in found_placeholders:
                    found_placeholders[normalized_word].append({
                        "page_index": page_index,
                        "x0": word["x0"],
                        "x1": word["x1"],
                        "top": word["top"],
                        "bottom": word["bottom"],
                        "text": word["text"],
                    })
    return found_placeholders

def expand_box(box: tuple[int, int, int, int], padding: tuple[int, int, int, int], image_size: tuple[int, int]) -> tuple[int, int, int, int]:
    left = max(0, box[0] + padding[0])
    top = max(0, box[1] + padding[1])
    right = min(image_size[0], box[2] + padding[2])
    bottom = min(image_size[1], box[3] + padding[3])
    return left, top, right, bottom

def draw_text_placeholder(page_image: Image.Image, placeholder_name: str, occurrence: dict, value: str):
    style = PLACEHOLDER_STYLES[placeholder_name]
    x0 = round(occurrence["x0"] * PDF_RENDER_SCALE)
    x1 = round(occurrence["x1"] * PDF_RENDER_SCALE)
    top = round(occurrence["top"] * PDF_RENDER_SCALE)
    bottom = round(occurrence["bottom"] * PDF_RENDER_SCALE)
    box = expand_box((x0, top, x1, bottom), style["padding"], page_image.size)

    draw = ImageDraw.Draw(page_image)
    draw.rectangle(box, fill=style["background"])

    text_value = value
    if placeholder_name == "or" and occurrence["text"].startswith("(") and occurrence["text"].endswith(")"):
        text_value = f"({value})"
    elif placeholder_name in {"med_d", "med_si"}:
        stripped_value = format_number_with_thousands(value)
        if not stripped_value.startswith("$"):
            stripped_value = f"${stripped_value}"
        if "+ IVA" not in stripped_value.upper():
            stripped_value = f"{stripped_value} + IVA"
        text_value = stripped_value
    elif placeholder_name == "gc_value":
        stripped_value = format_number_with_thousands(value)
        if stripped_value and not stripped_value.startswith("$"):
            stripped_value = f"${stripped_value}"
        text_value = stripped_value
    elif placeholder_name == "porcentaje_value":
        stripped_value = value.strip()
        if "%" not in stripped_value:
            stripped_value = f"{stripped_value}%"
        text_value = stripped_value
    elif placeholder_name == "ahorro_value":
        text_value = format_number_with_thousands(value)

    max_width = max(10, box[2] - box[0])
    max_height = max(10, box[3] - box[1])
    if "font_size" in style:
        font = get_font(style["font_size"], style.get("font_weight", "regular"))
    else:
        font = fit_font(draw, text_value, max_width, max_height, style["max_font_size"])
    text_left, text_top, text_right, text_bottom = draw.textbbox((0, 0), text_value, font=font)
    text_width = text_right - text_left
    text_height = text_bottom - text_top
    if style.get("align") == "center":
        text_x = box[0] + max(0, (max_width - text_width) // 2) - text_left
    else:
        text_x = box[0] - text_left

    if style.get("vertical_align") == "top":
        text_y = box[1] - text_top
    else:
        text_y = box[1] + max(0, (max_height - text_height) // 2) - text_top
    text_y += style.get("text_offset_y", 0)

    draw.text(
        (text_x, text_y),
        text_value,
        fill=style["color"],
        font=font,
    )

def draw_logo_placeholder(page_image: Image.Image, occurrence: dict, logo_path: Path):
    style = PLACEHOLDER_STYLES["logo"]
    x0 = round(occurrence["x0"] * PDF_RENDER_SCALE)
    x1 = round(occurrence["x1"] * PDF_RENDER_SCALE)
    top = round(occurrence["top"] * PDF_RENDER_SCALE)
    bottom = round(occurrence["bottom"] * PDF_RENDER_SCALE)
    box = expand_box((x0, top, x1, bottom), style["padding"], page_image.size)

    draw = ImageDraw.Draw(page_image)
    draw.rectangle(box, fill=style["background"])

    with Image.open(logo_path) as logo_image:
        logo = logo_image.convert("RGBA")
        target_width = max(1, box[2] - box[0])
        target_height = max(1, box[3] - box[1])
        resized_logo = logo.copy()
        resized_logo.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)

        paste_x = box[0] + (target_width - resized_logo.width) // 2
        paste_y = box[1] + (target_height - resized_logo.height) // 2
        page_image.paste(resized_logo, (paste_x, paste_y), resized_logo)

def draw_simulacion_image(page_image: Image.Image, occurrence: dict, image_bytes: bytes):
    style = PLACEHOLDER_STYLES["simulacion_image"]
    x0 = round(occurrence["x0"] * PDF_RENDER_SCALE)
    x1 = round(occurrence["x1"] * PDF_RENDER_SCALE)
    top = round(occurrence["top"] * PDF_RENDER_SCALE)
    bottom = round(occurrence["bottom"] * PDF_RENDER_SCALE)
    box = expand_box((x0, top, x1, bottom), style["padding"], page_image.size)

    try:
        with Image.open(BytesIO(image_bytes)) as raw_image:
            simulation_image = ImageOps.exif_transpose(raw_image).convert("RGBA")
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="No fue posible leer la imagen de simulacion.") from exc

    target_width = max(1, box[2] - box[0])
    target_height = max(1, box[3] - box[1])
    fitted_image = ImageOps.fit(
        simulation_image,
        (target_width, target_height),
        method=Image.Resampling.LANCZOS,
    )

    page_image.paste(fitted_image, (box[0], box[1]), fitted_image)

def build_presentacion_pdf(
    pdf_path: Path,
    replacements: dict[str, str],
    logo_path: Path,
    simulacion_bytes: bytes,
) -> BytesIO:
    required_placeholders = set(replacements.keys()) | {"logo", "simulacion_image"}
    found_placeholders = locate_placeholders(pdf_path, required_placeholders)
    missing_placeholders = [name for name, matches in found_placeholders.items() if not matches]
    if missing_placeholders:
        missing_values = ", ".join(sorted(missing_placeholders))
        raise HTTPException(
            status_code=400,
            detail=f"No se encontraron estos placeholders en el PDF: {missing_values}.",
        )

    pdf_document = pdfium.PdfDocument(str(pdf_path))
    rendered_pages = []

    try:
        for page in pdf_document:
            rendered_pages.append(page.render(scale=PDF_RENDER_SCALE).to_pil().convert("RGB"))
    finally:
        pdf_document.close()

    for occurrence in found_placeholders["logo"]:
        draw_logo_placeholder(rendered_pages[occurrence["page_index"]], occurrence, logo_path)

    simulacion_occurrence = found_placeholders["simulacion_image"][0]
    draw_simulacion_image(
        rendered_pages[simulacion_occurrence["page_index"]],
        simulacion_occurrence,
        simulacion_bytes,
    )

    for placeholder_name, placeholder_value in replacements.items():
        for occurrence in found_placeholders[placeholder_name]:
            draw_text_placeholder(
                rendered_pages[occurrence["page_index"]],
                placeholder_name,
                occurrence,
                placeholder_value,
            )

    output = BytesIO()
    rendered_pages[0].save(
        output,
        format="PDF",
        save_all=True,
        append_images=rendered_pages[1:],
        resolution=144.0,
    )
    output.seek(0)
    return output

filas_objetivo = [
    "Nivel 1 OR propietario activos",
    "Nivel 1 propiedad activos compartida",
    "Nivel 1 cliente propietario activos",
    "Nivel 2",
    "Nivel 3"
]

# Mapeo de nombres del PDF → estándar unificado (coincide con CSV)
NIVEL_ESTANDAR = {
    "Nivel 1 OR propietario activos": "CU1 Prop, OR",
    "Nivel 1 propiedad activos compartida": "CU12 Prop, Mixta",
    "Nivel 1 cliente propietario activos": "CU1 Prop, Cliente",
    "Nivel 2": "CU2",
    "Nivel 3": "CU3"
}

@app.post("/upload-pdf/")
async def upload_pdf(
    file: UploadFile = File(...), 
    operador_red: str = Form(...),
    mes: int = Form(...),
    anio: int = Form(...),
    overwrite: bool = Form(False),
    db: Session = Depends(get_db)
):
    temp_file_path = f"temp_{file.filename}"
    async with aiofiles.open(temp_file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    # 1. Verificar si ya existe para sobreescribirlo
    doc_existente = db.query(Documento).filter(
        Documento.operador_red == operador_red,
        Documento.mes == mes,
        Documento.anio == anio
    ).first()

    sobreescrito = False
    if doc_existente:
        if not overwrite:
            # Si existe y no hemos dado el aval de sobreescribir, abortamos con 409 Conflict
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise HTTPException(status_code=409, detail="conflict_existing_record")
        else:
            db.delete(doc_existente)
            db.commit() # Aplicamos el borrado en cascada
            sobreescrito = True

    # 2. Crear e insertar el Documento Padre nuevo
    nuevo_documento = Documento(
        filename=file.filename,
        operador_red=operador_red,
        mes=mes,
        anio=anio
    )
    db.add(nuevo_documento)
    db.flush() # Importante: Obtenemos el ID del documento recién insertado pero sin confirmar la transacción global
    
    resultados = []
    try:
        with pdfplumber.open(temp_file_path) as pdf:
            page = pdf.pages[0]
            text = page.extract_text(layout=True)
            words = page.extract_words()
            lineas = text.split('\n')
            
            pr_words, g_words, t_words, r_words = [], [], [], []
            for w in words:
                if 120 < w['top'] < 200:
                    val = parse_decimal(w['text'])
                    if val is not None:
                        if 135 <= w['x0'] <= 160: g_words.append({"val": val, "top": w['top']})
                        elif 165 <= w['x0'] <= 185: t_words.append({"val": val, "top": w['top']})
                        elif 190 < w['x0'] < 220: pr_words.append({"val": val, "top": w['top']})
                        elif 265 <= w['x0'] <= 295: r_words.append({"val": val, "top": w['top']})
            
            pr_words.sort(key=lambda x: x['top'])
            pr_opciones = {"Nivel 1": None, "Nivel 2": None, "Nivel 3": None, "Nivel 4": None}
            if len(pr_words) >= 1: pr_opciones["Nivel 1"] = pr_words[0]["val"]
            if len(pr_words) >= 2: pr_opciones["Nivel 2"] = pr_words[1]["val"]
            if len(pr_words) >= 3: pr_opciones["Nivel 3"] = pr_words[2]["val"]
            if len(pr_words) >= 4: pr_opciones["Nivel 4"] = pr_words[3]["val"]

            g_words.sort(key=lambda x: x['top'])
            t_words.sort(key=lambda x: x['top'])
            r_words.sort(key=lambda x: x['top'])

            gen_global = g_words[0]["val"] if g_words else None
            stn_global = t_words[0]["val"] if t_words else None
            res_global = r_words[0]["val"] if r_words else None
            
            ot_opciones = {"Nivel 1": None, "Nivel 2": None, "Nivel 3": None}
            
            for i, linea in enumerate(lineas):      
                # Buscamos la mini-tabla de Costo Opcional Tarifario (OT)
                if "Costo por opcion tarifaria" in linea:
                    if i + 1 < len(lineas):
                        ops = re.findall(r'\b\d{1,3}(?:[.,]\d{2,3})*\b|N/A', lineas[i+1])
                        if len(ops) >= 3:
                            ot_opciones["Nivel 1"] = parse_decimal(ops[0]) if ops[0] != "N/A" else 0.0
                            ot_opciones["Nivel 2"] = parse_decimal(ops[1]) if ops[1] != "N/A" else 0.0
                            ot_opciones["Nivel 3"] = parse_decimal(ops[2]) if ops[2] != "N/A" else 0.0

            encontrados = set()
            for linea in lineas:
                for objetivo in filas_objetivo:
                    if linea.strip().startswith(objetivo) and objetivo not in encontrados:
                        numeros = re.findall(r'\b\d{1,3}(?:[.,]\d{2,3})*\b', linea)
                        if len(numeros) >= 4:
                            # Recuperar el OT por Nivel correspondiente
                            ot_val = None
                            pr_val = None
                            if "Nivel 1" in objetivo: 
                                ot_val = ot_opciones["Nivel 1"]
                                pr_val = pr_opciones["Nivel 1"]
                            elif "Nivel 2" in objetivo: 
                                ot_val = ot_opciones["Nivel 2"]
                                pr_val = pr_opciones["Nivel 2"]
                            elif "Nivel 3" in objetivo: 
                                ot_val = ot_opciones["Nivel 3"]
                                pr_val = pr_opciones["Nivel 3"]
                            elif "Nivel 4" in objetivo:
                                pr_val = pr_opciones["Nivel 4"]

                            nombre_estandar = NIVEL_ESTANDAR.get(objetivo, objetivo)

                            # 2. Guardar en Base de Datos por cada fila encontrada, asociándolos al documento
                            nuevo_registro = RegistroTarifario(
                                documento_id=nuevo_documento.id,
                                fila=nombre_estandar,
                                gen=gen_global,
                                stn=stn_global,
                                res=res_global,
                                d_val=parse_decimal(numeros[-4]),
                                c_val=parse_decimal(numeros[-3]),
                                cu_val=parse_decimal(numeros[-2]),
                                cot_val=parse_decimal(numeros[-1]),
                                ot_val=ot_val,
                                pr_val=pr_val
                            )
                            db.add(nuevo_registro)
                            
                            # Para devolverlo al vuelo a la app
                            resultados.append({
                                "operador_red": operador_red,
                                "mes": mes,
                                "anio": anio,
                                "fila": nombre_estandar,
                                "gen": gen_global, "stn": stn_global, "res": res_global,
                                "d_val": parse_decimal(numeros[-4]), "c_val": parse_decimal(numeros[-3]),
                                "cu_val": parse_decimal(numeros[-2]), "cot_val": parse_decimal(numeros[-1]),
                                "ot_val": ot_val,
                                "pr_val": pr_val
                            })
                            encontrados.add(objetivo)

            # Confirmar que tanto el Padre como los Hijos se guarden bien
            db.commit() 
    except Exception as e:
        db.rollback()
        raise e
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    return {"message": "PDF procesado exitosamente", "data": resultados, "sobreescrito": sobreescrito}

@app.get("/registros/")
def get_registros(db: Session = Depends(get_db)):
    # Usamos joinedload para traer el Documento Padre junto con cada Fila y evitar queries N+1
    registros = db.query(RegistroTarifario).options(joinedload(RegistroTarifario.documento)).all()
    
    # Lo aplanamos para que la tabla en React sea fácil de pintar
    resultado = []
    for reg in registros:
        doc = reg.documento
        resultado.append({
            "operador_red": doc.operador_red,
            "mes": doc.mes,
            "anio": doc.anio,
            "fila": reg.fila,
            "gen": reg.gen, "stn": reg.stn, "res": reg.res,
            "pr_val": reg.pr_val,
            "d_val": reg.d_val, "c_val": reg.c_val, "cu_val": reg.cu_val, "cot_val": reg.cot_val,
            "ot_val": reg.ot_val
        })
    return resultado

@app.get("/registros-enerbit/")
def get_registros_enerbit(db: Session = Depends(get_db)):
    registros = db.query(RegistroTarifarioEnerbit).options(joinedload(RegistroTarifarioEnerbit.documento)).all()
    resultado = []
    for reg in registros:
        doc = reg.documento
        resultado.append({
            "operador_red": "enerBit",
            "or_asociado": doc.operador_red,
            "mes": doc.mes,
            "anio": doc.anio,
            "fila": reg.fila,
            "gen": reg.gen, "stn": reg.stn, "res": reg.res,
            "pr_val": reg.pr_val,
            "d_val": reg.d_val, "c_val": reg.c_val, "cu_val": reg.cu_val, "cot_val": reg.cot_val,
            "ot_val": reg.ot_val
        })
    return resultado

@app.get("/dashboard/resumen")
def get_resumen(anio: int, operador_red: str = "Afinia", db: Session = Depends(get_db)):
    """Resumen anual: Diferencia Tarifaria y Favor Cobertura por mes y nivel."""
    # FijaBit del año
    params = db.query(ParametrosOperador).filter(
        ParametrosOperador.anio == anio,
        ParametrosOperador.operador_red == operador_red
    ).first()
    fijabit_hogar = params.fijabit_hogar if params else None
    fijabit_comercial = params.fijabit_comercial if params else None

    # Documentos del año
    docs_afinia = db.query(Documento).filter(Documento.operador_red == operador_red, Documento.anio == anio).all()
    docs_enerbit = db.query(DocumentoEnerbit).filter(DocumentoEnerbit.operador_red == operador_red, DocumentoEnerbit.anio == anio).all()

    # Meses disponibles (unión de ambos)
    meses_set = set()
    for d in docs_afinia:
        meses_set.add(d.mes)
    for d in docs_enerbit:
        meses_set.add(d.mes)

    niveles = ["CU1 Prop, OR", "CU12 Prop, Mixta", "CU1 Prop, Cliente", "CU2", "CU3"]
    resultado = []

    for m in sorted(meses_set):
        doc_af = next((d for d in docs_afinia if d.mes == m), None)
        doc_eb = next((d for d in docs_enerbit if d.mes == m), None)

        afinia_map = {}
        if doc_af:
            for r in db.query(RegistroTarifario).filter(RegistroTarifario.documento_id == doc_af.id).all():
                afinia_map[r.fila] = r

        enerbit_map = {}
        if doc_eb:
            for r in db.query(RegistroTarifarioEnerbit).filter(RegistroTarifarioEnerbit.documento_id == doc_eb.id).all():
                enerbit_map[r.fila] = r

        niveles_data = {}
        for nivel in niveles:
            af = afinia_map.get(nivel)
            eb = enerbit_map.get(nivel)

            cot_or = af.cot_val if af else None
            cot_eb = eb.cot_val if eb else None
            diferencia = round(cot_or - cot_eb, 2) if cot_or is not None and cot_eb is not None else None

            # Favor Cobertura Hogar = G_eB + C_eB - OT_eB - FijaBit_Hogar
            favor_hogar = None
            favor_comercio = None
            pro_hogar = None
            pro_comercio = None
            if eb:
                g = eb.gen or 0
                c = eb.c_val or 0
                ot = eb.ot_val or 0
                base = round(g + c - ot, 2)
                if fijabit_hogar is not None:
                    favor_hogar = round(base - fijabit_hogar, 2)
                    pro_hogar = round(cot_eb - favor_hogar, 2) if cot_eb is not None else None
                if fijabit_comercial is not None:
                    favor_comercio = round(base - fijabit_comercial, 2)
                    pro_comercio = round(cot_eb - favor_comercio, 2) if cot_eb is not None else None

            # Efecto Contribución = Diferencia Tarifaria * 20%
            efecto_contribucion = round(diferencia * 0.20, 2) if diferencia is not None else None

            # Neto Cliente = Favor Cobertura + Diferencia Tarifaria - Efecto Contribución
            neto_hogar = None
            neto_comercio = None
            if all(v is not None for v in [favor_hogar, diferencia, efecto_contribucion]):
                neto_hogar = round(favor_hogar + diferencia - efecto_contribucion, 2)
            if all(v is not None for v in [favor_comercio, diferencia, efecto_contribucion]):
                neto_comercio = round(favor_comercio + diferencia - efecto_contribucion, 2)

            niveles_data[nivel] = {
                "cot_or": cot_or,
                "cot_eb": cot_eb,
                "diferencia_tarifaria": diferencia,
                "efecto_contribucion": efecto_contribucion,
                "favor_cobertura_hogar": favor_hogar,
                "favor_cobertura_comercio": favor_comercio,
                "pro_hogar": pro_hogar,
                "pro_comercio": pro_comercio,
                "neto_hogar": neto_hogar,
                "neto_comercio": neto_comercio
            }

        resultado.append({"mes": m, "niveles": niveles_data})

    return {
        "data": resultado,
        "anio": anio,
        "operador_red": operador_red,
        "fijabit_hogar": fijabit_hogar,
        "fijabit_comercial": fijabit_comercial
    }

# ENDPOINTS PARA PLAN ENERPRO
@app.get("/plan-enerpro/parametros")
def get_parametros_operador(anio: int, operador_red: str, db: Session = Depends(get_db)):
    record = db.query(ParametrosOperador).filter(ParametrosOperador.anio == anio, ParametrosOperador.operador_red == operador_red).first()
    return record

@app.post("/plan-enerpro/parametros")
def save_parametros_operador(data: ParametrosOperadorBase, db: Session = Depends(get_db)):
    record = db.query(ParametrosOperador).filter(ParametrosOperador.anio == data.anio, ParametrosOperador.operador_red == data.operador_red).first()
    if record:
        record.fijabit_hogar = data.fijabit_hogar
        record.fijabit_comercial = data.fijabit_comercial
    else:
        record = ParametrosOperador(
            operador_red=data.operador_red,
            anio=data.anio,
            fijabit_hogar=data.fijabit_hogar,
            fijabit_comercial=data.fijabit_comercial
        )
        db.add(record)
    db.commit()
    return {"status": "success"}

@app.get("/plan-enerpro/globales")
def get_cargos_globales(anio: int, db: Session = Depends(get_db)):
    record = db.query(CargosGlobales).filter(CargosGlobales.anio == anio).first()
    return record

@app.post("/plan-enerpro/globales")
def save_cargos_globales(data: CargosGlobalesBase, db: Session = Depends(get_db)):
    record = db.query(CargosGlobales).filter(CargosGlobales.anio == data.anio).first()
    if record:
        record.medida_directa_hogar = data.medida_directa_hogar
        record.medida_directa_zc = data.medida_directa_zc
        record.medida_semi_indirecta_zc = data.medida_semi_indirecta_zc
        record.medida_directa_comercial = data.medida_directa_comercial
        record.medida_semi_indirecta_comercial = data.medida_semi_indirecta_comercial
    else:
        record = CargosGlobales(
            anio=data.anio,
            medida_directa_hogar=data.medida_directa_hogar,
            medida_directa_zc=data.medida_directa_zc,
            medida_semi_indirecta_zc=data.medida_semi_indirecta_zc,
            medida_directa_comercial=data.medida_directa_comercial,
            medida_semi_indirecta_comercial=data.medida_semi_indirecta_comercial
        )
        db.add(record)
    db.commit()
    return {"status": "success"}

# --- EXTRACCION CSV (enerBit) ---
def parse_decimal_csv(text):
    """Convierte formato colombiano (punto=miles, coma=decimal) a float."""
    if text is None:
        return None
    text = text.strip()
    if not text or text == "N/A":
        return None
    try:
        cleaned = text.replace('.', '').replace(',', '.')
        return float(cleaned)
    except (ValueError, TypeError):
        return None

@app.post("/upload-csv/")
async def upload_csv(
    file: UploadFile = File(...),
    operador_red: str = Form(...),
    mes: int = Form(...),
    anio: int = Form(...),
    overwrite: bool = Form(False),
    db: Session = Depends(get_db)
):
    content = await file.read()
    text = content.decode('latin-1')
    reader = csv.reader(io.StringIO(text), delimiter=';')
    rows = list(reader)

    # 1. Extraer T y R
    t_val = None
    r_val = None
    for row in rows:
        row_text = ';'.join(row)
        if 'Componentes transversales' in row_text:
            for i, cell in enumerate(row):
                if 'T:' in cell:
                    t_val = parse_decimal_csv(row[i + 1]) if i + 1 < len(row) else None
                if 'R:' in cell:
                    r_val = parse_decimal_csv(row[i + 1]) if i + 1 < len(row) else None
            break

    # 2. Encontrar bloque de Afinia dentro del CSV de enerBit
    operador_header_row = None
    for i, row in enumerate(rows):
        if len(row) > 8 and 'afinia' in row[8].strip().lower():
            operador_header_row = i
            break
    
    if operador_header_row is None:
        raise HTTPException(status_code=400, detail="No se encontró la sección de Afinia en el CSV.")

    # 3. Verificar si ya existe para sobreescribir
    or_asociado = "Afinia"
    doc_existente = db.query(DocumentoEnerbit).filter(
        DocumentoEnerbit.operador_red == or_asociado,
        DocumentoEnerbit.mes == mes,
        DocumentoEnerbit.anio == anio
    ).first()

    sobreescrito = False
    if doc_existente:
        if not overwrite:
            raise HTTPException(status_code=409, detail="conflict_existing_record")
        else:
            db.delete(doc_existente)
            db.commit()
            sobreescrito = True

    # 4. Crear Documento Padre enerBit
    nuevo_documento = DocumentoEnerbit(
        filename=file.filename,
        operador_red=or_asociado,
        mes=mes,
        anio=anio
    )
    db.add(nuevo_documento)
    db.flush()

    # 5. Extraer filas de datos y guardar
    niveles_objetivo = ["CU1 Prop, OR", "CU12 Prop, Mixta", "CU1 Prop, Cliente", "CU2", "CU3"]
    resultados = []
    data_start = operador_header_row + 2

    for row in rows[data_start:]:
        nivel = row[0].strip() if len(row) > 0 else ""
        if nivel.lower().startswith("mercado"):
            break
        if nivel in niveles_objetivo:
            g_val    = parse_decimal_csv(row[8])  if len(row) > 8  else None
            d_val    = parse_decimal_csv(row[9])  if len(row) > 9  else None
            pr_val   = parse_decimal_csv(row[10]) if len(row) > 10 else None
            c_cot    = parse_decimal_csv(row[11]) if len(row) > 11 else None
            cu_cot   = parse_decimal_csv(row[12]) if len(row) > 12 else None
            cot_csv  = parse_decimal_csv(row[13]) if len(row) > 13 else None

            # Transformaciones
            c_val = round(c_cot - cot_csv, 2) if c_cot is not None and cot_csv is not None else None
            cu_val = round(cu_cot - cot_csv, 2) if cu_cot is not None and cot_csv is not None else None
            ot_val = cot_csv
            cot_val = cu_cot

            nuevo_registro = RegistroTarifarioEnerbit(
                documento_id=nuevo_documento.id,
                fila=nivel,
                gen=g_val, stn=t_val, res=r_val,
                d_val=d_val, pr_val=pr_val, c_val=c_val,
                cu_val=cu_val, cot_val=cot_val, ot_val=ot_val
            )
            db.add(nuevo_registro)

            resultados.append({
                "fila": nivel, "gen": g_val, "stn": t_val, "res": r_val,
                "d_val": d_val, "pr_val": pr_val, "c_val": c_val,
                "cu_val": cu_val, "cot_val": cot_val, "ot_val": ot_val
            })

    db.commit()
    return {"message": "CSV procesado exitosamente", "data": resultados, "sobreescrito": sobreescrito}
