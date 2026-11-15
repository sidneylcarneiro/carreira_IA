"""Rotas de autenticação: cadastro, login, logout e (estrutural) Google OAuth."""
import os

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from authlib.integrations.starlette_client import OAuth

from ..dependencies import get_db
from ..config import settings
from .. import models

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

from jinja2 import Environment, FileSystemLoader  # noqa: E402
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def render(template_name: str, request: Request, **context) -> HTMLResponse:
    template = env.get_template(template_name)
    context.setdefault("request", request)
    return template.render(**context)


# --- Google OAuth (estrutural; ativado apenas com credenciais configuradas) ---
oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render("login.html", request)


@router.get("/registro", response_class=HTMLResponse)
async def registro_page(request: Request):
    return render("registro.html", request)


@router.post("/registro", response_class=HTMLResponse)
async def registrar(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    existente = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if existente:
        return render("registro.html", request, erro="Já existe uma conta com este email.", nome=nome, email=email)

    senha_hash = pwd_context.hash(senha)
    usuario = models.Usuario(
        nome=nome.strip(),
        email=email,
        senha_hash=senha_hash,
        creditos_vaga=10,
        creditos_curriculo=10,
        creditos_adaptacao=10,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    request.session["user_id"] = usuario.id
    return RedirectResponse(url="/", status_code=303)


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if not usuario or not usuario.senha_hash or not pwd_context.verify(senha, usuario.senha_hash):
        return render("login.html", request, erro="Email ou senha inválidos.", email=email)
    request.session["user_id"] = usuario.id
    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/login/google")
async def login_google(request: Request):
    """Inicia o fluxo OAuth do Google (requer GOOGLE_CLIENT_ID/SECRET)."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return RedirectResponse(url="/login?erro=google_nao_configurado", status_code=303)
    redirect_uri = f"{settings.BASE_URL}/auth/google"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google")
async def auth_google(request: Request, db: Session = Depends(get_db)):
    """Callback do OAuth do Google: cria/loga o usuário com base no email."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return RedirectResponse(url="/login?erro=google_nao_configurado", status_code=303)

    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or await oauth.google.userinfo(token)
    email = userinfo.get("email")
    if not email:
        return RedirectResponse(url="/login?erro=email_indisponivel", status_code=303)

    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if not usuario:
        usuario = models.Usuario(
            nome=userinfo.get("name", email),
            email=email,
            senha_hash=None,  # login social: sem senha
            creditos_vaga=10,
            creditos_curriculo=10,
            creditos_adaptacao=10,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

    request.session["user_id"] = usuario.id
    return RedirectResponse(url="/", status_code=303)