import pdfplumber
def test_file(fp):
    with pdfplumber.open(fp) as pdf:
        text = pdf.pages[0].extract_text(layout=True)
        lines = text.split('\n')
        for j in range(5, 20):
            print(f"[{j}]: {lines[j]}")
test_file("../backend/pdfs_de_prueba/02:2026.pdf")
