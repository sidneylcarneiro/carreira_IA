from fastapi import Request, Depends
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models


class NotAuthenticatedError(Exception):
    """Exceção levantada quando o usuário não está autenticado."""


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.Usuario:
    """Lê o id do usuário da sessão e retorna o registro correspondente."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise NotAuthenticatedError()
    user = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
    if not user:
        raise NotAuthenticatedError()
    return user