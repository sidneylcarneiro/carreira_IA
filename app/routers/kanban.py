"""Rotas do Quadro Kanban, sincronizado com o Dashboard.

O quadro começa vazio: uma vaga só entra no Kanban quando o usuário clica em
"+ Kanban" no Dashboard. Cada vaga recebe um status_kanban que a coloca em uma
das 4 etapas (candidatado, entrevista, nao_selecionado, contratado). Remover do
quadro apenas limpa o status_kanban (a vaga continua no Dashboard).
"""
import os

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from .. import models

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

# Ordem e rótulos das etapas do Kanban.
ETAPAS = ["candidatado", "entrevista", "nao_selecionado", "contratado"]
ETAPAS_LABEL = {
    "candidatado": "Candidatado",
    "entrevista": "Entrevista",
    "nao_selecionado": "Não Selecionado",
    "contratado": "Contratado",
}

# Cores (Tailwind) do badge de cada etapa.
ETAPAS_COR = {
    "candidatado": "bg-blue-100 text-blue-700",
    "entrevista": "bg-amber-100 text-amber-700",
    "nao_selecionado": "bg-red-100 text-red-700",
    "contratado": "bg-green-100 text-green-700",
}


def render(template_name: str, request: Request, **context) -> HTMLResponse:
    template = env.get_template(template_name)
    context.setdefault("request", request)
    return template.render(**context)


def _badge_html(status: str, vaga_id: int) -> str:
    """Retorna o badge clicável de etapa (usado no Dashboard via HTMX)."""
    label = ETAPAS_LABEL.get(status, status)
    cor = ETAPAS_COR.get(status, "bg-gray-100 text-gray-700")
    return (
        f'<a href="/kanban" title="Ver no Quadro Kanban" '
        f'class="inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium {cor}">'
        f"{label}</a>"
    )


def _get_vaga_para_usuario(db: Session, vaga_id: int, usuario) -> models.VagaAnalisada:
    """Busca a vaga garantindo que pertence ao usuário logado."""
    vaga = (
        db.query(models.VagaAnalisada)
        .filter(models.VagaAnalisada.id == vaga_id, models.VagaAnalisada.id_usuario == usuario.id)
        .first()
    )
    if not vaga:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    return vaga


@router.get("/kanban", response_class=HTMLResponse)
async def kanban_page(
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Exibe o quadro Kanban com as vagas do usuário que possuem etapa definida."""
    vagas = (
        db.query(models.VagaAnalisada)
        .filter(
            models.VagaAnalisada.id_usuario == usuario.id,
            models.VagaAnalisada.status_kanban.isnot(None),
        )
        .order_by(models.VagaAnalisada.id.desc())
        .all()
    )

    # Agrupa por etapa e descobre a adaptação de cada vaga (para o link rápido).
    por_etapa = {etapa: [] for etapa in ETAPAS}
    for vaga in vagas:
        adaptacao = (
            db.query(models.CurriculoAdaptado)
            .filter(
                models.CurriculoAdaptado.id_vaga == vaga.id,
                models.CurriculoAdaptado.id_usuario == usuario.id,
            )
            .first()
        )
        etapa = vaga.status_kanban if vaga.status_kanban in ETAPAS else None
        if etapa:
            por_etapa[etapa].append({"vaga": vaga, "adaptacao": adaptacao})

    return render(
        "kanban.html",
        request,
        usuario=usuario,
        por_etapa=por_etapa,
        etapas=ETAPAS,
        etapas_label=ETAPAS_LABEL,
        etapas_cor=ETAPAS_COR,
        total=len(vagas),
    )


@router.post("/kanban/adicionar/{vaga_id}", response_class=HTMLResponse)
async def kanban_adicionar(
    vaga_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Adiciona a vaga ao quadro (etapa inicial 'candidatado').

    Retorna um fragmento HTML (badge) para substituir o botão "+ Kanban" no
    Dashboard via HTMX (hx-swap=outerHTML).
    """
    vaga = _get_vaga_para_usuario(db, vaga_id, usuario)
    vaga.status_kanban = "candidatado"
    db.commit()
    db.refresh(vaga)
    return HTMLResponse(_badge_html(vaga.status_kanban, vaga.id))


@router.post("/kanban/mover/{vaga_id}", response_class=HTMLResponse)
async def kanban_mover(
    vaga_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Move a vaga entre as etapas do Kanban (usado por drag & drop e pelo select)."""
    if status not in ETAPAS:
        raise HTTPException(status_code=400, detail="Etapa inválida.")
    vaga = _get_vaga_para_usuario(db, vaga_id, usuario)
    vaga.status_kanban = status
    db.commit()
    db.refresh(vaga)
    return PlainTextResponse("ok", status_code=200)


@router.post("/kanban/remover/{vaga_id}", response_class=HTMLResponse)
async def kanban_remover(
    vaga_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Remove a vaga do quadro, sem apagá-la do Dashboard."""
    vaga = _get_vaga_para_usuario(db, vaga_id, usuario)
    vaga.status_kanban = None
    db.commit()
    return PlainTextResponse("ok", status_code=200)