import pdfplumber

def test_file(fp):
    print(f"=== {fp} ===")
    with pdfplumber.open(fp) as pdf:
        words = pdf.pages[0].extract_words()
        
        pr_words = []
        for w in words:
            # PR column is theoretically x0=201.5. Let's cast a net [190, 220]
            if 190 < w['x0'] < 220 and w['top'] > 120 and w['top'] < 300:
                text = w['text'].replace(',', '.')
                try:
                    val = float(text)
                    pr_words.append(w)
                except ValueError:
                    pass
        
        pr_words.sort(key=lambda x: x['top'])
        for w in pr_words:
            print(f"PR Found: {w['text']} at Top: {w['top']}")

test_file("../backend/pdfs_de_prueba/02:2026.pdf")
test_file("../backend/pdfs_de_prueba/03:2026.pdf")
