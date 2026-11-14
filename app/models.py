from sqlalchemy import Column, Integer, String, JSON
from .database import Base

class Usuario(Base):
    __tablename__ = 'usuario'
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    email = Column(String, unique=True, index=True)

class VagaAnalisada(Base):
    __tablename__ = 'vaga_analisada'
    id = Column(Integer, primary_key=True, index=True)
    vaga_data = Column(JSON)

class CurriculoGerado(Base):
    __tablename__ = 'curriculo_gerado'
    id = Column(Integer, primary_key=True, index=True)
    curriculo_data = Column(JSON)