import pdfplumber

def test_file(fp):
    print(f"=== {fp} === ")
    with pdfplumber.open(fp) as pdf:
        text = pdf.pages[0].extract_text(layout=True)
        lines = text.split('\n')
        
        # Searching heuristically
        for i, line in enumerate(lines):
            if "PR" in line or "P R" in line or "G" in line or "T" in line:
                # We specifically look for 'PR', 'PR:', 'G y T'
                if "PR" in line or "P R" in line or "G y T" in line or "P.R." in line:
                    start = max(0, i - 1)
                    end = min(len(lines), i + 2)
                    print(f"--- MATCH {i} ---")
                    for j in range(start, end):
                        print(f"[{j}]: {lines[j]}")

test_file("../backend/pdfs_de_prueba/02:2026.pdf")
test_file("../backend/pdfs_de_prueba/03:2026.pdf")
