import pdfplumber

def search_pr(fp):
    print(f"=== {fp} ===")
    with pdfplumber.open(fp) as pdf:
        words = pdf.pages[0].extract_words()
        # Find the word closest to "PR: G y T" or just dump all numbers that could be PR
        for w in words:
            if '38,65' in w['text'] or '38.65' in w['text']:
                print("FOUND 38,65:", w)
        # Also let's print all numbers > 10 and < 60 that are near the top
        for w in words:
            if w['top'] > 100 and w['top'] < 300:
                text = w['text'].replace(',', '.')
                try:
                    val = float(text)
                    if 10 < val < 100:
                        print("Possible PR:", w['text'], "at x0:", w['x0'], "top:", w['top'])
                except:
                    pass

search_pr("../backend/pdfs_de_prueba/02:2026.pdf")
search_pr("../backend/pdfs_de_prueba/03:2026.pdf")
