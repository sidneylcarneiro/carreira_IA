"""Serviço de leitura/extração de texto de arquivos de currículo (PDF, DOCX, TXT)."""
import io
from PyPDF2 import PdfReader
from docx import Document


def extrair_texto_pdf(data: bytes) -> str:
    """Extrai o texto de um PDF a partir de seus bytes."""
    reader = PdfReader(io.BytesIO(data))
    paginas = [pagina.extract_text() or "" for pagina in reader.pages]
    return "\n".join(paginas).strip()


def extrair_texto_docx(data: bytes) -> str:
    """Extrai o texto de um arquivo .docx a partir de seus bytes."""
    documento = Document(io.BytesIO(data))
    paragrafos = [p.text for p in documento.paragraphs]
    return "\n".join(paragrafos).strip()


def extrair_texto_txt(data: bytes) -> str:
    """Decodifica um arquivo de texto puro."""
    return data.decode("utf-8", errors="ignore").strip()


def extrair_texto_de_arquivo(nome_arquivo: str, data: bytes) -> str:
    """
    Extrai o texto de um arquivo de currículo com base na extensão.

    Suporta PDF, DOCX e TXT. Levanta ValueError para formatos não suportados.
    """
    if not nome_arquivo or "." not in nome_arquivo:
        raise ValueError("Não foi possível identificar o formato do arquivo.")

    extensao = nome_arquivo.rsplit(".", 1)[-1].lower()

    if extensao == "pdf":
        return extrair_texto_pdf(data)
    if extensao == "docx":
        return extrair_texto_docx(data)
    if extensao == "txt":
        return extrair_texto_txt(data)

    raise ValueError("Formato não suportado. Envie um arquivo PDF, DOCX ou TXT.")