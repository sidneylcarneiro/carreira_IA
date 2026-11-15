"""Rotas de gestão da conta: perfil, assinatura/saldo e segurança."""
import os

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from ..dependencies import get_current_user

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def render(template_name: str, request: Request, **context) -> HTMLResponse:
    template = env.get_template(template_name)
    context.setdefault("request", request)
    return template.render(**context)


@router.get("/perfil", response_class=HTMLResponse)
async def perfil_page(request: Request, usuario=Depends(get_current_user)):
    """Página de edição do perfil (Nome, E-mail e Telefone)."""
    return render("perfil.html", request, usuario=usuario)


@router.get("/assinatura", response_class=HTMLResponse)
async def assinatura_page(request: Request, usuario=Depends(get_current_user)):
    """Página de assinatura e saldo de créditos."""
    return render("assinatura.html", request, usuario=usuario)


@router.get("/seguranca", response_class=HTMLResponse)
async def seguranca_page(request: Request, usuario=Depends(get_current_user)):
    """Página de segurança / alteração de senha."""
    return render("seguranca.html", request, usuario=usuario)
