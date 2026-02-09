import pypdf
from docx import Document
import io

class ResumeParser:
    """
    Service to extract raw text from PDF or DOCX files.
    """
    
    @staticmethod
    def parse_pdf(file_bytes: bytes) -> str:
        pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()

    @staticmethod
    def parse_docx(file_bytes: bytes) -> str:
        doc = Document(io.BytesIO(file_bytes))
        text = "\n".join([para.text for para in doc.paragraphs])
        return text.strip()