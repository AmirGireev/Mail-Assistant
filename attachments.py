import io

# size limit
MAX_BYTES = 10 * 1024 * 1024


# file to text
def extract(filename: str, ctype: str, data: bytes):
    if not data or len(data) > MAX_BYTES:
        return "", False
    n = filename.lower()
    try:
        # pdf
        if n.endswith(".pdf"):
            from pypdf import PdfReader

            r = PdfReader(io.BytesIO(data))
            text = "\n".join((p.extract_text() or "") for p in r.pages[:10])
            return (text, False) if len(text.strip()) > 50 else ("", True)
        # word
        if n.endswith(".docx"):
            from docx import Document

            d = Document(io.BytesIO(data))
            parts = [p.text for p in d.paragraphs]
            for t in d.tables:
                for row in t.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
            return "\n".join(parts), False
        # excel
        if n.endswith((".xlsx", ".xlsm")):
            from openpyxl import load_workbook

            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            parts = []
            for ws in wb.worksheets[:3]:
                for row in ws.iter_rows(max_row=50, values_only=True):
                    parts.append(" | ".join("" if c is None else str(c) for c in row))
            return "\n".join(parts), False
        # plain text
        if n.endswith((".txt", ".csv", ".md", ".ics", ".html", ".htm")):
            return data.decode("utf-8", errors="ignore"), False
        # image
        if ctype.startswith("image/"):
            return "", True
    except Exception:
        return "", False
    return "", False