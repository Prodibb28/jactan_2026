import pdfplumber

def test_file(fp):
    print(f"=== {fp} ===")
    with pdfplumber.open(fp) as pdf:
        text = pdf.pages[0].extract_text(layout=True)
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if "Costo por opcion tarifaria" in line or "COT" in line:
                print(f"[{i}]: {line}")
                if i+1 < len(lines): print(f"[{i+1}]: {lines[i+1]}")
                if i+2 < len(lines): print(f"[{i+2}]: {lines[i+2]}")

test_file("../backend/pdfs_de_prueba/02:2026.pdf")
test_file("../backend/pdfs_de_prueba/03:2026.pdf")
