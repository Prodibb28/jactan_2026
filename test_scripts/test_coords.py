import pdfplumber

def test_file(fp):
    print(f"=== {fp} === ")
    with pdfplumber.open(fp) as pdf:
        words = pdf.pages[0].extract_words()
        for w in words:
            if w['text'] in ['Generación', 'STN', 'PR:', 'D:', 'Restricciones', 'C/cialización', '314,40', '50,62', '27,18', '334,44', '57,63', '38,72']:
                print(f"{w['text']}: x0={w['x0']:.1f}, top={w['top']:.1f}")

test_file("../backend/pdfs_de_prueba/03:2026.pdf")
