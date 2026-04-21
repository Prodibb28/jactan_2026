import pdfplumber

def test_file(fp):
    print(f"=== {fp} === ")
    with pdfplumber.open(fp) as pdf:
        words = pdf.pages[0].extract_words()
        for w in words:
            if "Nivel" in w['text']:
                print(f"{w['text']}: x0={w['x0']:.1f}, top={w['top']:.1f}")

test_file("../backend/pdfs_de_prueba/03:2026.pdf")
