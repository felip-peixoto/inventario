from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field


class ProdutoBase(BaseModel):
    nome: str
    rfid_tag_id: str
    peso_unitario_g: Decimal
    tara_caixa_g: Decimal = Decimal("0")
    preco_unitario: Decimal


class ProdutoCreate(ProdutoBase):
    estoque_disponivel: int = 0


class ProdutoUpdate(BaseModel):
    nome: Optional[str] = None
    rfid_tag_id: Optional[str] = None
    peso_unitario_g: Optional[Decimal] = None
    tara_caixa_g: Optional[Decimal] = None
    preco_unitario: Optional[Decimal] = None
    estoque_disponivel: Optional[int] = None


class ProdutoRead(ProdutoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estoque_disponivel: int
    estoque_reservado: int

    @computed_field
    @property
    def peso_total_g(self) -> Decimal:
        return self.tara_caixa_g + self.estoque_disponivel * self.peso_unitario_g


class AjusteEstoque(BaseModel):
    nova_quantidade: int


class MovimentacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    produto_id: int
    produto_nome: str
    tipo: str
    quantidade: int
    peso_g: Optional[Decimal]
    criado_em: datetime


class OperacaoIn(BaseModel):
    produto_id: int
    peso_g: Decimal


class OperacaoPreviewOut(BaseModel):
    status: str  # "ok" | "empty" | "imprecise" | "no_change"
    produto_id: int
    produto_nome: str
    estoque_atual: int
    peso_g: Decimal
    tipo: Optional[str] = None
    quantidade: Optional[int] = None
    qtd_fisica: Optional[int] = None
    qtd_resultante: Optional[int] = None
