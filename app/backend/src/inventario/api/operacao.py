from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..db import get_session, settings
from ..domain.inventory import ReconcileStatus, reconcile
from ..models import Produto
from ..schemas import MovimentacaoRead, OperacaoIn, OperacaoPreviewOut
from ..services import aplicar_ajuste_estoque

router = APIRouter(prefix="/operacao", tags=["operacao"])


def _reconciliar(produto: Produto, peso_g: Decimal):
    return reconcile(
        produto_id=produto.id,
        peso_g=peso_g,
        tara_g=produto.tara_caixa_g,
        peso_unitario_g=produto.peso_unitario_g,
        estoque_disponivel=produto.estoque_disponivel,
        rounding_tolerance_units=settings.rounding_tolerance_units,
        empty_scale_tolerance_g=settings.empty_scale_tolerance_g,
    )


@router.post("/preview", response_model=OperacaoPreviewOut)
def preview(dados: OperacaoIn, session: Session = Depends(get_session)):
    produto = session.get(Produto, dados.produto_id)
    if produto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "produto não encontrado")
    r = _reconciliar(produto, dados.peso_g)
    out = OperacaoPreviewOut(
        status=r.status.value,
        produto_id=produto.id,
        produto_nome=produto.nome,
        estoque_atual=produto.estoque_disponivel,
        peso_g=dados.peso_g,
    )
    if r.movement is not None:
        out.tipo = r.movement.tipo
        out.quantidade = r.movement.quantidade
        out.qtd_fisica = r.movement.qtd_fisica
        out.qtd_resultante = r.movement.qtd_resultante
    return out


@router.post("/confirmar", response_model=MovimentacaoRead, status_code=status.HTTP_201_CREATED)
def confirmar(dados: OperacaoIn, session: Session = Depends(get_session)):
    produto = session.get(Produto, dados.produto_id)
    if produto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "produto não encontrado")
    r = _reconciliar(produto, dados.peso_g)
    if r.status is not ReconcileStatus.OK or r.movement is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"leitura não confirmável: {r.status.value}"
        )
    mov = aplicar_ajuste_estoque(session, produto, r.movement.qtd_fisica, peso_g=dados.peso_g)
    return MovimentacaoRead(
        id=mov.id,
        produto_id=mov.produto_id,
        produto_nome=produto.nome,
        tipo=mov.tipo,
        quantidade=mov.quantidade,
        peso_g=mov.peso_g,
        criado_em=mov.criado_em,
    )
