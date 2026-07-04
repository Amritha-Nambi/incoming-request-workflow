import io
import pdfplumber
import docx
from fastapi import UploadFile


async def extract_text(file: UploadFile) -> str:
    filename = file.filename.lower()
    content = await file.read()

    if filename.endswith((".txt", ".eml")):
        return content.decode("utf-8", errors="ignore")
    if filename.endswith(".pdf"):
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    if filename.endswith(".docx"):
        d = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in d.paragraphs)

    raise ValueError(f"Unsupported file type: {filename}")
