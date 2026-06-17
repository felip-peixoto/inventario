# Fase 1 — Fatia Vertical: Produtos (API + Tela) — Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax. **Commits são do usuário** — faça o `git add` proposto, pare e ofereça a mensagem; não commite sozinho. **Tudo roda em Docker** (host sem pip/node); testes via `docker compose run --rm [--no-deps] backend pytest`.

**Goal:** Entregar uma fatia vertical navegável: API REST de produtos (FastAPI) + tela de Produtos em React (listar e cadastrar), rodando em containers. Sem serial/WebSocket (deixados para o fim por serem o maior risco).

**Architecture:** Backend FastAPI expõe CRUD de `/produtos` sobre o Postgres (via SQLModel). Frontend React (Vite + TypeScript + Tailwind) consome a API. Ambos em containers no `docker-compose.yml`. Entrada de dados manual nesta fatia; captura pela balança virá com a serial.

**Tech Stack:** FastAPI, SQLModel, Uvicorn, pytest (SQLite em memória para testes de API), React + Vite + TypeScript + Tailwind, Docker Compose.

**Depende de:** Plano 1 (fundação Docker, models, schema Alembic) — concluído.

---

## File Structure

```
inventario/
├── docker-compose.yml                        # MODIFICAR: comando uvicorn + porta 8000 no backend; serviço frontend
└── app/
    ├── backend/src/inventario/
    │   ├── db.py                              # NOVO — engine + get_session
    │   ├── main.py                            # NOVO — app FastAPI + CORS + /health
    │   ├── schemas.py                         # NOVO — ProdutoCreate/Update/Read
    │   └── api/
    │       ├── __init__.py                    # NOVO
    │       └── produtos.py                    # NOVO — router CRUD
    ├── backend/tests/
    │   ├── conftest.py                        # NOVO — TestClient + SQLite override
    │   ├── test_health.py                     # NOVO
    │   └── test_produtos_api.py               # NOVO
    └── frontend/                              # NOVO — app React (Vite)
        ├── Dockerfile
        ├── package.json / vite / tailwind ... # scaffold
        └── src/
            ├── main.tsx, App.tsx
            ├── api.ts                          # cliente da API
            ├── components/Sidebar.tsx
            └── pages/Produtos.tsx
```

---

## Task 1: App FastAPI + sessão de banco + /health

**Files:**
- Create: `app/backend/src/inventario/db.py`
- Create: `app/backend/src/inventario/main.py`
- Create: `app/backend/tests/conftest.py`
- Create: `app/backend/tests/test_health.py`

- [ ] **Step 1: Escrever `tests/conftest.py`** (TestClient com SQLite em memória; substitui a sessão do Postgres)

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import inventario.models  # noqa: F401  (registra as tabelas no metadata)
from inventario.db import get_session
from inventario.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Escrever o teste que falha `tests/test_health.py`**

```python
# tests/test_health.py
def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 3: Rodar e confirmar que falha**

Run: `docker compose run --rm --no-deps backend pytest tests/test_health.py -v`
Expected: erro de import/coleta (`inventario.main`/`inventario.db` não existem).

- [ ] **Step 4: Implementar `db.py`**

```python
# src/inventario/db.py
from collections.abc import Iterator

from sqlmodel import Session, create_engine

from .config import Settings

settings = Settings()
engine = create_engine(settings.database_url, echo=False)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
```

- [ ] **Step 5: Implementar `main.py`**

```python
# src/inventario/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Inventário")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `docker compose run --rm --no-deps backend pytest tests/test_health.py -v`
Expected: PASS (1 passed)

- [ ] **Step 7: Commit** (usuário roda)

```bash
git add app/backend/src/inventario/db.py app/backend/src/inventario/main.py \
        app/backend/tests/conftest.py app/backend/tests/test_health.py
# git commit -m "feat(api): app FastAPI com /health e sessão de banco"
```

---

## Task 2: Schemas de Produto

**Files:**
- Create: `app/backend/src/inventario/schemas.py`
- Test: `app/backend/tests/test_schemas.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_schemas.py
from decimal import Decimal
from inventario.schemas import ProdutoRead


def test_peso_total_calculado():
    p = ProdutoRead(
        id=1,
        nome="Parafuso M6",
        rfid_tag_id="A1B2C3D4",
        peso_unitario_g=Decimal("3.2"),
        tara_caixa_g=Decimal("40"),
        preco_unitario=Decimal("0.15"),
        estoque_disponivel=25,
        estoque_reservado=0,
    )
    # 40 + 25 * 3.2 = 120.0
    assert p.peso_total_g == Decimal("120.0")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker compose run --rm --no-deps backend pytest tests/test_schemas.py -v`
Expected: FAIL (`No module named 'inventario.schemas'`)

- [ ] **Step 3: Implementar `schemas.py`**

```python
# src/inventario/schemas.py
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
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker compose run --rm --no-deps backend pytest tests/test_schemas.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit** (usuário roda)

```bash
git add app/backend/src/inventario/schemas.py app/backend/tests/test_schemas.py
# git commit -m "feat(api): schemas de produto (com peso_total calculado)"
```

---

## Task 3: Endpoints CRUD de Produtos

**Files:**
- Create: `app/backend/src/inventario/api/__init__.py`
- Create: `app/backend/src/inventario/api/produtos.py`
- Modify: `app/backend/src/inventario/main.py` (incluir o router)
- Test: `app/backend/tests/test_produtos_api.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_produtos_api.py
def _payload(**over):
    p = {
        "nome": "Parafuso M6",
        "rfid_tag_id": "A1B2C3D4",
        "peso_unitario_g": "3.2",
        "tara_caixa_g": "40",
        "preco_unitario": "0.15",
        "estoque_disponivel": 25,
    }
    p.update(over)
    return p


def test_criar_e_listar(client):
    r = client.post("/produtos", json=_payload())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] > 0
    assert body["peso_total_g"] == "120.0"

    r = client.get("/produtos")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_tag_duplicada_da_conflito(client):
    assert client.post("/produtos", json=_payload()).status_code == 201
    r = client.post("/produtos", json=_payload(nome="Outro"))
    assert r.status_code == 409


def test_get_update_delete(client):
    pid = client.post("/produtos", json=_payload()).json()["id"]

    r = client.get(f"/produtos/{pid}")
    assert r.status_code == 200

    r = client.put(f"/produtos/{pid}", json={"nome": "Parafuso M8"})
    assert r.status_code == 200
    assert r.json()["nome"] == "Parafuso M8"

    assert client.delete(f"/produtos/{pid}").status_code == 204
    assert client.get(f"/produtos/{pid}").status_code == 404


def test_get_inexistente_404(client):
    assert client.get("/produtos/999").status_code == 404
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker compose run --rm --no-deps backend pytest tests/test_produtos_api.py -v`
Expected: erro de coleta (`inventario.api.produtos` não existe).

- [ ] **Step 3: Criar `api/__init__.py` (vazio) e implementar `api/produtos.py`**

```python
# src/inventario/api/produtos.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..db import get_session
from ..models import Produto
from ..schemas import ProdutoCreate, ProdutoRead, ProdutoUpdate

router = APIRouter(prefix="/produtos", tags=["produtos"])


@router.get("", response_model=list[ProdutoRead])
def listar(session: Session = Depends(get_session)):
    return session.exec(select(Produto).order_by(Produto.nome)).all()


@router.post("", response_model=ProdutoRead, status_code=status.HTTP_201_CREATED)
def criar(dados: ProdutoCreate, session: Session = Depends(get_session)):
    produto = Produto(**dados.model_dump())
    session.add(produto)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "rfid_tag_id já cadastrado")
    session.refresh(produto)
    return produto


@router.get("/{produto_id}", response_model=ProdutoRead)
def obter(produto_id: int, session: Session = Depends(get_session)):
    produto = session.get(Produto, produto_id)
    if produto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "produto não encontrado")
    return produto


@router.put("/{produto_id}", response_model=ProdutoRead)
def atualizar(produto_id: int, dados: ProdutoUpdate, session: Session = Depends(get_session)):
    produto = session.get(Produto, produto_id)
    if produto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "produto não encontrado")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(produto, campo, valor)
    session.add(produto)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "rfid_tag_id já cadastrado")
    session.refresh(produto)
    return produto


@router.delete("/{produto_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(produto_id: int, session: Session = Depends(get_session)):
    produto = session.get(Produto, produto_id)
    if produto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "produto não encontrado")
    session.delete(produto)
    session.commit()
```

- [ ] **Step 4: Registrar o router em `main.py`**

Adicionar o import e o include dentro de `create_app()`:
```python
    from .api.produtos import router as produtos_router
    app.include_router(produtos_router)
```
(colocar antes do `return app`)

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `docker compose run --rm --no-deps backend pytest tests/test_produtos_api.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit** (usuário roda)

```bash
git add app/backend/src/inventario/api app/backend/src/inventario/main.py \
        app/backend/tests/test_produtos_api.py
# git commit -m "feat(api): CRUD de produtos"
```

---

## Task 4: Servir a API via uvicorn no compose

**Files:**
- Modify: `docker-compose.yml` (backend: comando uvicorn + porta 8000)

- [ ] **Step 1: Ajustar o serviço `backend`** — adicionar `command` e `ports`:

```yaml
  backend:
    build: ./app/backend
    working_dir: /repo/app/backend
    volumes:
      - ./:/repo
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    command: ["uvicorn", "inventario.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src", "--reload"]
    ports:
      - "8000:8000"
```

- [ ] **Step 2: Aplicar a migration e subir a API**

Run:
```bash
docker compose up -d db
docker compose run --rm -w /repo backend alembic upgrade head
docker compose up -d backend
```
Expected: backend sobe; sem erros no `docker compose logs backend`.

- [ ] **Step 3: Verificar a API de ponta a ponta (contra o Postgres real)**

Run:
```bash
curl -s -X POST localhost:8000/produtos -H 'Content-Type: application/json' \
  -d '{"nome":"Parafuso M6","rfid_tag_id":"A1B2C3D4","peso_unitario_g":"3.2","tara_caixa_g":"40","preco_unitario":"0.15","estoque_disponivel":25}'
echo; curl -s localhost:8000/produtos
```
Expected: o POST retorna o produto com `"peso_total_g":"120.0"`; o GET lista 1 produto.

- [ ] **Step 4: Derrubar**

Run: `docker compose down`

- [ ] **Step 5: Commit** (usuário roda)

```bash
git add docker-compose.yml
# git commit -m "feat(infra): servir a API via uvicorn no compose (porta 8000)"
```

---

## Task 5: Scaffold do frontend (Vite + React + TS + Tailwind) em Docker

**Files:**
- Create: `app/frontend/` (scaffold Vite), `app/frontend/Dockerfile`
- Modify: `docker-compose.yml` (serviço `frontend`)

- [ ] **Step 1: Criar o scaffold Vite dentro de um container Node** (evita Node no host)

Run (da raiz do repo):
```bash
docker run --rm -v "$PWD/app:/work" -w /work node:22-slim \
  npm create vite@latest frontend -- --template react-ts
```
Expected: cria `app/frontend/` com o template React+TS.

- [ ] **Step 2: Adicionar Tailwind ao projeto** — criar/garantir os arquivos:

`app/frontend/package.json` deve incluir as devDeps `tailwindcss`, `postcss`, `autoprefixer`. Run:
```bash
docker run --rm -v "$PWD/app/frontend:/work" -w /work node:22-slim \
  sh -c "npm install && npm install -D tailwindcss@3 postcss autoprefixer && npx tailwindcss init -p"
```

`app/frontend/tailwind.config.js`:
```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

`app/frontend/src/index.css` (substituir conteúdo):
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 3: Configurar o Vite para rodar acessível no container** — `app/frontend/vite.config.ts`:

```ts
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173 },
})
```

- [ ] **Step 4: Criar `app/frontend/Dockerfile`**

```dockerfile
FROM node:22-slim
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]
```

- [ ] **Step 5: Adicionar o serviço `frontend` ao `docker-compose.yml`**

```yaml
  frontend:
    build: ./app/frontend
    volumes:
      - ./app/frontend:/app
      - /app/node_modules
    ports:
      - "5173:5173"
    depends_on:
      - backend
```

- [ ] **Step 6: Subir e verificar que o dev server responde**

Run:
```bash
docker compose up -d --build frontend
sleep 5
curl -s -I localhost:5173 | head -1
```
Expected: `HTTP/1.1 200 OK` (página padrão do Vite). Abra `http://localhost:5173` no navegador para ver.

- [ ] **Step 7: Commit** (usuário roda)

```bash
git add app/frontend docker-compose.yml
# git commit -m "feat(frontend): scaffold Vite + React + TS + Tailwind em Docker"
```

---

## Task 6: Tela de Produtos (shell + tabela + cadastro) ligada à API

**Files:**
- Create: `app/frontend/src/api.ts`
- Create: `app/frontend/src/components/Sidebar.tsx`
- Create: `app/frontend/src/pages/Produtos.tsx`
- Modify: `app/frontend/src/App.tsx`, `app/frontend/src/main.tsx`

- [ ] **Step 1: Cliente da API `src/api.ts`**

```ts
const BASE = "http://localhost:8000"

export type Produto = {
  id: number
  nome: string
  rfid_tag_id: string
  peso_unitario_g: string
  tara_caixa_g: string
  preco_unitario: string
  estoque_disponivel: number
  estoque_reservado: number
  peso_total_g: string
}

export type NovoProduto = {
  nome: string
  rfid_tag_id: string
  peso_unitario_g: string
  tara_caixa_g: string
  preco_unitario: string
  estoque_disponivel: number
}

export async function listarProdutos(): Promise<Produto[]> {
  const r = await fetch(`${BASE}/produtos`)
  if (!r.ok) throw new Error("falha ao listar")
  return r.json()
}

export async function criarProduto(p: NovoProduto): Promise<Produto> {
  const r = await fetch(`${BASE}/produtos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(p),
  })
  if (!r.ok) throw new Error((await r.json()).detail ?? "falha ao criar")
  return r.json()
}
```

- [ ] **Step 2: Sidebar `src/components/Sidebar.tsx`** (estilo do mockup; Produtos ativo)

```tsx
const itens = [
  { label: "Operação", ativo: false },
  { label: "Produtos", ativo: true },
  { label: "Histórico", ativo: false },
]

export function Sidebar() {
  return (
    <aside className="w-48 shrink-0 border-r border-slate-700 bg-slate-900 p-3 text-slate-300">
      <div className="mb-4 font-bold text-white">≡ Inventário</div>
      <nav className="flex flex-col gap-1">
        {itens.map((i) => (
          <div
            key={i.label}
            className={`rounded-md px-3 py-2 ${i.ativo ? "bg-slate-700 text-white" : "opacity-60"}`}
          >
            {i.label}
          </div>
        ))}
      </nav>
    </aside>
  )
}
```

- [ ] **Step 3: Página `src/pages/Produtos.tsx`** (tabela com coluna Peso total + formulário de cadastro manual)

```tsx
import { useEffect, useState } from "react"
import { criarProduto, listarProdutos, type NovoProduto, type Produto } from "../api"

const vazio: NovoProduto = {
  nome: "", rfid_tag_id: "", peso_unitario_g: "", tara_caixa_g: "0",
  preco_unitario: "", estoque_disponivel: 0,
}

export function Produtos() {
  const [produtos, setProdutos] = useState<Produto[]>([])
  const [form, setForm] = useState<NovoProduto>(vazio)
  const [erro, setErro] = useState<string | null>(null)

  async function carregar() {
    setProdutos(await listarProdutos())
  }
  useEffect(() => { carregar() }, [])

  async function salvar(e: React.FormEvent) {
    e.preventDefault()
    setErro(null)
    try {
      await criarProduto({ ...form, estoque_disponivel: Number(form.estoque_disponivel) })
      setForm(vazio)
      await carregar()
    } catch (err) {
      setErro((err as Error).message)
    }
  }

  return (
    <div className="flex flex-1 gap-4 p-4 text-sm text-slate-200">
      <div className="flex-1">
        <h2 className="mb-3 text-lg font-bold text-white">Produtos</h2>
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-slate-700 text-left text-xs uppercase opacity-60">
              <th className="py-2">Nome</th><th>Tag</th><th>Peso u.</th>
              <th>Tara</th><th className="text-sky-300">Peso total</th>
              <th>Preço</th><th>Estoque</th>
            </tr>
          </thead>
          <tbody>
            {produtos.map((p) => (
              <tr key={p.id} className="border-b border-slate-800">
                <td className="py-2 text-white">{p.nome}</td>
                <td className="font-mono">{p.rfid_tag_id}</td>
                <td>{p.peso_unitario_g} g</td>
                <td>{p.tara_caixa_g} g</td>
                <td className="text-sky-300">{p.peso_total_g} g</td>
                <td>R$ {p.preco_unitario}</td>
                <td className="text-emerald-400">{p.estoque_disponivel}</td>
              </tr>
            ))}
            {produtos.length === 0 && (
              <tr><td colSpan={7} className="py-4 opacity-50">Nenhum produto ainda.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <form onSubmit={salvar} className="w-64 rounded-lg border border-slate-700 p-4">
        <h3 className="mb-3 font-semibold text-white">Novo produto</h3>
        {([
          ["nome", "Nome", "text"],
          ["rfid_tag_id", "Tag RFID", "text"],
          ["peso_unitario_g", "Peso unitário (g)", "text"],
          ["tara_caixa_g", "Tara (g)", "text"],
          ["preco_unitario", "Preço (R$)", "text"],
          ["estoque_disponivel", "Estoque inicial", "number"],
        ] as const).map(([campo, rotulo, tipo]) => (
          <label key={campo} className="mb-2 block">
            <span className="mb-1 block text-xs opacity-60">{rotulo}</span>
            <input
              type={tipo}
              className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1"
              value={(form as Record<string, string | number>)[campo]}
              onChange={(e) => setForm({ ...form, [campo]: e.target.value })}
              required={campo !== "tara_caixa_g"}
            />
          </label>
        ))}
        {erro && <p className="mb-2 text-xs text-red-400">{erro}</p>}
        <button className="mt-2 w-full rounded bg-emerald-500 py-2 font-bold text-emerald-950">
          Salvar produto
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 4: Montar o shell em `src/App.tsx`**

```tsx
import { Sidebar } from "./components/Sidebar"
import { Produtos } from "./pages/Produtos"

export default function App() {
  return (
    <div className="flex min-h-screen bg-slate-950">
      <Sidebar />
      <Produtos />
    </div>
  )
}
```

- [ ] **Step 5: Garantir o import do CSS em `src/main.tsx`**

Verificar que `src/main.tsx` importa `./index.css` (o template Vite já faz; se removeu, readicione).

- [ ] **Step 6: Verificar de ponta a ponta**

Run:
```bash
docker compose up -d db
docker compose run --rm -w /repo backend alembic upgrade head
docker compose up -d --build backend frontend
sleep 6
curl -s localhost:8000/produtos
curl -s -I localhost:5173 | head -1
```
Expected: API responde (lista JSON, possivelmente vazia `[]`); Vite responde 200. Abrir `http://localhost:5173`, cadastrar um produto pelo formulário e vê-lo aparecer na tabela com o **Peso total** calculado.

- [ ] **Step 7: Commit** (usuário roda)

```bash
git add app/frontend/src
# git commit -m "feat(frontend): tela de Produtos (listar + cadastrar) ligada à API"
```

---

## Self-Review

**1. Cobertura:** API de produtos (CRUD) → Tasks 1-4; tela de Produtos consumindo a API → Tasks 5-6. Tela visível ao fim da Task 6. Serial/WebSocket/Operação e captura pela balança: fora desta fatia (propositalmente, por serem o maior risco). ✓

**2. Placeholders:** sem TBD; código completo em cada passo. ✓

**3. Consistência de tipos:** `ProdutoRead.peso_total_g` (Decimal serializado como string) consumido como `string` em `api.ts`/tabela; `criarProduto` envia os mesmos campos de `ProdutoCreate`; `get_session` é o ponto de override nos testes (SQLite) e a sessão Postgres em produção. ✓

**Nota:** os campos numéricos chegam como string no JSON (Decimal). O formulário envia strings — compatível com `ProdutoCreate` (Pydantic faz o parse de Decimal a partir de string).
