"""
Script de extracción de tarifas desde CSV para Afinia.
Lee el CSV de publicación de tarifas EnerBit y extrae:
  - Componentes transversales: T y R
  - Datos de la sección Afinia: G, D, PR, C+COT, CU+COT, COT
  Para los niveles: CU1 Prop OR, CU12 Prop Mixta, CU1 Prop Cliente, CU2, CU3
"""
import csv
import sys
import os

def parse_decimal(text):
    """Convierte texto con formato colombiano (coma decimal, punto para miles) a float."""
    if text is None:
        return None
    text = text.strip()
    if not text or text == "N/A":
        return None
    try:
        # Quitar puntos de miles y convertir coma decimal a punto
        cleaned = text.replace('.', '').replace(',', '.')
        return float(cleaned)
    except (ValueError, TypeError):
        return None

def extract_afinia_from_csv(filepath):
    """Extrae los datos de Afinia y transversales del CSV de tarifas."""
    
    with open(filepath, 'r', encoding='latin-1') as f:
        reader = csv.reader(f, delimiter=';')
        rows = list(reader)
    
    # --- 1. Extraer T y R (Componentes Transversales) ---
    t_val = None
    r_val = None
    for row in rows:
        row_text = ';'.join(row)
        if 'Componentes transversales' in row_text:
            for i, cell in enumerate(row):
                if 'T:' in cell:
                    t_val = parse_decimal(row[i + 1]) if i + 1 < len(row) else None
                if 'R:' in cell:
                    r_val = parse_decimal(row[i + 1]) if i + 1 < len(row) else None
            break
    
    print(f"{'='*70}")
    print(f"  COMPONENTES TRANSVERSALES")
    print(f"{'='*70}")
    print(f"  T (Transmisión):   {t_val}")
    print(f"  R (Restricciones): {r_val}")
    print()

    # --- 2. Encontrar el bloque de Afinia ---
    # Estructura del CSV:
    #   Row N:   Mercado; ; Pereira; ; ...; ; Afinia; ; Cf...
    #   Row N+1: Nivel de Tensión; ; G; D; PR; C+COT; CU+COT; COT; G; D; PR; C+COT; CU+COT; COT
    #   Row N+2: CU1 Prop, OR; ; val; val; ...  (datos Pereira cols 2-7, Afinia cols 8-13)
    
    afinia_header_row = None
    cf_afinia = None
    
    for i, row in enumerate(rows):
        # Buscar la celda que contenga "Afinia" en las columnas de la derecha (col 8)
        if len(row) > 8 and 'afinia' in row[8].strip().lower():
            afinia_header_row = i
            # Extraer Cf ($/Fact) de Afinia (columna 12)
            cf_afinia = parse_decimal(row[12]) if len(row) > 12 else None
            break
    
    if afinia_header_row is None:
        print("ERROR: No se encontró la sección de Afinia en el CSV.")
        return None
    
    # --- 3. Extraer filas de datos (empiezan 2 filas después del header: saltar "Nivel de Tensión") ---
    niveles_objetivo = ["CU1 Prop, OR", "CU12 Prop, Mixta", "CU1 Prop, Cliente", "CU2", "CU3"]
    
    resultados = []
    data_start = afinia_header_row + 2  # +1 = header columnas, +2 = primera fila de datos
    
    for row in rows[data_start:]:
        nivel = row[0].strip() if len(row) > 0 else ""
        
        # Si encontramos otro bloque "Mercado", paramos
        if nivel.lower().startswith("mercado"):
            break
        
        # Verificar si es uno de nuestros niveles objetivo
        if nivel in niveles_objetivo:
            # Columnas Afinia: [8]=G, [9]=D, [10]=PR, [11]=C+COT, [12]=CU+COT, [13]=COT
            g_val   = parse_decimal(row[8])  if len(row) > 8  else None
            d_val   = parse_decimal(row[9])  if len(row) > 9  else None
            pr_val  = parse_decimal(row[10]) if len(row) > 10 else None
            c_cot   = parse_decimal(row[11]) if len(row) > 11 else None
            cu_cot  = parse_decimal(row[12]) if len(row) > 12 else None
            cot_val = parse_decimal(row[13]) if len(row) > 13 else None
            
            resultados.append({
                "nivel": nivel,
                "G": g_val,
                "T": t_val,
                "R": r_val,
                "D": d_val,
                "PR": pr_val,
                "C+COT": c_cot,
                "CU+COT": cu_cot,
                "COT": cot_val
            })
    
    # --- 4. Imprimir resultados ---
    print(f"{'='*70}")
    print(f"  SECCIÓN AFINIA  |  Cf ($/Fact): {cf_afinia}")
    print(f"{'='*70}")
    print(f"  {'Nivel':<22} {'G':>10} {'D':>10} {'PR':>10} {'C+COT':>10} {'CU+COT':>10} {'COT':>10}")
    print(f"  {'-'*82}")
    
    for r in resultados:
        print(f"  {r['nivel']:<22} {r['G']:>10} {r['D']:>10} {r['PR']:>10} {r['C+COT']:>10} {r['CU+COT']:>10} {r['COT']:>10}")
    
    print(f"\n  Transversales compartidos: T={t_val}, R={r_val}")
    print(f"{'='*70}")
    
    return {
        "transversales": {"T": t_val, "R": r_val},
        "cf_afinia": cf_afinia,
        "registros": resultados
    }

if __name__ == "__main__":
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backend", "excel_pdf",
        "20260421 publicación tarifas(Publicacion_Tarifas_Enerbit COT).csv"
    )
    
    if not os.path.exists(csv_path):
        print(f"Archivo no encontrado: {csv_path}")
        sys.exit(1)
    
    print(f"Leyendo: {os.path.basename(csv_path)}\n")
    data = extract_afinia_from_csv(csv_path)
