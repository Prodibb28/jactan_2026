import json
import os
import base64

import openai
from fastapi import APIRouter, HTTPException, UploadFile, File

router = APIRouter()


@router.post("/invoice-extractor/")
async def invoice_extractor(file: UploadFile = File(...)):
    SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
    SUPPORTED_PDF_TYPE = "application/pdf"
    content_type = file.content_type or ""
    filename = file.filename or ""
    is_pdf = content_type == SUPPORTED_PDF_TYPE or filename.lower().endswith(".pdf")
    is_image = content_type in SUPPORTED_IMAGE_TYPES or any(
        filename.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")
    )

    if not is_pdf and not is_image:
        raise HTTPException(status_code=400, detail="Unsupported file type. Upload a PDF or an image (JPG, PNG, WEBP, GIF).")

    raw_bytes = await file.read()

    image_media_types_by_extension = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = content_type
    if is_image:
        _, extension = os.path.splitext(filename.lower())
        media_type = image_media_types_by_extension.get(extension, "image/jpeg")
        if content_type in SUPPORTED_IMAGE_TYPES:
            media_type = "image/jpeg" if content_type == "image/jpg" else content_type
    image_b64 = base64.standard_b64encode(raw_bytes).decode("utf-8")
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    print(f"Uploading file to OpenAI: filename={filename}, content_type={content_type}, media_type={media_type}, size={len(raw_bytes)} bytes")

    uploaded_file = client.files.create(
        file=(filename, raw_bytes, content_type), purpose="assistants"
    )

    message = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "file",
                        "file": {"file_id": uploaded_file.id},
                    },
                    {
                        "type": "text",
                        "text": """
                            You are a data extraction assistant specialized in Colombian electricity bills (facturas de energía).

                            Extract the following fields from this electricity bill and return them as a JSON object with EXACTLY this structure:

                            {
                                "estrato_clasificacion": number,
                                "direccion": string,
                                "consumo_mes_anterior_kwh": number,
                                "dias_facturados": number,
                                "total_mes": number,
                                "promedio_consumo_diario_kwh": number,
                                "costo_unitario": {
                                    "G": number,
                                    "T": number,
                                    "PR": number,
                                    "R": number,
                                    "D": number,
                                    "C": number,
                                    "CU": number
                                },
                                "tipo_cliente": string,
                                "factor_multiplo": number
                            }

                            Field extraction rules:

                            1. "estrato_clasificacion": Extract the value next to "Estrato/Clasificación" in the user data section and take only the numeric part.

                            2. "consumo_mes_anterior_kwh": In the "Consumo de los últimos 6 meses" bar chart,
                            there are 7 bars shown (6 previous months + current month).
                            Extract ONLY the second-to-last bar value (the month immediately before the current billing period).
                            Do NOT return the current month's consumption.

                            3. "dias_facturados": Extract the number next to "Días Facturados" in the meter reading section.

                            4. "costo_unitario": Extract each component from the "Costo unitario $/kWh" breakdown table:
                            - G (Generación)
                            - T (Transmisión)
                            - PR (Pérdidas)
                            - R (Restricciones)
                            - D (Distribución)
                            - C (Comercialización)
                            - CU (Costo Unitario total)
                            All values should be numbers (decimals allowed).

                            Return ONLY the JSON object, no explanation, no markdown, no extra text.
                            If a field cannot be found, set its value to null.

                            5. "direccion": Extract the full address from the "Dirección de suministro" field in the user data section
                            6. "total_mes": Extract the total amount to pay for the month from the "Total Mes" field, removing any currency symbols and formatting, and return it as a number.
                            7. "promedio_consumo_diario_kwh": Extract from "Promedio consumo diario" and return it as a number (remove "kWh" and any formatting).
                            8. "tipo_cliente": from the "Estrato/Clasificación" field, if it contains the word "Resid" classify as "residencial", if not classify as "comercial"
                            9. "factor_multiplo": from the "Factor Múltiplo"
                        """,
                    },
                ],
            }
        ],
    )
    extracted_text = message.choices[0].message.content
    return json.loads(extracted_text)
