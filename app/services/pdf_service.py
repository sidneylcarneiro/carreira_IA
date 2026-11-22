"""Serviço de geração de PDFs profissionais.

Gera PDFs separados para o Currículo Adaptado e para a Carta de Apresentação,
renderizando templates Jinja2 (em app/templates/pdf/) e convertendo o HTML para
bytes PDF usando o WeasyPrint.
"""
import os
import re
import unicodedata
from datetime import date

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATES_PDF_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates",
    "pdf",
)

_env = Environment(loader=FileSystemLoader(TEMPLATES_PDF_DIR))


def _slugify(texto: str, default: str = "documento") -> str:
    """Higieniza texto para uso seguro em nomes de arquivo (sem acentos/espaços)."""
    if not texto:
        return default
    # Remove acentos
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    # Mantém apenas letras, números, espaços e hífens; o resto vira espaço
    texto = re.sub(r"[^a-zA-Z0-9\s-]", " ", texto)
    # Espaços e hífens repetidos viram um único hífen
    texto = re.sub(r"\s+", "-", texto)
    texto = re.sub(r"-+", "-", texto).strip("-").lower()
    return texto or default


def _vaga_da_empresa(vaga_data: dict) -> str:
    """Extrai o nome da empresa de vaga_data ({'vaga': {'empresa': ...}})."""
    try:
        return ((vaga_data or {}).get("vaga") or {}).get("empresa") or ""
    except (AttributeError, TypeError):
        return ""


def _paragrafos(texto: str):
    """Divide o texto em parágrafos, respeitando quebras de parágrafo (linha em branco)."""
    texto = (texto or "").strip()
    if not texto:
        return []
    # Separa por uma ou mais linhas em branco
    blocos = re.split(r"\n\s*\n", texto)
    return [b.strip() for b in blocos if b.strip()]


def gerar_pdf_curriculo(curriculo_json: dict, usuario, vaga_data: dict) -> bytes:
    """Renderiza o template do currículo adaptado e retorna os bytes do PDF."""
    template = _env.get_template("curriculo_pdf.html")
    html = template.render(dados=curriculo_json or {})
    return HTML(string=html).write_pdf()


def gerar_pdf_carta(carta_texto: str, usuario, vaga_data: dict) -> bytes:
    """Renderiza o template da carta de apresentação e retorna os bytes do PDF."""
    template = _env.get_template("carta_pdf.html")
    vaga = ((vaga_data or {}).get("vaga")) or {}
    data_atual = date.today().strftime("%d/%m/%Y")
    html = template.render(
        corpo_paragrafos=_paragrafos(carta_texto),
        usuario=usuario,
        vaga=vaga,
        data_atual=data_atual,
    )
    return HTML(string=html).write_pdf()


def nome_arquivo_curriculo(vaga_data: dict) -> str:
    """Retorna o nome do arquivo do currículo: curriculo_<empresa>.pdf."""
    empresa = _slugify(_vaga_da_empresa(vaga_data))
    if empresa == "documento":
        return "curriculo.pdf"
    return f"curriculo_{empresa}.pdf"


def nome_arquivo_carta(vaga_data: dict) -> str:
    """Retorna o nome do arquivo da carta: carta_apresentacao_<empresa>.pdf."""
    empresa = _slugify(_vaga_da_empresa(vaga_data))
    if empresa == "documento":
        return "carta_apresentacao.pdf"
    return f"carta_apresentacao_{empresa}.pdf"
