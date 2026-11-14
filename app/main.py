import os
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Gestão de Carreira e ATS", version="1.0.0")

# Definindo caminhos absolutos para evitar erros de diretório no Docker
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Montando a pasta static (para CSS customizado, JS extra, imagens, etc.)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Configurando o Jinja2Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.get("/")
async def read_root(request: Request):
    """
    Renderiza a interface inicial (index.html) com o formulário HTMX.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analisar-vaga")
async def analisar_vaga(request: Request, vaga_texto: str = Form(...)):
    """
    Recebe o texto bruto da vaga enviado pelo frontend via HTMX.
    Retorna o fragmento resultado.html que será injetado na div destino sem refresh.
    """
    # TODO: Implementar a chamada ao serviço do DeepSeek e gravação no PostgreSQL
    
    # Por enquanto, retornamos o template de placeholder injetando uma mensagem simulada
    return templates.TemplateResponse(
        "resultado.html", 
        {
            "request": request,
            "mensagem": "Vaga recebida com sucesso! Em breve, a IA analisará estes dados."
        }
    )