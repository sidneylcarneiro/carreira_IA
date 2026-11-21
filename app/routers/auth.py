"""Rotas de autenticação: cadastro, login, logout e (estrutural) Google OAuth."""
import os
import logging

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.base_client import OAuthError
from authlib.integrations.base_client.errors import MismatchingStateError

from ..dependencies import get_db
from ..config import settings
from .. import models

logger = logging.getLogger(__name__)

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


# --- Google OAuth (login social) ---
CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url=CONF_URL,
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    erro_codigo = request.query_params.get("erro")
    mensagens = {
        "google_nao_configurado": "O login com Google ainda não está configurado. Use email e senha.",
        "email_indisponivel": "Não foi possível obter o email da sua conta Google.",
        "acesso_negado": "Acesso negado ao login com Google.",
        "erro_oauth": "Não foi possível concluir o login com Google. Tente novamente.",
        "sessao_invalida": (
            "O login com Google não pôde validar a sessão (state do OAuth não bateu). "
            "Isso normalmente acontece quando você acessa o sistema por um endereço diferente "
            "do usado na tela de login (ex.: localhost em vez de 127.0.0.1) ou quando o cookie "
            "de sessão foi perdido. Feche e reabra a aba, use sempre o mesmo endereço e tente de novo."
        ),
    }
    erro = mensagens.get(erro_codigo) if erro_codigo else None
    return render("login.html", request, erro=erro)


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

    # O "state" do OAuth é gravado/validado através do cookie de sessão. Por isso a URL de
    # callback precisa usar o MESMO host que o navegador está usando agora — caso contrário o
    # cookie não é enviado no callback e o Google retorna MismatchingStateError.
    if settings.OAUTH_REDIRECT_BASE_URL:
        # Caso de produção atrás de proxy reverse com URL pública diferente da interna.
        redirect_uri = f"{settings.OAUTH_REDIRECT_BASE_URL.rstrip('/')}/auth/google"
    else:
        redirect_uri = str(request.url_for("auth_google"))

    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google")
async def auth_google(request: Request, db: Session = Depends(get_db)):
    """Callback do OAuth do Google: cria/loga o usuário com base no email."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return RedirectResponse(url="/login?erro=google_nao_configurado", status_code=303)

    try:
        token = await oauth.google.authorize_access_token(request)
    except MismatchingStateError as e:
        # O "state" vindo do Google não bate com o gravado na sessão do navegador.
        logger.warning("MismatchingStateError no OAuth do Google: %s", e, exc_info=True)
        if settings.OAUTH_DEBUG:
            return {
                "erro_real": str(e),
                "tipo_do_erro": str(type(e)),
                "state_no_callback": request.query_params.get("state"),
                "chaves_de_estado_na_sessao": [
                    k for k in request.session.keys() if k.startswith("_state_google_")
                ],
                "tem_user_id_na_sessao": "user_id" in request.session,
            }
        return RedirectResponse(url="/login?erro=sessao_invalida", status_code=303)
    except OAuthError as e:
        # Fluxo rejeitado pelo próprio Google (ex.: usuário clicou em "cancelar").
        logger.warning("OAuthError no OAuth do Google: %s", e, exc_info=True)
        if e.error == "access_denied":
            return RedirectResponse(url="/login?erro=acesso_negado", status_code=303)
        if settings.OAUTH_DEBUG:
            return {"erro_real": str(e), "tipo_do_erro": str(type(e))}
        return RedirectResponse(url="/login?erro=erro_oauth", status_code=303)
    except Exception as e:
        logger.exception("Falha inesperada no OAuth do Google")
        if settings.OAUTH_DEBUG:
            return {"erro_real": str(e), "tipo_do_erro": str(type(e))}
        return RedirectResponse(url="/login?erro=erro_oauth", status_code=303)

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