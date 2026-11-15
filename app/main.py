import os
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from app.services.deepseek_service import analisar_vaga_com_ia
from app.services.scraper_service import extrair_texto_da_url, ScraperError

app = FastAPI(title="Gestão de Carreira e ATS", version="1.0.0")

# Definindo caminhos absolutos para evitar erros de diretório no Docker
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Montando a pasta static (para CSS customizado, JS extra, imagens, etc.)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Configurando o Jinja2 para renderizar templates
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Renderiza a interface inicial (index.html) com o formulário HTMX.
    """
    template = env.get_template("index.html")
    return template.render(request=request)

@app.post("/analisar-vaga", response_class=HTMLResponse)
async def analisar_vaga(request: Request, vaga_texto: str = Form(None), vaga_url: str = Form(None)):
    """
    Recebe o texto bruto da vaga (colado) ou a URL da vaga enviados pelo frontend via HTMX.

    Se uma URL for informada, o conteúdo da página é extraído antes de ser enviado
    à IA. Retorna o fragmento resultado.html que será injetado na div destino sem refresh.
    """
    try:
        # Decide a fonte do texto: URL raspada ou texto colado
        if vaga_url:
            texto_vaga = await extrair_texto_da_url(vaga_url)
        elif vaga_texto:
            texto_vaga = vaga_texto
        else:
            raise ValueError("Nenhum conteúdo foi informado. Cole o texto ou informe a URL da vaga.")

        # Chamando o serviço do DeepSeek para análise da vaga
        resultado_analise = await analisar_vaga_com_ia(texto_vaga)

        # Retornando o resultado analisado para o template
        template = env.get_template("resultado.html")
        return template.render(request=request, resultado=resultado_analise, sucesso=True)
    except ScraperError as e:
        # Falha ao extrair conteúdo da URL: mensagem elegante orientando a colar o texto
        template = env.get_template("resultado.html")
        return template.render(
            request=request,
            mensagem=(
                f"Não foi possível extrair o conteúdo da URL informada. {str(e)} "
                "O site pode estar fora do ar ou bloquear acessos automáticos. "
                "Para esta vaga, tente usar a opção 'Colar Texto' com o conteúdo da descrição."
            ),
            sucesso=False,
        )
    except Exception as e:
        # Em caso de erro, retornar mensagem de erro
        template = env.get_template("resultado.html")
        return template.render(request=request, mensagem=f"Erro ao analisar a vaga: {str(e)}", sucesso=False)
