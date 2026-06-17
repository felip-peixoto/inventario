from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Numeric
from sqlmodel import SQLModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Produto(SQLModel, table=True):
    __tablename__ = "produtos"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(max_length=150)
    rfid_tag_id: str = Field(max_length=50, unique=True, index=True)
    peso_unitario_g: Decimal = Field(sa_type=Numeric(10, 3))
    tara_caixa_g: Decimal = Field(default=Decimal("0"), sa_type=Numeric(10, 3))
    preco_unitario: Decimal = Field(sa_type=Numeric(10, 2))
    estoque_disponivel: int = Field(default=0)
    estoque_reservado: int = Field(default=0)
    criado_em: datetime = Field(default_factory=_utcnow)
    atualizado_em: datetime = Field(default_factory=_utcnow)


class Venda(SQLModel, table=True):
    __tablename__ = "vendas"

    id: Optional[int] = Field(default=None, primary_key=True)
    status: str = Field(default="PENDENTE", max_length=20)
    valor_total: Decimal = Field(default=Decimal("0"), sa_type=Numeric(10, 2))
    pix_txid: Optional[str] = Field(default=None, max_length=100)
    pix_qrcode: Optional[str] = None
    criado_em: datetime = Field(default_factory=_utcnow)
    confirmado_em: Optional[datetime] = None
    expira_em: Optional[datetime] = None


class Movimentacao(SQLModel, table=True):
    __tablename__ = "movimentacoes"

    id: Optional[int] = Field(default=None, primary_key=True)
    produto_id: int = Field(foreign_key="produtos.id")
    venda_id: Optional[int] = Field(default=None, foreign_key="vendas.id")
    tipo: str = Field(max_length=20)
    quantidade: int
    peso_g: Optional[Decimal] = Field(default=None, sa_type=Numeric(10, 3))
    preco_unitario_snapshot: Optional[Decimal] = Field(default=None, sa_type=Numeric(10, 2))
    criado_em: datetime = Field(default_factory=_utcnow)
