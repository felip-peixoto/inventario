from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import inventario.models  # noqa: F401  (registra as tabelas no metadata)
from inventario.db import get_session
from inventario.main import app
from inventario.pagamentos.mercadopago import PagamentoPix


class FakeMP:
    """Cliente de pagamento falso (sem rede), configurável nos testes."""

    def __init__(self):
        self.status_consulta = "pending"

    def criar_pagamento_pix(self, valor, descricao):
        return PagamentoPix(
            id="PAY123",
            status="pending",
            qr_code="COPIA_E_COLA",
            qr_code_base64="BASE64IMG",
            expira_em=datetime.now(timezone.utc) + timedelta(minutes=30),
        )

    def consultar_pagamento(self, pagamento_id):
        return self.status_consulta


def _engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session():
    with Session(_engine()) as s:
        yield s


@pytest.fixture
def fake_mp():
    return FakeMP()


@pytest.fixture
def client(fake_mp):
    engine = _engine()

    def override_get_session():
        with Session(engine) as session:
            yield session

    from inventario.api.vendas import get_mp

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_mp] = lambda: fake_mp
    yield TestClient(app)
    app.dependency_overrides.clear()
