import os
from fastapi import FastAPI, Request, Form, Depends, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, engine
from app import models
from app.dependencies import get_db, get_current_user, NotAuthenticatedError
from app.services.deepseek_service import analisar_vaga_com_ia, estruturar_curriculo_base, adaptar_curriculo
from app.services.scraper_service import extrair_texto_da_url, ScraperError
from app.services.file_service import extrair_texto_de_arquivo
from app.routers import auth

app = FastAPI(title="Gestão de Carreira e ATS", version="2.0.0")

# Middleware de sessão (cookies) para gerenciar o usuário logado
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET)

# Definindo caminhos absolutos para evitar erros de diretório no Docker
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Montando a pasta static (para CSS customizado, JS extra, imagens, etc.)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Configurando o Jinja2 para renderizar templates
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

# Registrando as rotas de autenticação
app.include_router(auth.router)


@app.exception_handler(NotAuthenticatedError)
async def not_authenticated_handler(request: Request, exc: NotAuthenticatedError):
    return RedirectResponse(url="/login", status_code=303)


@app.on_event("startup")
def startup():
    # Cria as tabelas caso ainda não existam
    Base.metadata.create_all(bind=engine)


def render(template_name: str, request: Request, **context):
    template = env.get_template(template_name)
    context.setdefault("request", request)
    return template.render(**context)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, usuario=Depends(get_current_user)):
    """Renderiza a interface inicial (index.html) com o formulário HTMX."""
    return render("index.html", request, usuario=usuario)


@app.get("/curriculo", response_class=HTMLResponse)
async def curriculo_page(request: Request, usuario=Depends(get_current_user)):
    """Renderiza a página de envio do currículo."""
    return render("curriculo.html", request, usuario=usuario)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db), usuario=Depends(get_current_user)):
    """Lista as vagas analisadas pelo usuário e o estado de adaptação de cada uma."""
    vagas = (
        db.query(models.VagaAnalisada)
        .filter(models.VagaAnalisada.id_usuario == usuario.id)
        .order_by(models.VagaAnalisada.id.desc())
        .all()
    )
    lista = []
    for vaga in vagas:
        adaptacao = (
            db.query(models.CurriculoAdaptado)
            .filter(
                models.CurriculoAdaptado.id_vaga == vaga.id,
                models.CurriculoAdaptado.id_usuario == usuario.id,
            )
            .first()
        )
        lista.append({"vaga": vaga, "adaptacao": adaptacao})
    return render("dashboard.html", request, usuario=usuario, vagas=lista)


@app.post("/analisar-vaga", response_class=HTMLResponse)
async def analisar_vaga(
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
    vaga_texto: str = Form(None),
    vaga_url: str = Form(None),
):
    """
    Recebe o texto ou a URL da vaga, debita 1 crédito de vaga, analisa com a IA
    e salva a vaga analisada. Retorna o fragmento resultado.html via HTMX.
    """
    try:
        url_original = None
        # Decide a fonte do texto: URL raspada ou texto colado
        if vaga_url:
            texto_vaga = await extrair_texto_da_url(vaga_url)
            url_original = vaga_url
        elif vaga_texto:
            texto_vaga = vaga_texto
        else:
            raise ValueError("Nenhum conteúdo foi informado. Cole o texto ou informe a URL da vaga.")

        # Verifica e debita 1 crédito de vaga
        if usuario.creditos_vaga < 1:
            return render("resultado.html", request, sucesso=False, usuario=usuario,
                          mensagem="Você não possui créditos de vaga disponíveis.")
        usuario.creditos_vaga -= 1
        db.commit()

        try:
            resultado_analise = await analisar_vaga_com_ia(texto_vaga)

            vaga = models.VagaAnalisada(
                id_usuario=usuario.id,
                vaga_data=resultado_analise,
                url_original=url_original,
                texto_original=texto_vaga,
            )
            db.add(vaga)
            db.commit()
            db.refresh(vaga)

            return render("resultado.html", request, sucesso=True, usuario=usuario, resultado=resultado_analise, vaga=vaga)
        except Exception:
            # Reembolsa o crédito em caso de falha
            usuario.creditos_vaga += 1
            db.commit()
            raise
    except ScraperError as e:
        return render("resultado.html", request, sucesso=False, usuario=usuario, mensagem=(
            f"Não foi possível extrair o conteúdo da URL informada. {str(e)} "
            "O site pode estar fora do ar ou bloquear acessos automáticos. "
            "Para esta vaga, tente usar a opção 'Colar Texto' com o conteúdo da descrição."
        ))
    except Exception as e:
        return render("resultado.html", request, sucesso=False, usuario=usuario,
                      mensagem=f"Erro ao analisar a vaga: {str(e)}")


@app.post("/upload-curriculo", response_class=HTMLResponse)
async def upload_curriculo(
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
    arquivo: UploadFile = File(None),
    texto: str = Form(None),
):
    """
    Recebe um arquivo (PDF/DOCX/TXT) ou texto colado, extrai o texto, debita 1 crédito
    de currículo, estrutura com a IA e salva o CurriculoBase.
    """
    try:
        if arquivo and arquivo.filename:
            data = await arquivo.read()
            texto_bruto = extrair_texto_de_arquivo(arquivo.filename, data)
        elif texto and texto.strip():
            texto_bruto = texto.strip()
        else:
            raise ValueError("Envie um arquivo (PDF, DOCX ou TXT) ou cole o texto do currículo.")

        if not texto_bruto.strip():
            raise ValueError("Não foi possível extrair texto do currículo. Verifique o arquivo ou cole o texto manualmente.")

        # Verifica e debita 1 crédito de currículo
        if usuario.creditos_curriculo < 1:
            return render("curriculo_resultado.html", request, sucesso=False, usuario=usuario,
                          mensagem="Você não possui créditos de currículo disponíveis.")
        usuario.creditos_curriculo -= 1
        db.commit()

        try:
            curriculo_estruturado = await estruturar_curriculo_base(texto_bruto)

            base = models.CurriculoBase(
                id_usuario=usuario.id,
                texto_bruto=texto_bruto,
                curriculo_estruturado=curriculo_estruturado,
            )
            db.add(base)
            db.commit()
            db.refresh(base)

            return render("curriculo_resultado.html", request, sucesso=True, usuario=usuario,
                          curriculo=curriculo_estruturado, base=base)
        except Exception:
            # Reembolsa o crédito em caso de falha
            usuario.creditos_curriculo += 1
            db.commit()
            raise
    except Exception as e:
        return render("curriculo_resultado.html", request, sucesso=False, usuario=usuario,
                      mensagem=f"Erro ao estruturar o currículo: {str(e)}")


@app.post("/gerar-adaptacao/{vaga_id}", response_class=HTMLResponse)
async def gerar_adaptacao(
    vaga_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """
    Verifica e debita 1 crédito de adaptação, pega a vaga e o currículo base do usuário,
    chama a IA de adaptação e salva na tabela CurriculoAdaptado.
    """
    vaga = None
    try:
        vaga = (
            db.query(models.VagaAnalisada)
            .filter(models.VagaAnalisada.id == vaga_id, models.VagaAnalisada.id_usuario == usuario.id)
            .first()
        )
        if not vaga:
            raise ValueError("Vaga não encontrada.")

        curriculo_base = (
            db.query(models.CurriculoBase)
            .filter(models.CurriculoBase.id_usuario == usuario.id)
            .order_by(models.CurriculoBase.id.desc())
            .first()
        )
        if not curriculo_base:
            raise ValueError("Você ainda não possui um currículo estruturado. Envie seu currículo primeiro.")

        # Verifica e debita 1 crédito de adaptação
        if usuario.creditos_adaptacao < 1:
            return render("adaptacao_resultado.html", request, sucesso=False, usuario=usuario,
                          vaga=vaga, mensagem="Você não possui créditos de adaptação disponíveis.")
        usuario.creditos_adaptacao -= 1
        db.commit()

        try:
            resultado_adaptacao = await adaptar_curriculo(curriculo_base.curriculo_estruturado, vaga.vaga_data)

            adaptacao = models.CurriculoAdaptado(
                id_usuario=usuario.id,
                id_vaga=vaga.id,
                curriculo_adaptado=resultado_adaptacao.get("curriculo_adaptado"),
                carta_apresentacao=resultado_adaptacao.get("carta_apresentacao", ""),
            )
            db.add(adaptacao)
            db.commit()
            db.refresh(adaptacao)

            return render("adaptacao_resultado.html", request, sucesso=True, usuario=usuario,
                          adaptacao=adaptacao, vaga=vaga)
        except Exception:
            # Reembolsa o crédito em caso de falha
            usuario.creditos_adaptacao += 1
            db.commit()
            raise
    except Exception as e:
        return render("adaptacao_resultado.html", request, sucesso=False, usuario=usuario,
                      vaga=vaga, mensagem=f"Erro ao gerar a adaptação: {str(e)}")


@app.get("/baixar-adaptacao/{adaptacao_id}")
async def baixar_adaptacao(
    adaptacao_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Gera um arquivo de texto com o currículo adaptado e a carta de apresentação."""
    adaptacao = (
        db.query(models.CurriculoAdaptado)
        .filter(models.CurriculoAdaptado.id == adaptacao_id, models.CurriculoAdaptado.id_usuario == usuario.id)
        .first()
    )
    if not adaptacao:
        raise HTTPException(status_code=404, detail="Adaptação não encontrada.")

    conteudo = _formatar_curriculo_para_download(adaptacao)
    return Response(
        content=conteudo,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="curriculo_adaptado_{adaptacao.id}.txt"'
        },
    )


def _formatar_curriculo_para_download(adaptacao: models.CurriculoAdaptado) -> str:
    """Formata o currículo adaptado + carta de apresentação em texto puro para download."""
    linhas = []
    linhas.append("=" * 60)
    linhas.append("CURRÍCULO ADAPTADO")
    linhas.append("=" * 60)

    dados = adaptacao.curriculo_adaptado or {}

    if dados.get("dados_pessoais"):
        for chave, valor in dados["dados_pessoais"].items():
            if valor:
                rotulo = chave.replace("_", " ").capitalize()
                linhas.append(f"{rotulo}: {valor}")

    if dados.get("resumo_profissional"):
        linhas.append("\nRESUMO PROFISSIONAL:")
        linhas.append(dados["resumo_profissional"])

    if dados.get("experiencias"):
        linhas.append("\nEXPERIÊNCIAS:")
        for exp in dados["experiencias"]:
            cargo = exp.get("cargo", "")
            empresa = exp.get("empresa", "")
            periodo = exp.get("periodo", "")
            linhas.append(f"- {cargo} @ {empresa} ({periodo})")
            if exp.get("descricao_destacada"):
                linhas.append(f"  {exp['descricao_destacada']}")

    if dados.get("educacao"):
        linhas.append("\nEDUCAÇÃO:")
        for edu in dados["educacao"]:
            curso = edu.get("curso", "")
            instituicao = edu.get("instituicao", "")
            periodo = edu.get("periodo", "")
            linhas.append(f"- {curso} - {instituicao} ({periodo})")

    if dados.get("skills_destaque"):
        linhas.append("\nSKILLS EM DESTAQUE:")
        linhas.append(", ".join(dados["skills_destaque"]))

    linhas.append("\n\n" + "=" * 60)
    linhas.append("CARTA DE APRESENTAÇÃO")
    linhas.append("=" * 60)
    linhas.append(adaptacao.carta_apresentacao or "")

    return "\n".join(linhas)
