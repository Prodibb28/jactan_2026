from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
import pdfplumber
import csv
import re
import os
import io
import aiofiles

from database import SessionLocal, Documento, RegistroTarifario, ParametrosOperador, CargosGlobales, DocumentoEnerbit, RegistroTarifarioEnerbit
from pydantic import BaseModel
from typing import Optional

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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