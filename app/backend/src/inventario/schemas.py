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
