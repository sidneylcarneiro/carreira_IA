from sqlalchemy import Column, Integer, String, JSON, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from .database import Base


class Usuario(Base):
    __tablename__ = 'usuario'
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), index=True)
    email = Column(String(120), unique=True, index=True)
    senha_hash = Column(String(255), nullable=True)  # nulo se for login social
    telefone = Column(String, nullable=True)
    creditos_vaga = Column(Integer, default=10, nullable=False)
    creditos_curriculo = Column(Integer, default=10, nullable=False)
    creditos_adaptacao = Column(Integer, default=10, nullable=False)
    data_criacao = Column(DateTime(timezone=True), server_default=func.now())


class VagaAnalisada(Base):
    __tablename__ = 'vaga_analisada'
    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey('usuario.id'), index=True)
    vaga_data = Column(JSON)
    url_original = Column(String(500), nullable=True)
    texto_original = Column(Text, nullable=True)
    data_criacao = Column(DateTime(timezone=True), server_default=func.now())


class CurriculoBase(Base):
    __tablename__ = 'curriculo_base'
    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey('usuario.id'), index=True)
    texto_bruto = Column(Text)
    curriculo_estruturado = Column(JSON)
    data_criacao = Column(DateTime(timezone=True), server_default=func.now())


class CurriculoAdaptado(Base):
    __tablename__ = 'curriculo_adaptado'
    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey('usuario.id'), index=True)
    id_vaga = Column(Integer, ForeignKey('vaga_analisada.id'), index=True)
    curriculo_adaptado = Column(JSON)
    carta_apresentacao = Column(Text)
    data_criacao = Column(DateTime(timezone=True), server_default=func.now())