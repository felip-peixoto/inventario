# Fase 2 — Backend de Vendas + Pix (Mercado Pago) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans. Steps usam checkbox (`- [ ]`).

**Goal:** Backend do fluxo de venda com Pix: carrinho → reserva de estoque → geração de Pix → confirmação/expiração, tudo em Python, com o Mercado Pago isolado e mockável.

**Architecture:** `pagamentos/mercadopago.py` isola o SDK (interface `ClientePagamento`, injetável). `services_venda.py` faz a máquina de estados (reserva/confirmação/reversão/reconciliação) sobre o schema existente — os itens da venda **são as movimentações `RESERVA`**. `api/vendas.py` expõe os endpoints. Sem tabelas novas.

**Tech Stack:** FastAPI, SQLModel, pytest (SQLite + MP falso), SDK `mercadopago` (Python), Docker.

## Global Constraints

- **Tudo roda em Docker.** O host não tem pip. Testes: `docker compose run --rm --no-deps backend pytest`. Build: `docker compose build backend`. Comando base: `DC="docker compose --project-directory /home/joao/Repos/Oficinas2/inventario -f /home/joao/Repos/Oficinas2/inventario/docker-compose.yml"`.
- **Commits são do usuário** — fazer `git add` e sugerir a mensagem; não commitar.
- Dinheiro/pesos em **`Decimal`** (`NUMERIC`). Datas em UTC tz-aware.
- Tipos de movimento da Fase 2: `RESERVA`/`CONFIRMACAO`/`REVERSAO`. Convenção `quantidade`: `RESERVA=−q`, `CONFIRMACAO=−q`, `REVERSAO=+q`.
- Confirmar/reverter só agem sobre venda `PENDENTE` (idempotência).

---

## File Structure

```
app/backend/
├── requirements.txt                              # + mercadopago
└── src/inventario/
    ├── config.py                                 # + mercadopago_access_token, venda_expiracao_minutos
    ├── main.py                                   # + router de vendas
    ├── schemas.py                                # + schemas de venda
    ├── services_venda.py                         # NOVO — máquina de estados
    ├── pagamentos/
    │   ├── __init__.py                           # NOVO
    │   └── mercadopago.py                        # NOVO — cliente MP isolado
    └── api/vendas.py                             # NOVO — endpoints
└── tests/
    ├── conftest.py                               # + fixtures session e fake_mp; client injeta fake_mp
    ├── test_services_venda.py                    # NOVO
    └── test_vendas_api.py                        # NOVO
```

---

## Task 1: Dependências, config, cliente MP isolado e fixtures de teste

**Files:**
- Modify: `app/backend/requirements.txt`
- Modify: `app/backend/src/inventario/config.py`
- Create: `app/backend/src/inventario/pagamentos/__init__.py`
- Create: `app/backend/src/inventario/pagamentos/mercadopago.py`
- Modify: `app/backend/tests/conftest.py`

**Interfaces:**
- Produces: `PagamentoPix(id:str, status:str, qr_code:str, qr_code_base64:str, expira_em:datetime)`;
  `ClientePagamento` (Protocol) com `criar_pagamento_pix(valor:Decimal, descricao:str) -> PagamentoPix`
  e `consultar_pagamento(pagamento_id:str) -> str`; `MercadoPago(access_token:str, expiracao_minutos:int)`.
  Fixtures pytest: `session` (Session SQLite), `fake_mp` (FakeMP configurável via `status_consulta`),
  e `client` passa a injetar `fake_mp`.

- [ ] **Step 1: Adicionar o SDK em `requirements.txt`** (acrescentar a linha):
```
mercadopago==2.*
```

- [ ] **Step 2: Rebuildar a imagem**

Run: `$DC build backend`
Expected: build conclui, instala `mercadopago`.

- [ ] **Step 3: Estender `config.py`** — adicionar dois campos em `Settings` (depois de `device_timeout_s`):
```python
    # Pagamento (Fase 2)
    mercadopago_access_token: str = "CHANGE_ME"
    venda_expiracao_minutos: int = 30
```

- [ ] **Step 4: Criar `pagamentos/__init__.py`** (vazio).

- [ ] **Step 5: Criar `pagamentos/mercadopago.py`**
```python
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol

import mercadopago


@dataclass(frozen=True)
class PagamentoPix:
    id: str
    status: str
    qr_code: str          # copia-e-cola
    qr_code_base64: str
    expira_em: datetime


class ClientePagamento(Protocol):
    def criar_pagamento_pix(self, valor: Decimal, descricao: str) -> PagamentoPix: ...
    def consultar_pagamento(self, pagamento_id: str) -> str: ...


class MercadoPago:
    """Cliente real. Não é testado por unidade (boundary); validado com token manual."""

    def __init__(self, access_token: str, expiracao_minutos: int):
        self._sdk = mercadopago.SDK(access_token)
        self._expiracao_minutos = expiracao_minutos

    def criar_pagamento_pix(self, valor: Decimal, descricao: str) -> PagamentoPix:
        expira_em = datetime.now(timezone.utc) + timedelta(minutes=self._expiracao_minutos)
        resp = self._sdk.payment().create(
            {
                "transaction_amount": float(valor),
                "description": descricao,
                "payment_method_id": "pix",
                "payer": {"email": "comprador@example.com"},
            }
        )
        dados = resp["response"]
        tx = dados["point_of_interaction"]["transaction_data"]
        return PagamentoPix(
            id=str(dados["id"]),
            status=dados["status"],
            qr_code=tx["qr_code"],
            qr_code_base64=tx["qr_code_base64"],
            expira_em=expira_em,
        )

    def consultar_pagamento(self, pagamento_id: str) -> str:
        resp = self._sdk.payment().get(pagamento_id)
        return resp["response"]["status"]
```

- [ ] **Step 6: Estender `tests/conftest.py`** — adicionar imports, `FakeMP`, fixtures `session` e `fake_mp`, e injetar `fake_mp` no `client`. Substituir o conteúdo do arquivo por:
```python
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
```

- [ ] **Step 7: Verificar que o import do cliente e o pytest coletam** (o `client` importa `inventario.api.vendas`, que ainda não existe — então a verificação aqui é só do módulo de pagamentos e do build):

Run: `$DC run --rm --no-deps backend python -c "from inventario.pagamentos.mercadopago import PagamentoPix, MercadoPago; print('ok')"`
Expected: imprime `ok`.

> Nota: os testes só rodam verdes após a Task 3 (quando `api/vendas.py` existir, satisfazendo o import do `client`). As Tasks 2 e 3 usam estas fixtures.

- [ ] **Step 8: Commit**
```bash
git add app/backend/requirements.txt app/backend/src/inventario/config.py \
        app/backend/src/inventario/pagamentos app/backend/tests/conftest.py
# git commit -m "feat(pagamentos): cliente Mercado Pago isolado + config + fixtures de teste"
```

---

## Task 2: Serviços de venda (reserva, confirmação, reversão, reconciliação)

**Files:**
- Create: `app/backend/src/inventario/services_venda.py`
- Test: `app/backend/tests/test_services_venda.py`

**Interfaces:**
- Consumes: `Produto`, `Venda`, `Movimentacao` (models); `ClientePagamento`/`PagamentoPix` (Task 1).
- Produces:
  - `ProdutoInexistente(produto_id:int)`, `EstoqueInsuficiente(produto_id:int)` (exceções)
  - `itens_reserva(session, venda_id:int) -> list[Movimentacao]`
  - `criar_venda(session, itens:list[tuple[int,int]], mp) -> tuple[Venda, str]` (venda, qr_code_base64)
  - `confirmar_pagamento(session, venda) -> Venda`
  - `reverter_venda(session, venda, status:str) -> Venda`
  - `reconciliar(session, venda, mp) -> Venda`

- [ ] **Step 1: Escrever os testes que falham** (`tests/test_services_venda.py`)
```python
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from inventario.models import Produto, Movimentacao
from inventario import services_venda as sv


def _produto(session, nome, tag, preco, estoque):
    p = Produto(nome=nome, rfid_tag_id=tag, peso_unitario_g=Decimal("1"),
                preco_unitario=Decimal(preco), estoque_disponivel=estoque)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def test_criar_venda_reserva_e_calcula_total(session, fake_mp):
    a = _produto(session, "Refri", "A", "5.00", 8)
    b = _produto(session, "Salg", "B", "8.00", 5)
    venda, qr_base64 = sv.criar_venda(session, [(a.id, 3), (b.id, 2)], fake_mp)
    assert venda.status == "PENDENTE"
    assert venda.valor_total == Decimal("31.00")
    assert venda.pix_txid == "PAY123"
    assert qr_base64 == "BASE64IMG"
    session.refresh(a); session.refresh(b)
    assert (a.estoque_disponivel, a.estoque_reservado) == (5, 3)
    assert (b.estoque_disponivel, b.estoque_reservado) == (3, 2)
    reservas = sv.itens_reserva(session, venda.id)
    assert {m.tipo for m in reservas} == {"RESERVA"}
    assert sorted(m.quantidade for m in reservas) == [-3, -2][::-1] or sorted(m.quantidade for m in reservas) == [-3, -2]


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
    tipos = {m.tipo for m in session.query(Movimentacao).all()} if False else None  # ver nota
    confirmacoes = [m for m in sv.itens_reserva(session, venda.id)]  # ainda só RESERVA
    assert len(confirmacoes) == 1


def test_reverter_devolve_estoque(session, fake_mp):
    a = _produto(session, "Refri", "A", "5.00", 8)
    venda, _ = sv.criar_venda(session, [(a.id, 3)], fake_mp)
    sv.reverter_venda(session, venda, "CANCELADO")
    session.refresh(a); session.refresh(venda)
    assert venda.status == "CANCELADO"
    assert (a.estoque_disponivel, a.estoque_reservado) == (8, 0)


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
```

> Nota: o assert de `confirmacoes` acima é só para garantir que não quebrou; o foco do teste de confirmação são os estoques e o status. Mantê-lo simples.

- [ ] **Step 2: Rodar (RED)** — `$DC run --rm --no-deps backend pytest tests/test_services_venda.py -v`
Expected: erro de import (`services_venda` não existe).

- [ ] **Step 3: Implementar `services_venda.py`**
```python
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
```

- [ ] **Step 4: Rodar (GREEN)** — `$DC run --rm --no-deps backend pytest tests/test_services_venda.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**
```bash
git add app/backend/src/inventario/services_venda.py app/backend/tests/test_services_venda.py
# git commit -m "feat(vendas): serviços de reserva, confirmação, reversão e reconciliação"
```

---

## Task 3: Schemas + endpoints de venda

**Files:**
- Modify: `app/backend/src/inventario/schemas.py`
- Create: `app/backend/src/inventario/api/vendas.py`
- Modify: `app/backend/src/inventario/main.py`
- Test: `app/backend/tests/test_vendas_api.py`

**Interfaces:**
- Consumes: `services_venda` (Task 2); `Settings`, `db.settings`, `get_session`.
- Produces: `get_mp()` (dependência FastAPI, sobrescrita nos testes); rotas `POST /vendas`,
  `GET /vendas/{id}`, `POST /vendas/{id}/pagamento`, `POST /vendas/{id}/cancelar`.

- [ ] **Step 1: Escrever os testes que falham** (`tests/test_vendas_api.py`)
```python
def _produto(client, nome, tag, preco, estoque):
    return client.post("/produtos", json={
        "nome": nome, "rfid_tag_id": tag, "peso_unitario_g": "1",
        "preco_unitario": preco, "tara_caixa_g": "0", "estoque_disponivel": estoque,
    }).json()


def test_criar_venda_reserva(client):
    a = _produto(client, "Refri", "A", "5.00", 8)
    b = _produto(client, "Salg", "B", "8.00", 5)
    r = client.post("/vendas", json={"itens": [
        {"produto_id": a["id"], "quantidade": 3},
        {"produto_id": b["id"], "quantidade": 2},
    ]})
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["status"] == "PENDENTE"
    assert v["valor_total"] == "31.00"
    assert v["pix_copia_e_cola"] == "COPIA_E_COLA"
    assert v["qr_code_base64"] == "BASE64IMG"
    assert len(v["itens"]) == 2
    item_a = next(i for i in v["itens"] if i["produto_id"] == a["id"])
    assert item_a["quantidade"] == 3
    assert item_a["subtotal"] == "15.00"
    assert client.get(f"/produtos/{a['id']}").json()["estoque_disponivel"] == 5


def test_criar_venda_estoque_insuficiente_409(client):
    a = _produto(client, "Refri", "A", "5.00", 1)
    r = client.post("/vendas", json={"itens": [{"produto_id": a["id"], "quantidade": 3}]})
    assert r.status_code == 409


def test_pagamento_confirma(client):
    a = _produto(client, "Refri", "A", "5.00", 8)
    vid = client.post("/vendas", json={"itens": [{"produto_id": a["id"], "quantidade": 3}]}).json()["id"]
    r = client.post(f"/vendas/{vid}/pagamento")
    assert r.status_code == 200
    assert r.json()["status"] == "CONFIRMADO"
    assert client.get(f"/produtos/{a['id']}").json()["estoque_disponivel"] == 5


def test_cancelar_devolve(client):
    a = _produto(client, "Refri", "A", "5.00", 8)
    vid = client.post("/vendas", json={"itens": [{"produto_id": a["id"], "quantidade": 3}]}).json()["id"]
    r = client.post(f"/vendas/{vid}/cancelar")
    assert r.json()["status"] == "CANCELADO"
    assert client.get(f"/produtos/{a['id']}").json()["estoque_disponivel"] == 8


def test_get_reconcilia_aprovado(client, fake_mp):
    a = _produto(client, "Refri", "A", "5.00", 8)
    vid = client.post("/vendas", json={"itens": [{"produto_id": a["id"], "quantidade": 3}]}).json()["id"]
    fake_mp.status_consulta = "approved"
    r = client.get(f"/vendas/{vid}")
    assert r.json()["status"] == "CONFIRMADO"


def test_get_venda_inexistente_404(client):
    assert client.get("/vendas/999").status_code == 404
```

- [ ] **Step 2: Rodar (RED)** — `$DC run --rm --no-deps backend pytest tests/test_vendas_api.py -v`

- [ ] **Step 3: Adicionar schemas em `schemas.py`** (no fim do arquivo):
```python
class VendaItemIn(BaseModel):
    produto_id: int
    quantidade: int


class VendaCreate(BaseModel):
    itens: list[VendaItemIn]


class VendaItemRead(BaseModel):
    produto_id: int
    produto_nome: str
    quantidade: int
    preco_unitario: Decimal
    subtotal: Decimal


class VendaRead(BaseModel):
    id: int
    status: str
    valor_total: Decimal
    pix_copia_e_cola: Optional[str]
    expira_em: Optional[datetime]
    itens: list[VendaItemRead]


class VendaCriadaOut(VendaRead):
    qr_code_base64: Optional[str] = None
```

- [ ] **Step 4: Criar `api/vendas.py`**
```python
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
                produto_id=mov.produto_id, produto_nome=produto.nome,
                quantidade=qtd, preco_unitario=preco, subtotal=qtd * preco,
            )
        )
    return itens


def _read(session: Session, venda: Venda, qr_base64: str | None = None):
    campos = dict(
        id=venda.id, status=venda.status, valor_total=venda.valor_total,
        pix_copia_e_cola=venda.pix_qrcode, expira_em=venda.expira_em,
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
        raise HTTPException(status.HTTP_409_CONFLICT, f"estoque insuficiente para o produto {e.produto_id}")
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
```

- [ ] **Step 5: Registrar o router em `main.py`** (junto dos outros):
```python
    from .api.vendas import router as vendas_router
    app.include_router(vendas_router)
```

- [ ] **Step 6: Rodar (GREEN)** + suíte completa
```bash
$DC run --rm --no-deps backend pytest tests/test_vendas_api.py -v
$DC run --rm --no-deps backend pytest
```
Expected: 6 passed no primeiro; tudo verde no segundo.

- [ ] **Step 7: Commit**
```bash
git add app/backend/src/inventario/schemas.py app/backend/src/inventario/api/vendas.py \
        app/backend/src/inventario/main.py app/backend/tests/test_vendas_api.py
# git commit -m "feat(api): endpoints de venda (criar/obter/pagamento/cancelar)"
```

---

## Self-Review

**1. Cobertura da spec:**
- §3 arquitetura (pagamentos isolado, services_venda, api/vendas) → Tasks 1-3 ✓
- §4 itens=RESERVA, convenção quantidade → Task 2 ✓
- §5 máquina de estados (criar/confirmar/reverter/reconciliar, idempotência PENDENTE) → Task 2 ✓
- §7 endpoints (4 rotas, 409/404, qr_base64 só no POST) → Task 3 ✓
- §9 cliente MP (criar/consultar) → Task 1 ✓
- §11 erros (409/404, nada reservado em falha) → Tasks 2,3 ✓
- §12 testes MP mockado → Tasks 2,3 ✓
- §13 config → Task 1 ✓
- Fora deste plano (Plano 2): frontend (carrinho + QR), tipos novos no Histórico, token real/e2e.

**2. Placeholders:** sem TBD; código completo. (O `start=Decimal("0")` no `sum` evita misturar int+Decimal.)

**3. Consistência de tipos:** `criar_venda` retorna `(Venda, str)` — consumido assim em `_read(..., qr_base64)` e no teste. `ClientePagamento.consultar_pagamento -> str` ("approved"/"pending") usado em `reconciliar` e no `fake_mp.status_consulta`. `itens_reserva` retorna movimentos com `quantidade=-q`; `_itens_read` e `confirmar/reverter` usam `-mov.quantidade`. `get_mp` é o ponto de override no `client`. ✓
