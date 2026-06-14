# Fase 1 — Backend Dockerizado: Fundação e Domínio de Inventário — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Commits são do usuário:** os passos "Commit" mostram a mensagem sugerida, mas **quem roda `git commit` é o usuário**. Ao chegar num passo de commit, faça o `git add` proposto, pare e ofereça a mensagem — não commite sozinho.
>
> **Tudo roda dentro do Docker:** o host não tem `pip`/`venv`. A Tarefa 1 cria a fundação Docker; todas as tarefas seguintes constroem e testam **dentro do container** (`docker compose run --rm backend pytest`). Nada de Python é instalado no host.

**Goal:** Estabelecer a fundação Docker (Postgres + container de backend Python) e, dentro dela, a lógica de domínio do inventário testada (estabilização de peso e reconciliação por peso → movimento pendente), os modelos SQLModel e o schema do banco via Alembic.

**Architecture:** `docker-compose.yml` sobe `db` (Postgres 16, com volume e healthcheck) e `backend` (imagem Python com as dependências instaladas; código entra por bind mount do repo). A lógica de negócio é **pura** em `app/backend/src/inventario/domain/`, testável com pytest. Os modelos SQLModel espelham a DDL; o banco é criado por uma migration Alembic hand-written que reproduz exatamente a DDL v2 (CHECK constraints, índices e trigger). Sem leitura serial, API ou frontend neste plano.

**Tech Stack:** Docker + Docker Compose, Python 3.13 (em container), FastAPI (próximos planos), SQLModel, psycopg 3, Alembic, pydantic-settings, pytest, PostgreSQL 16.

**Refinamento da spec §3.1:** o `alembic.ini` fica na raiz do repo e o `script_location` aponta para `database/migrations/`; o `env.py` adiciona `app/backend/src` ao path para importar os models. A `database/schema.sql` genérica é removida. O `backend` monta o repo inteiro em `/repo` para enxergar tanto `app/backend` quanto `database/`.

---

## File Structure

```
inventario/
├── docker-compose.yml                       # NOVO — db + backend
├── .env                                      # NOVO — local, gitignored (credenciais/vars)
├── .env.example                              # ATUALIZADO — Postgres local (era Supabase)
├── alembic.ini                               # NOVO — script_location = database/migrations
├── database/
│   ├── schema.sql                            # REMOVIDO (DDL genérica antiga)
│   └── migrations/                           # NOVO — Alembic
│       ├── env.py
│       ├── script.py.mako
│       └── versions/0001_schema_inicial.py
└── app/
    └── backend/                              # NOVO (reorg de app/ flat → app/backend)
        ├── Dockerfile                        # NOVO
        ├── requirements.txt
        ├── pytest.ini
        └── src/inventario/
        │   ├── __init__.py
        │   ├── config.py                     # settings via env
        │   ├── models.py                     # SQLModel: Produto, Venda, Movimentacao
        │   └── domain/
        │       ├── __init__.py
        │       ├── weight.py                 # buffer de estabilização
        │       └── inventory.py              # reconciliação → PendingMovement
        └── tests/
            ├── __init__.py
            ├── test_config.py
            ├── test_weight.py
            ├── test_inventory.py
            └── test_models.py
```

Comandos de referência (rodados da raiz do repo):
- Build: `docker compose build backend`
- Testes: `docker compose run --rm backend pytest <args>`
- Migration: `docker compose run --rm -w /repo backend alembic upgrade head`

---

## Task 1: Fundação Docker (db + backend)

**Files:**
- Create: `app/backend/requirements.txt`
- Create: `app/backend/Dockerfile`
- Create: `app/backend/pytest.ini`
- Create: `app/backend/src/inventario/__init__.py`
- Create: `app/backend/src/inventario/domain/__init__.py`
- Create: `app/backend/tests/__init__.py`
- Create: `docker-compose.yml`
- Create: `.env`
- Modify: `.env.example`

- [ ] **Step 1: Criar a estrutura de pastas e arquivos de pacote vazios**

```bash
cd app/backend
mkdir -p src/inventario/domain tests
touch src/inventario/__init__.py src/inventario/domain/__init__.py tests/__init__.py
cd ../..
```

- [ ] **Step 2: Criar `app/backend/requirements.txt`**

```
fastapi==0.115.*
uvicorn[standard]==0.32.*
sqlmodel==0.0.22
psycopg[binary]==3.2.*
alembic==1.13.*
pyserial==3.5
pydantic-settings==2.*
pytest==8.*
```

- [ ] **Step 3: Criar `app/backend/pytest.ini`**

```ini
[pytest]
pythonpath = src
testpaths = tests
```

- [ ] **Step 4: Criar `app/backend/Dockerfile`**

```dockerfile
FROM python:3.13-slim

WORKDIR /repo/app/backend

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Em dev o código entra por bind mount; a cópia mantém a imagem utilizável standalone.
COPY . /repo/app/backend

# Mantido vivo para `docker compose run` sobrescrever com o comando desejado.
CMD ["sleep", "infinity"]
```

- [ ] **Step 5: Criar `docker-compose.yml` na raiz do repo**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 3s
      timeout: 3s
      retries: 10
    ports:
      - "5432:5432"

  backend:
    build: ./app/backend
    working_dir: /repo/app/backend
    volumes:
      - ./:/repo
    env_file: .env
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

- [ ] **Step 6: Criar `.env` na raiz do repo** (gitignored)

```
POSTGRES_USER=inventario
POSTGRES_PASSWORD=inventario
POSTGRES_DB=inventario
DATABASE_URL=postgresql+psycopg://inventario:inventario@db:5432/inventario
SERIAL_PORT=/dev/ttyUSB0
SERIAL_BAUD=115200
WEIGHT_STABILITY_SAMPLES=3
WEIGHT_STABILITY_TOLERANCE_G=2.0
ROUNDING_TOLERANCE_UNITS=0.4
EMPTY_SCALE_TOLERANCE_G=5.0
DEVICE_TIMEOUT_S=5
MERCADOPAGO_ACCESS_TOKEN=CHANGE_ME
```

- [ ] **Step 7: Atualizar `.env.example`** (sobrescrever o conteúdo antigo do Supabase)

```
# Banco (Postgres local containerizado)
POSTGRES_USER=inventario
POSTGRES_PASSWORD=troque_esta_senha
POSTGRES_DB=inventario
DATABASE_URL=postgresql+psycopg://inventario:troque_esta_senha@db:5432/inventario

# Dispositivo serial (descubra com: ls /dev/ttyUSB* /dev/ttyACM*)
SERIAL_PORT=/dev/ttyUSB0
SERIAL_BAUD=115200

# Lógica de inventário
WEIGHT_STABILITY_SAMPLES=3
WEIGHT_STABILITY_TOLERANCE_G=2.0
ROUNDING_TOLERANCE_UNITS=0.4
EMPTY_SCALE_TOLERANCE_G=5.0
DEVICE_TIMEOUT_S=5

# Fase 2 (PIX / Mercado Pago) — inerte na Fase 1
MERCADOPAGO_ACCESS_TOKEN=CHANGE_ME
```

- [ ] **Step 8: Buildar a imagem do backend**

Run: `docker compose build backend`
Expected: build conclui; `pip install` instala as dependências sem erro.

- [ ] **Step 9: Verificar que as dependências importam dentro do container**

Run:
```bash
docker compose run --rm backend python -c "import fastapi, sqlmodel, alembic, serial, psycopg; print('deps OK')"
```
Expected: imprime `deps OK` (e sobe/derruba o `db` automaticamente pela dependência).

- [ ] **Step 10: Verificar que o Postgres sobe saudável**

Run:
```bash
docker compose up -d db
docker compose exec db pg_isready -U inventario -d inventario
docker compose down
```
Expected: `accepting connections`.

- [ ] **Step 11: Commit** (usuário roda)

```bash
git add app/backend/requirements.txt app/backend/Dockerfile app/backend/pytest.ini \
        app/backend/src app/backend/tests docker-compose.yml .env.example
# .env é gitignored — não entra
# git commit -m "chore(infra): fundação Docker (Postgres + backend Python)"
```

---

## Task 2: Configuração via ambiente (`config.py`)

**Files:**
- Create: `app/backend/src/inventario/config.py`
- Test: `app/backend/tests/test_config.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_config.py
from decimal import Decimal
from inventario.config import Settings


def test_defaults_quando_so_database_url_e_serial_port_definidos(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/inv")
    monkeypatch.setenv("SERIAL_PORT", "/dev/ttyUSB0")
    s = Settings()
    assert s.serial_baud == 115200
    assert s.weight_stability_samples == 3
    assert s.weight_stability_tolerance_g == Decimal("2.0")
    assert s.rounding_tolerance_units == Decimal("0.4")
    assert s.empty_scale_tolerance_g == Decimal("5.0")
    assert s.device_timeout_s == 5


def test_le_overrides_do_ambiente(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/inv")
    monkeypatch.setenv("SERIAL_PORT", "/dev/ttyACM0")
    monkeypatch.setenv("SERIAL_BAUD", "9600")
    monkeypatch.setenv("WEIGHT_STABILITY_SAMPLES", "5")
    s = Settings()
    assert s.serial_port == "/dev/ttyACM0"
    assert s.serial_baud == 9600
    assert s.weight_stability_samples == 5
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `docker compose run --rm backend pytest tests/test_config.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'inventario.config'`

- [ ] **Step 3: Implementar `config.py`**

```python
# src/inventario/config.py
from decimal import Decimal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False)

    # Banco / serial
    database_url: str
    serial_port: str
    serial_baud: int = 115200

    # Lógica de inventário
    weight_stability_samples: int = 3
    weight_stability_tolerance_g: Decimal = Decimal("2.0")
    rounding_tolerance_units: Decimal = Decimal("0.4")
    empty_scale_tolerance_g: Decimal = Decimal("5.0")
    device_timeout_s: int = 5
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `docker compose run --rm backend pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit** (usuário roda)

```bash
git add app/backend/src/inventario/config.py app/backend/tests/test_config.py
# git commit -m "feat(backend): configuração tipada via variáveis de ambiente"
```

---

## Task 3: Domínio — estabilização do peso (`domain/weight.py`)

**Files:**
- Create: `app/backend/src/inventario/domain/weight.py`
- Test: `app/backend/tests/test_weight.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_weight.py
from decimal import Decimal
from inventario.domain.weight import WeightBuffer


def make_buffer():
    return WeightBuffer(samples=3, tolerance_g=Decimal("2.0"))


def test_nao_estavel_antes_de_encher_o_buffer():
    b = make_buffer()
    b.add(Decimal("100.0"))
    b.add(Decimal("100.0"))
    assert b.is_stable() is False
    assert b.stable_value() is None


def test_estavel_quando_dentro_da_tolerancia():
    b = make_buffer()
    for v in ("100.0", "101.0", "100.5"):
        b.add(Decimal(v))
    assert b.is_stable() is True
    assert b.stable_value() == Decimal("100.5")  # média das 3 leituras


def test_nao_estavel_quando_uma_leitura_salta():
    b = make_buffer()
    for v in ("100.0", "100.5", "130.0"):
        b.add(Decimal(v))
    assert b.is_stable() is False
    assert b.stable_value() is None


def test_so_considera_as_ultimas_n_leituras():
    b = make_buffer()
    for v in ("130.0", "100.0", "100.5", "101.0"):
        b.add(Decimal(v))
    assert b.is_stable() is True  # a leitura 130.0 já saiu da janela de 3
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker compose run --rm backend pytest tests/test_weight.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'inventario.domain.weight'`

- [ ] **Step 3: Implementar `weight.py`**

```python
# src/inventario/domain/weight.py
from collections import deque
from decimal import Decimal


class WeightBuffer:
    """Mantém as últimas N leituras de peso e decide se estão estáveis."""

    def __init__(self, samples: int, tolerance_g: Decimal):
        self._samples = samples
        self._tolerance = Decimal(str(tolerance_g))
        self._buf: deque[Decimal] = deque(maxlen=samples)

    def add(self, peso_g: Decimal) -> None:
        self._buf.append(Decimal(str(peso_g)))

    def is_stable(self) -> bool:
        if len(self._buf) < self._samples:
            return False
        return (max(self._buf) - min(self._buf)) <= self._tolerance

    def stable_value(self) -> Decimal | None:
        if not self.is_stable():
            return None
        return sum(self._buf) / len(self._buf)
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker compose run --rm backend pytest tests/test_weight.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit** (usuário roda)

```bash
git add app/backend/src/inventario/domain/weight.py app/backend/tests/test_weight.py
# git commit -m "feat(backend): buffer de estabilização do peso"
```

---

## Task 4: Domínio — reconciliação por peso (`domain/inventory.py`)

Regra central da §7.3 da spec: peso estável + produto → movimento pendente.

**Files:**
- Create: `app/backend/src/inventario/domain/inventory.py`
- Test: `app/backend/tests/test_inventory.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_inventory.py
from decimal import Decimal
from inventario.domain.inventory import reconcile, ReconcileStatus


def base(**over):
    args = dict(
        produto_id=1,
        peso_g=Decimal("120.0"),
        tara_g=Decimal("40.0"),
        peso_unitario_g=Decimal("3.2"),
        estoque_disponivel=20,
        rounding_tolerance_units=Decimal("0.4"),
        empty_scale_tolerance_g=Decimal("5.0"),
    )
    args.update(over)
    return args


def test_entrada_gera_reposicao():
    # (120 - 40) / 3.2 = 25; estoque 20 -> +5
    r = reconcile(**base())
    assert r.status is ReconcileStatus.OK
    assert r.movement.tipo == "REPOSICAO"
    assert r.movement.quantidade == 5
    assert r.movement.qtd_fisica == 25
    assert r.movement.qtd_resultante == 25


def test_saida_gera_ajuste():
    # (110.4 - 40) / 3.2 = 22; estoque 25 -> -3
    r = reconcile(**base(peso_g=Decimal("110.4"), estoque_disponivel=25))
    assert r.status is ReconcileStatus.OK
    assert r.movement.tipo == "AJUSTE"
    assert r.movement.quantidade == -3
    assert r.movement.qtd_resultante == 22


def test_sem_mudanca_quando_delta_zero():
    r = reconcile(**base(estoque_disponivel=25))  # qtd_fisica 25 == estoque
    assert r.status is ReconcileStatus.NO_CHANGE
    assert r.movement is None


def test_caixa_fora_da_balanca():
    # peso 30 < tara 40 - tolerância 5
    r = reconcile(**base(peso_g=Decimal("30.0")))
    assert r.status is ReconcileStatus.EMPTY
    assert r.movement is None


def test_caixa_presente_e_vazia_e_valida():
    # peso ~ tara -> 0 unidades; estoque 4 -> AJUSTE -4
    r = reconcile(**base(peso_g=Decimal("40.0"), estoque_disponivel=4))
    assert r.status is ReconcileStatus.OK
    assert r.movement.qtd_fisica == 0
    assert r.movement.quantidade == -4


def test_leitura_imprecisa():
    # (121.5 - 40) / 3.2 = 25.468...; longe de inteiro > 0.4
    r = reconcile(**base(peso_g=Decimal("121.5")))
    assert r.status is ReconcileStatus.IMPRECISE
    assert r.movement is None
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker compose run --rm backend pytest tests/test_inventory.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'inventario.domain.inventory'`

- [ ] **Step 3: Implementar `inventory.py`**

```python
# src/inventario/domain/inventory.py
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


class ReconcileStatus(str, Enum):
    OK = "ok"
    EMPTY = "empty"          # caixa não está (totalmente) na balança
    IMPRECISE = "imprecise"  # leitura longe de um inteiro
    NO_CHANGE = "no_change"  # delta zero


@dataclass(frozen=True)
class PendingMovement:
    produto_id: int
    tipo: str           # 'REPOSICAO' | 'AJUSTE'
    quantidade: int     # com sinal: + entrada, - saída
    peso_g: Decimal
    qtd_fisica: int
    qtd_resultante: int


@dataclass(frozen=True)
class ReconcileResult:
    status: ReconcileStatus
    movement: PendingMovement | None = None


def reconcile(
    *,
    produto_id: int,
    peso_g: Decimal,
    tara_g: Decimal,
    peso_unitario_g: Decimal,
    estoque_disponivel: int,
    rounding_tolerance_units: Decimal,
    empty_scale_tolerance_g: Decimal,
) -> ReconcileResult:
    peso_g = Decimal(str(peso_g))
    tara_g = Decimal(str(tara_g))
    peso_unitario_g = Decimal(str(peso_unitario_g))

    # caixa não está (totalmente) na balança
    if peso_g < tara_g - Decimal(str(empty_scale_tolerance_g)):
        return ReconcileResult(ReconcileStatus.EMPTY)

    liquido = peso_g - tara_g
    if liquido < 0:
        liquido = Decimal(0)

    unidades = liquido / peso_unitario_g
    qtd_fisica = int(unidades.to_integral_value(rounding=ROUND_HALF_UP))

    if abs(unidades - qtd_fisica) > Decimal(str(rounding_tolerance_units)):
        return ReconcileResult(ReconcileStatus.IMPRECISE)

    delta = qtd_fisica - estoque_disponivel
    if delta == 0:
        return ReconcileResult(ReconcileStatus.NO_CHANGE)

    tipo = "REPOSICAO" if delta > 0 else "AJUSTE"
    movement = PendingMovement(
        produto_id=produto_id,
        tipo=tipo,
        quantidade=delta,
        peso_g=peso_g,
        qtd_fisica=qtd_fisica,
        qtd_resultante=qtd_fisica,
    )
    return ReconcileResult(ReconcileStatus.OK, movement)
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker compose run --rm backend pytest tests/test_inventory.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit** (usuário roda)

```bash
git add app/backend/src/inventario/domain/inventory.py app/backend/tests/test_inventory.py
# git commit -m "feat(backend): reconciliação por peso (movimento pendente)"
```

---

## Task 5: Modelos SQLModel (`models.py`)

Espelham a DDL v2 para uso do ORM nos próximos planos. A fonte da verdade do banco é a migration (Task 6).

**Files:**
- Create: `app/backend/src/inventario/models.py`
- Test: `app/backend/tests/test_models.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_models.py
from decimal import Decimal
from inventario.models import Produto, Movimentacao, Venda


def test_produto_tem_defaults_de_estoque():
    p = Produto(
        nome="Parafuso M6",
        rfid_tag_id="A1B2C3D4",
        peso_unitario_g=Decimal("3.2"),
        preco_unitario=Decimal("0.15"),
    )
    assert p.estoque_disponivel == 0
    assert p.estoque_reservado == 0
    assert p.tara_caixa_g == Decimal("0")


def test_tabelas_registradas_no_metadata():
    nomes = set(Produto.metadata.tables.keys())
    assert {"produtos", "vendas", "movimentacoes"} <= nomes
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker compose run --rm backend pytest tests/test_models.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'inventario.models'`

- [ ] **Step 3: Implementar `models.py`**

```python
# src/inventario/models.py
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class Produto(SQLModel, table=True):
    __tablename__ = "produtos"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(max_length=150)
    rfid_tag_id: str = Field(max_length=50, unique=True, index=True)
    peso_unitario_g: Decimal
    tara_caixa_g: Decimal = Field(default=Decimal("0"))
    preco_unitario: Decimal
    estoque_disponivel: int = Field(default=0)
    estoque_reservado: int = Field(default=0)
    criado_em: datetime = Field(default_factory=datetime.utcnow)
    atualizado_em: datetime = Field(default_factory=datetime.utcnow)


class Venda(SQLModel, table=True):
    __tablename__ = "vendas"

    id: Optional[int] = Field(default=None, primary_key=True)
    status: str = Field(default="PENDENTE", max_length=20)
    valor_total: Decimal = Field(default=Decimal("0"))
    pix_txid: Optional[str] = Field(default=None, max_length=100)
    pix_qrcode: Optional[str] = None
    criado_em: datetime = Field(default_factory=datetime.utcnow)
    confirmado_em: Optional[datetime] = None
    expira_em: Optional[datetime] = None


class Movimentacao(SQLModel, table=True):
    __tablename__ = "movimentacoes"

    id: Optional[int] = Field(default=None, primary_key=True)
    produto_id: int = Field(foreign_key="produtos.id")
    venda_id: Optional[int] = Field(default=None, foreign_key="vendas.id")
    tipo: str = Field(max_length=20)
    quantidade: int
    peso_g: Optional[Decimal] = None
    preco_unitario_snapshot: Optional[Decimal] = None
    criado_em: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker compose run --rm backend pytest tests/test_models.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit** (usuário roda)

```bash
git add app/backend/src/inventario/models.py app/backend/tests/test_models.py
# git commit -m "feat(backend): modelos SQLModel (produtos, vendas, movimentacoes)"
```

---

## Task 6: Schema do banco via Alembic + remoção da schema.sql antiga

Migration hand-written para reproduzir **exatamente** a DDL v2 (CHECK, índices, trigger).

**Files:**
- Delete: `database/schema.sql`
- Create: `alembic.ini`
- Create: `database/migrations/env.py`
- Create: `database/migrations/script.py.mako`
- Create: `database/migrations/versions/0001_schema_inicial.py`

- [ ] **Step 1: Remover a `schema.sql` genérica**

```bash
git rm database/schema.sql
```

- [ ] **Step 2: Criar `alembic.ini` na raiz do repo**

```ini
[alembic]
script_location = database/migrations
# DATABASE_URL é lido em env.py a partir do ambiente

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Criar `database/migrations/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: Criar `database/migrations/env.py`**

```python
# database/migrations/env.py
import os
import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Torna o pacote inventario importável (app/backend/src)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "backend" / "src"))

from inventario.models import SQLModel  # noqa: E402  (registra as tabelas)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 5: Criar a migration inicial `database/migrations/versions/0001_schema_inicial.py`**

```python
"""schema inicial (DDL v2)

Revision ID: 0001
Revises:
Create Date: 2026-06-14
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE produtos (
            id                  SERIAL          PRIMARY KEY,
            nome                VARCHAR(150)    NOT NULL,
            rfid_tag_id         VARCHAR(50)     NOT NULL UNIQUE,
            peso_unitario_g     NUMERIC(10,3)   NOT NULL,
            tara_caixa_g        NUMERIC(10,3)   NOT NULL DEFAULT 0,
            preco_unitario      NUMERIC(10,2)   NOT NULL,
            estoque_disponivel  INT             NOT NULL DEFAULT 0 CHECK (estoque_disponivel >= 0),
            estoque_reservado   INT             NOT NULL DEFAULT 0 CHECK (estoque_reservado  >= 0),
            criado_em           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            atualizado_em       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
        );

        CREATE TABLE vendas (
            id              SERIAL          PRIMARY KEY,
            status          VARCHAR(20)     NOT NULL DEFAULT 'PENDENTE'
                                CHECK (status IN ('PENDENTE','CONFIRMADO','CANCELADO','EXPIRADO')),
            valor_total     NUMERIC(10,2)   NOT NULL DEFAULT 0,
            pix_txid        VARCHAR(100)    UNIQUE,
            pix_qrcode      TEXT,
            criado_em       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            confirmado_em   TIMESTAMPTZ,
            expira_em       TIMESTAMPTZ
        );

        CREATE TABLE movimentacoes (
            id                      SERIAL          PRIMARY KEY,
            produto_id              INT             NOT NULL REFERENCES produtos(id),
            venda_id                INT             REFERENCES vendas(id),
            tipo                    VARCHAR(20)     NOT NULL
                                        CHECK (tipo IN ('RESERVA','CONFIRMACAO','REVERSAO','REPOSICAO','AJUSTE')),
            quantidade              INT             NOT NULL,
            peso_g                  NUMERIC(10,3),
            preco_unitario_snapshot NUMERIC(10,2),
            criado_em               TIMESTAMPTZ     NOT NULL DEFAULT NOW()
        );

        CREATE INDEX idx_produtos_rfid ON produtos(rfid_tag_id);
        CREATE INDEX idx_vendas_status ON vendas(status);
        CREATE INDEX idx_vendas_pix    ON vendas(pix_txid);
        CREATE INDEX idx_mov_produto   ON movimentacoes(produto_id);
        CREATE INDEX idx_mov_venda     ON movimentacoes(venda_id);

        CREATE OR REPLACE FUNCTION fn_atualizar_timestamp()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.atualizado_em = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_produtos_ts
            BEFORE UPDATE ON produtos
            FOR EACH ROW EXECUTE FUNCTION fn_atualizar_timestamp();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_produtos_ts ON produtos;
        DROP FUNCTION IF EXISTS fn_atualizar_timestamp();
        DROP TABLE IF EXISTS movimentacoes;
        DROP TABLE IF EXISTS vendas;
        DROP TABLE IF EXISTS produtos;
        """
    )
```

- [ ] **Step 6: Subir o `db` e aplicar a migration dentro do container**

Run (da raiz do repo):
```bash
docker compose up -d db
docker compose run --rm -w /repo backend alembic upgrade head
```
Expected: log do Alembic "Running upgrade  -> 0001, schema inicial" sem erros.

- [ ] **Step 7: Conferir as tabelas e a trigger; depois derrubar**

Run:
```bash
docker compose exec db psql -U inventario -d inventario -c "\dt"
docker compose exec db psql -U inventario -d inventario -c "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal;"
docker compose down
```
Expected: lista `produtos`, `vendas`, `movimentacoes`; trigger `trg_produtos_ts` presente.

- [ ] **Step 8: Commit** (usuário roda)

```bash
git add alembic.ini database/migrations
git rm database/schema.sql
# git commit -m "feat(db): schema inicial (DDL v2) via Alembic; remove schema.sql genérica"
```

---

## Self-Review

**1. Spec coverage (deste plano):**
- §3 Arquitetura (containers db + backend) → Task 1 ✓
- §4 Stack (SQLModel, Alembic, psycopg, Docker) → Tasks 1, 5, 6 ✓
- §5 Modelo de dados (DDL v2, CHECK, trigger, índices) → Task 6 + Task 5 ✓
- §7.2 Estabilização do peso → Task 3 ✓
- §7.3 Cálculo/reconciliação (entrada/saída/no-change/imprecisa/caixa fora) → Task 4 ✓
- §11 Config via ambiente + `.env.example` Postgres local → Tasks 1, 2 ✓
- §3.1 `database/` para migrations; remoção da schema.sql genérica → Task 6 ✓
- Fora do escopo deste plano (planos seguintes): serial reader, REST/WS, confirmação transacional, frontend, README, serviço uvicorn no compose. Sem lacunas dentro do escopo declarado.

**2. Placeholder scan:** nenhum TBD/TODO; todo passo de código tem o código completo. ✓

**3. Type consistency:** `reconcile(...)` → `ReconcileResult{status, movement}`; `PendingMovement{produto_id, tipo, quantidade, peso_g, qtd_fisica, qtd_resultante}` idêntico entre teste (Task 4) e implementação. `Settings` expõe os nomes consumidos (`weight_stability_*`, `rounding_tolerance_units`, `empty_scale_tolerance_g`). `WeightBuffer(samples, tolerance_g)` consistente. Nomes de env (`.env`/`.env.example`) batem com os campos de `Settings` (Task 2). ✓
