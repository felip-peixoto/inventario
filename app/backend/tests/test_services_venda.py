from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlmodel import select

from inventario.models import Movimentacao, Produto
from inventario import services_venda as sv


def _produto(session, nome, tag, preco, estoque):
    p = Produto(nome=nome, rfid_tag_id=tag, peso_unitario_g=Decimal("1"),
                preco_unitario=Decimal(preco), estoque_disponivel=estoque)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _movs(session, tipo):
    return list(session.exec(select(Movimentacao).where(Movimentacao.tipo == tipo)).all())


def test_criar_venda_reserva_e_calcula_total(session, fake_mp):
    a = _produto(session, "Refri", "A", "5.00", 8)
    b = _produto(session, "Salg", "B", "8.00", 5)
    venda, qr_base64 = sv.criar_venda(session, [(a.id, 3), (b.id, 2)], fake_mp)
    assert venda.status == "PENDENTE"
    assert venda.valor_total == Decimal("31.00")
    assert venda.pix_txid == "PAY123"
    assert venda.pix_qrcode == "COPIA_E_COLA"
    assert qr_base64 == "BASE64IMG"
    session.refresh(a); session.refresh(b)
    assert (a.estoque_disponivel, a.estoque_reservado) == (5, 3)
    assert (b.estoque_disponivel, b.estoque_reservado) == (3, 2)
    reservas = sv.itens_reserva(session, venda.id)
    assert sorted(m.quantidade for m in reservas) == [-3, -2]


def test_criar_venda_estoque_insuficiente_nao_reserva(session, fake_mp):
    a = _produto(session, "Refri", "A", "5.00", 2)
    with pytest.raises(sv.EstoqueInsuficiente):
        sv.criar_venda(session, [(a.id, 3)], fake_mp)
    session.refresh(a)
    assert (a.estoque_disponivel, a.estoque_reservado) == (2, 0)


def test_criar_venda_produto_inexistente(session, fake_mp):
    with pytest.raises(sv.ProdutoInexistente):
        sv.criar_venda(session, [(999, 1)], fake_mp)


def test_confirmar_pagamento(session, fake_mp):
    a = _produto(session, "Refri", "A", "5.00", 8)
    venda, _ = sv.criar_venda(session, [(a.id, 3)], fake_mp)
    sv.confirmar_pagamento(session, venda)
    session.refresh(a); session.refresh(venda)
    assert venda.status == "CONFIRMADO"
    assert venda.confirmado_em is not None
    assert (a.estoque_disponivel, a.estoque_reservado) == (5, 0)
    assert len(_movs(session, "CONFIRMACAO")) == 1


def test_reverter_devolve_estoque(session, fake_mp):
    a = _produto(session, "Refri", "A", "5.00", 8)
    venda, _ = sv.criar_venda(session, [(a.id, 3)], fake_mp)
    sv.reverter_venda(session, venda, "CANCELADO")
    session.refresh(a); session.refresh(venda)
    assert venda.status == "CANCELADO"
    assert (a.estoque_disponivel, a.estoque_reservado) == (8, 0)
    assert len(_movs(session, "REVERSAO")) == 1


def test_confirmar_idempotente(session, fake_mp):
    a = _produto(session, "Refri", "A", "5.00", 8)
    venda, _ = sv.criar_venda(session, [(a.id, 3)], fake_mp)
    sv.confirmar_pagamento(session, venda)
    sv.confirmar_pagamento(session, venda)  # segunda vez é no-op
    session.refresh(a)
    assert (a.estoque_disponivel, a.estoque_reservado) == (5, 0)
    assert len(_movs(session, "CONFIRMACAO")) == 1


def test_reconciliar_aprovado_confirma(session, fake_mp):
    a = _produto(session, "Refri", "A", "5.00", 8)
    venda, _ = sv.criar_venda(session, [(a.id, 3)], fake_mp)
    fake_mp.status_consulta = "approved"
    sv.reconciliar(session, venda, fake_mp)
    session.refresh(venda)
    assert venda.status == "CONFIRMADO"


def test_reconciliar_expirado_reverte(session, fake_mp):
    a = _produto(session, "Refri", "A", "5.00", 8)
    venda, _ = sv.criar_venda(session, [(a.id, 3)], fake_mp)
    venda.expira_em = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.add(venda); session.commit()
    sv.reconciliar(session, venda, fake_mp)  # fake continua "pending"
    session.refresh(venda)
    assert venda.status == "EXPIRADO"
