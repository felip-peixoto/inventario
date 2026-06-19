from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..db import get_session, settings
from ..models import Produto, Venda
from ..pagamentos.mercadopago import ClientePagamento, MercadoPago
from ..schemas import VendaCreate, VendaCriadaOut, VendaItemRead, VendaRead
from .. import services_venda as sv

router = APIRouter(prefix="/vendas", tags=["vendas"])


def get_mp() -> ClientePagamento:
    return MercadoPago(settings.mercadopago_access_token, settings.venda_expiracao_minutos)


def _itens_read(session: Session, venda_id: int) -> list[VendaItemRead]:
    itens = []
    for mov in sv.itens_reserva(session, venda_id):
        produto = session.get(Produto, mov.produto_id)
        qtd = -mov.quantidade
        preco = mov.preco_unitario_snapshot
        itens.append(
            VendaItemRead(
                produto_id=mov.produto_id,
                produto_nome=produto.nome,
                quantidade=qtd,
                preco_unitario=preco,
                subtotal=qtd * preco,
            )
        )
    return itens


def _read(session: Session, venda: Venda, qr_base64: str | None = None):
    campos = dict(
        id=venda.id,
        status=venda.status,
        valor_total=venda.valor_total,
        pix_copia_e_cola=venda.pix_qrcode,
        expira_em=venda.expira_em,
        itens=_itens_read(session, venda.id),
    )
    if qr_base64 is not None:
        return VendaCriadaOut(**campos, qr_code_base64=qr_base64)
    return VendaRead(**campos)


@router.post("", response_model=VendaCriadaOut, status_code=status.HTTP_201_CREATED)
def criar(dados: VendaCreate, session: Session = Depends(get_session), mp=Depends(get_mp)):
    itens = [(i.produto_id, i.quantidade) for i in dados.itens]
    try:
        venda, qr_base64 = sv.criar_venda(session, itens, mp)
    except sv.ProdutoInexistente as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"produto {e.produto_id} não encontrado")
    except sv.EstoqueInsuficiente as e:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"estoque insuficiente para o produto {e.produto_id}"
        )
    return _read(session, venda, qr_base64)


@router.get("/{venda_id}", response_model=VendaRead)
def obter(venda_id: int, session: Session = Depends(get_session), mp=Depends(get_mp)):
    venda = session.get(Venda, venda_id)
    if venda is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "venda não encontrada")
    sv.reconciliar(session, venda, mp)
    return _read(session, venda)


@router.post("/{venda_id}/pagamento", response_model=VendaRead)
def pagamento(venda_id: int, session: Session = Depends(get_session)):
    venda = session.get(Venda, venda_id)
    if venda is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "venda não encontrada")
    if venda.status != "PENDENTE":
        raise HTTPException(status.HTTP_409_CONFLICT, "venda não está pendente")
    sv.confirmar_pagamento(session, venda)
    return _read(session, venda)


@router.post("/{venda_id}/cancelar", response_model=VendaRead)
def cancelar(venda_id: int, session: Session = Depends(get_session)):
    venda = session.get(Venda, venda_id)
    if venda is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "venda não encontrada")
    if venda.status != "PENDENTE":
        raise HTTPException(status.HTTP_409_CONFLICT, "venda não está pendente")
    sv.reverter_venda(session, venda, "CANCELADO")
    return _read(session, venda)
