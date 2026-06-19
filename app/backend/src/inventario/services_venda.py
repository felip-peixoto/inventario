from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from .models import Movimentacao, Produto, Venda
from .pagamentos.mercadopago import ClientePagamento


class ProdutoInexistente(Exception):
    def __init__(self, produto_id: int):
        self.produto_id = produto_id


class EstoqueInsuficiente(Exception):
    def __init__(self, produto_id: int):
        self.produto_id = produto_id


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def itens_reserva(session: Session, venda_id: int) -> list[Movimentacao]:
    return list(
        session.exec(
            select(Movimentacao).where(
                Movimentacao.venda_id == venda_id, Movimentacao.tipo == "RESERVA"
            )
        ).all()
    )


def criar_venda(
    session: Session, itens: list[tuple[int, int]], mp: ClientePagamento
) -> tuple[Venda, str]:
    carregados = []
    for produto_id, qtd in itens:
        produto = session.get(Produto, produto_id)
        if produto is None:
            raise ProdutoInexistente(produto_id)
        if qtd <= 0 or produto.estoque_disponivel < qtd:
            raise EstoqueInsuficiente(produto_id)
        carregados.append((produto, qtd))

    valor_total = sum((p.preco_unitario * qtd for p, qtd in carregados), start=Decimal("0"))
    pagamento = mp.criar_pagamento_pix(valor_total, "Venda inventário")

    venda = Venda(
        status="PENDENTE",
        valor_total=valor_total,
        pix_txid=pagamento.id,
        pix_qrcode=pagamento.qr_code,
        expira_em=pagamento.expira_em,
    )
    session.add(venda)
    session.flush()  # garante venda.id

    for produto, qtd in carregados:
        produto.estoque_disponivel -= qtd
        produto.estoque_reservado += qtd
        session.add(produto)
        session.add(
            Movimentacao(
                produto_id=produto.id,
                venda_id=venda.id,
                tipo="RESERVA",
                quantidade=-qtd,
                preco_unitario_snapshot=produto.preco_unitario,
            )
        )
    session.commit()
    session.refresh(venda)
    return venda, pagamento.qr_code_base64


def confirmar_pagamento(session: Session, venda: Venda) -> Venda:
    if venda.status != "PENDENTE":
        return venda
    for mov in itens_reserva(session, venda.id):
        qtd = -mov.quantidade
        produto = session.get(Produto, mov.produto_id)
        produto.estoque_reservado -= qtd
        session.add(produto)
        session.add(
            Movimentacao(
                produto_id=produto.id, venda_id=venda.id, tipo="CONFIRMACAO",
                quantidade=mov.quantidade, preco_unitario_snapshot=mov.preco_unitario_snapshot,
            )
        )
    venda.status = "CONFIRMADO"
    venda.confirmado_em = _agora()
    session.add(venda)
    session.commit()
    session.refresh(venda)
    return venda


def reverter_venda(session: Session, venda: Venda, status: str) -> Venda:
    if venda.status != "PENDENTE":
        return venda
    for mov in itens_reserva(session, venda.id):
        qtd = -mov.quantidade
        produto = session.get(Produto, mov.produto_id)
        produto.estoque_reservado -= qtd
        produto.estoque_disponivel += qtd
        session.add(produto)
        session.add(
            Movimentacao(
                produto_id=produto.id, venda_id=venda.id, tipo="REVERSAO",
                quantidade=qtd, preco_unitario_snapshot=mov.preco_unitario_snapshot,
            )
        )
    venda.status = status
    session.add(venda)
    session.commit()
    session.refresh(venda)
    return venda


def reconciliar(session: Session, venda: Venda, mp: ClientePagamento) -> Venda:
    if venda.status != "PENDENTE":
        return venda
    if venda.expira_em is not None and _agora() > _aware(venda.expira_em):
        return reverter_venda(session, venda, "EXPIRADO")
    if mp.consultar_pagamento(venda.pix_txid) == "approved":
        return confirmar_pagamento(session, venda)
    return venda
