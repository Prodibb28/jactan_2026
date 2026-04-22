from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
import pdfplumber
import re
import os
import aiofiles

from database import SessionLocal, Documento, RegistroTarifario, ParametrosOperador, CargosGlobales
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
                            ot_opciones["Nivel 1"] = parse_decimal(ops[0]) if ops[0] != "N/A" else None
                            ot_opciones["Nivel 2"] = parse_decimal(ops[1]) if ops[1] != "N/A" else None
                            ot_opciones["Nivel 3"] = parse_decimal(ops[2]) if ops[2] != "N/A" else None

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

                            # 2. Guardar en Base de Datos por cada fila encontrada, asociándolos al documento
                            nuevo_registro = RegistroTarifario(
                                documento_id=nuevo_documento.id,
                                fila=objetivo,
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
                                "fila": objetivo,
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