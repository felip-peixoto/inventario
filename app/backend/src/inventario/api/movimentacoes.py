from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..db import get_session
from ..models import Movimentacao, Produto
from ..schemas import MovimentacaoRead

router = APIRouter(prefix="/movimentacoes", tags=["movimentacoes"])


@router.get("", response_model=list[MovimentacaoRead])
def listar(
    produto_id: Optional[int] = None,
    tipo: Optional[str] = None,
    session: Session = Depends(get_session),
):
    q = (
        select(Movimentacao, Produto.nome)
        .join(Produto)
        .order_by(Movimentacao.criado_em.desc(), Movimentacao.id.desc())
    )
    if produto_id is not None:
        q = q.where(Movimentacao.produto_id == produto_id)
    if tipo is not None:
        q = q.where(Movimentacao.tipo == tipo)
    return [
        MovimentacaoRead(
            id=m.id,
            produto_id=m.produto_id,
            produto_nome=nome,
            tipo=m.tipo,
            quantidade=m.quantidade,
            peso_g=m.peso_g,
            criado_em=m.criado_em,
        )
        for m, nome in session.exec(q).all()
    ]
