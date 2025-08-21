import pandas as pd
import pdfplumber
import docx


def extract_text(file) -> str:
    name = file.name.lower()
    if name.endswith(".txt") or name.endswith(".md"):
        return file.read().decode("utf-8", errors="ignore")
    elif name.endswith(".docx"):
        d = docx.Document(file)
        return "\n".join(p.text for p in d.paragraphs)
    elif name.endswith(".pdf"):
        text = []
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text.append(page.extract_text() or "")
        return "\n".join(text)
    elif name.endswith(".csv"):
        df = pd.read_csv(file)
        return df.to_csv(index=False)
    elif name.endswith(".xlsx"):
        df = pd.read_excel(file)
        return df.to_csv(index=False)
    return ""
