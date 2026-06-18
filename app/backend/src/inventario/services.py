from decimal import Decimal
from typing import Optional

from sqlmodel import Session

from .models import Movimentacao, Produto


class SemMudanca(Exception):
    """Levantada quando o ajuste não altera o estoque (delta zero)."""


def aplicar_ajuste_estoque(
    session: Session,
    produto: Produto,
    nova_quantidade: int,
    peso_g: Optional[Decimal] = None,
) -> Movimentacao:
    """Grava a movimentação e atualiza o estoque numa transação (spec §7.4)."""
    delta = nova_quantidade - produto.estoque_disponivel
    if delta == 0:
        raise SemMudanca()
    mov = Movimentacao(
        produto_id=produto.id,
        tipo="REPOSICAO" if delta > 0 else "AJUSTE",
        quantidade=delta,
        peso_g=peso_g,
    )
    produto.estoque_disponivel = nova_quantidade
    session.add(mov)
    session.add(produto)
    session.commit()
    session.refresh(mov)
    return mov
