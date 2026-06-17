# Fase 1 — Fatia Vertical: Histórico (+ ajuste manual de estoque) — Implementation Plan

> **Commits são do usuário.** **Tudo roda em Docker.** Testes: `docker compose run --rm --no-deps backend pytest`.

**Goal:** Tela de Histórico (lista de movimentações com filtros) + a capacidade de gerar movimentações por **ajuste manual de estoque** (lógica transacional reutilizada depois pela balança).

**Architecture:** Um serviço `aplicar_ajuste_estoque` grava uma `movimentacao` (tipo derivado do sinal do delta) e atualiza `estoque_disponivel` numa transação. Endpoint POST para disparar o ajuste e GET para listar movimentações (com join no produto para o nome). Frontend ganha navegação simples (estado) e a página de Histórico; a página de Produtos ganha um ajuste de estoque inline para gerar dados.

**Decisões:**
- A DDL adotada **não persiste saldo resultante** por movimentação → a tabela do Histórico não tem essa coluna.
- `peso_g` fica `NULL` em ajuste manual (só a balança preenche peso).
- Navegação no frontend via estado (sem react-router) — 3 páginas só.

**Depende de:** Fatia Produtos (API + tela) — concluída.

---

## Task 1: Serviço de ajuste de estoque + endpoint

**Files:**
- Create: `app/backend/src/inventario/services.py`
- Modify: `app/backend/src/inventario/api/produtos.py` (endpoint POST ajustar-estoque)
- Modify: `app/backend/src/inventario/schemas.py` (AjusteEstoque, MovimentacaoRead)
- Test: `app/backend/tests/test_estoque.py`

- [ ] **Step 1: Testes que falham** (`tests/test_estoque.py`)

```python
def _produto(client, **over):
    p = {"nome": "Parafuso", "rfid_tag_id": "TAG1", "peso_unitario_g": "3.2",
         "tara_caixa_g": "40", "preco_unitario": "0.15", "estoque_disponivel": 20}
    p.update(over)
    return client.post("/produtos", json=p).json()


def test_ajuste_aumenta_estoque_gera_reposicao(client):
    pid = _produto(client)["id"]
    r = client.post(f"/produtos/{pid}/ajustar-estoque", json={"nova_quantidade": 25})
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["tipo"] == "REPOSICAO"
    assert m["quantidade"] == 5
    assert m["produto_nome"] == "Parafuso"
    # estoque atualizado
    assert client.get(f"/produtos/{pid}").json()["estoque_disponivel"] == 25


def test_ajuste_diminui_estoque_gera_ajuste(client):
    pid = _produto(client, rfid_tag_id="TAG2")["id"]
    r = client.post(f"/produtos/{pid}/ajustar-estoque", json={"nova_quantidade": 12})
    assert r.json()["tipo"] == "AJUSTE"
    assert r.json()["quantidade"] == -8


def test_ajuste_sem_mudanca_da_400(client):
    pid = _produto(client, rfid_tag_id="TAG3")["id"]
    r = client.post(f"/produtos/{pid}/ajustar-estoque", json={"nova_quantidade": 20})
    assert r.status_code == 400


def test_ajuste_produto_inexistente_404(client):
    r = client.post("/produtos/999/ajustar-estoque", json={"nova_quantidade": 5})
    assert r.status_code == 404
```

- [ ] **Step 2: Rodar (RED)** — `docker compose run --rm --no-deps backend pytest tests/test_estoque.py -v`

- [ ] **Step 3: Schemas** — adicionar em `schemas.py`:

```python
from datetime import datetime

class AjusteEstoque(BaseModel):
    nova_quantidade: int


class MovimentacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    produto_id: int
    produto_nome: str
    tipo: str
    quantidade: int
    peso_g: Optional[Decimal]
    criado_em: datetime
```

- [ ] **Step 4: Serviço** (`services.py`)

```python
from sqlmodel import Session
from .models import Movimentacao, Produto


class SemMudanca(Exception):
    pass


def aplicar_ajuste_estoque(session: Session, produto: Produto, nova_quantidade: int) -> Movimentacao:
    delta = nova_quantidade - produto.estoque_disponivel
    if delta == 0:
        raise SemMudanca()
    mov = Movimentacao(
        produto_id=produto.id,
        tipo="REPOSICAO" if delta > 0 else "AJUSTE",
        quantidade=delta,
        peso_g=None,
    )
    produto.estoque_disponivel = nova_quantidade
    session.add(mov)
    session.add(produto)
    session.commit()
    session.refresh(mov)
    return mov
```

- [ ] **Step 5: Endpoint** em `api/produtos.py` (adicionar imports e rota):

```python
from ..schemas import AjusteEstoque, MovimentacaoRead
from ..services import aplicar_ajuste_estoque, SemMudanca


@router.post("/{produto_id}/ajustar-estoque", response_model=MovimentacaoRead,
             status_code=status.HTTP_201_CREATED)
def ajustar_estoque(produto_id: int, dados: AjusteEstoque, session: Session = Depends(get_session)):
    produto = session.get(Produto, produto_id)
    if produto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "produto não encontrado")
    try:
        mov = aplicar_ajuste_estoque(session, produto, dados.nova_quantidade)
    except SemMudanca:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "estoque já está nesse valor")
    return MovimentacaoRead(
        id=mov.id, produto_id=mov.produto_id, produto_nome=produto.nome,
        tipo=mov.tipo, quantidade=mov.quantidade, peso_g=mov.peso_g, criado_em=mov.criado_em,
    )
```

- [ ] **Step 6: Rodar (GREEN)** — `... pytest tests/test_estoque.py -v` (4 passed)

- [ ] **Step 7: Commit**
```bash
git add app/backend/src/inventario/services.py app/backend/src/inventario/schemas.py \
        app/backend/src/inventario/api/produtos.py app/backend/tests/test_estoque.py
# git commit -m "feat(api): ajuste manual de estoque (gera movimentação transacional)"
```

---

## Task 2: Listagem de movimentações (com filtros)

**Files:**
- Create: `app/backend/src/inventario/api/movimentacoes.py`
- Modify: `app/backend/src/inventario/main.py` (incluir router)
- Test: `app/backend/tests/test_movimentacoes_api.py`

- [ ] **Step 1: Testes que falham**

```python
def _setup(client):
    p = client.post("/produtos", json={"nome": "Parafuso", "rfid_tag_id": "T1",
        "peso_unitario_g": "3.2", "tara_caixa_g": "40", "preco_unitario": "0.15",
        "estoque_disponivel": 20}).json()
    client.post(f"/produtos/{p['id']}/ajustar-estoque", json={"nova_quantidade": 25})
    client.post(f"/produtos/{p['id']}/ajustar-estoque", json={"nova_quantidade": 22})
    return p


def test_lista_movimentacoes(client):
    _setup(client)
    r = client.get("/movimentacoes")
    assert r.status_code == 200
    dados = r.json()
    assert len(dados) == 2
    assert dados[0]["produto_nome"] == "Parafuso"
    assert {d["tipo"] for d in dados} == {"REPOSICAO", "AJUSTE"}


def test_filtra_por_tipo(client):
    _setup(client)
    r = client.get("/movimentacoes", params={"tipo": "AJUSTE"})
    assert len(r.json()) == 1
    assert r.json()[0]["tipo"] == "AJUSTE"


def test_filtra_por_produto(client):
    p = _setup(client)
    r = client.get("/movimentacoes", params={"produto_id": p["id"]})
    assert len(r.json()) == 2
    r2 = client.get("/movimentacoes", params={"produto_id": 999})
    assert r2.json() == []
```

- [ ] **Step 2: Rodar (RED)**

- [ ] **Step 3: Router** (`api/movimentacoes.py`)

```python
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
            id=m.id, produto_id=m.produto_id, produto_nome=nome, tipo=m.tipo,
            quantidade=m.quantidade, peso_g=m.peso_g, criado_em=m.criado_em,
        )
        for m, nome in session.exec(q).all()
    ]
```

- [ ] **Step 4: Registrar em `main.py`** (junto do produtos_router):
```python
    from .api.movimentacoes import router as movimentacoes_router
    app.include_router(movimentacoes_router)
```

- [ ] **Step 5: Rodar (GREEN)** (3 passed) + suíte completa

- [ ] **Step 6: Commit**
```bash
git add app/backend/src/inventario/api/movimentacoes.py app/backend/src/inventario/main.py \
        app/backend/tests/test_movimentacoes_api.py
# git commit -m "feat(api): listagem de movimentações com filtros"
```

---

## Task 3: Navegação + página de Histórico (frontend)

**Files:**
- Modify: `app/frontend/src/api.ts` (Movimentacao, listarMovimentacoes)
- Modify: `app/frontend/src/components/Sidebar.tsx` (navegação por callback)
- Modify: `app/frontend/src/App.tsx` (estado de página)
- Create: `app/frontend/src/pages/Historico.tsx`

- [ ] **Step 1: api.ts** — adicionar:
```ts
export type Movimentacao = {
  id: number
  produto_id: number
  produto_nome: string
  tipo: string
  quantidade: number
  peso_g: string | null
  criado_em: string
}

export async function listarMovimentacoes(filtros: { produto_id?: number; tipo?: string } = {}): Promise<Movimentacao[]> {
  const qs = new URLSearchParams()
  if (filtros.produto_id) qs.set("produto_id", String(filtros.produto_id))
  if (filtros.tipo) qs.set("tipo", filtros.tipo)
  const r = await fetch(`${BASE}/movimentacoes?${qs.toString()}`)
  if (!r.ok) throw new Error("falha ao listar movimentações")
  return r.json()
}
```

- [ ] **Step 2: Sidebar** — receber página ativa e callback:
```tsx
type Pagina = "Operação" | "Produtos" | "Histórico"

export function Sidebar({ ativa, onSelect }: { ativa: Pagina; onSelect: (p: Pagina) => void }) {
  const itens: Pagina[] = ["Operação", "Produtos", "Histórico"]
  return (
    <aside className="w-48 shrink-0 border-r border-slate-700 bg-slate-900 p-3 text-slate-300">
      <div className="mb-4 font-bold text-white">≡ Inventário</div>
      <nav className="flex flex-col gap-1">
        {itens.map((label) => (
          <button
            key={label}
            onClick={() => onSelect(label)}
            className={`rounded-md px-3 py-2 text-left ${
              label === ativa ? "bg-slate-700 text-white" : "opacity-60 hover:opacity-100"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>
    </aside>
  )
}

export type { Pagina }
```

- [ ] **Step 3: App.tsx** — estado de página:
```tsx
import { useState } from "react"
import { Sidebar, type Pagina } from "./components/Sidebar"
import { Produtos } from "./pages/Produtos"
import { Historico } from "./pages/Historico"

export default function App() {
  const [pagina, setPagina] = useState<Pagina>("Produtos")
  return (
    <div className="flex min-h-screen bg-slate-950">
      <Sidebar ativa={pagina} onSelect={setPagina} />
      {pagina === "Produtos" && <Produtos />}
      {pagina === "Histórico" && <Historico />}
      {pagina === "Operação" && (
        <div className="flex-1 p-6 text-slate-400">Operação — em breve (depende da balança).</div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Página `pages/Historico.tsx`**
```tsx
import { useEffect, useState } from "react"
import { listarMovimentacoes, type Movimentacao } from "../api"

const TIPOS = ["", "REPOSICAO", "AJUSTE"]

function badge(tipo: string) {
  const cor = tipo === "REPOSICAO" ? "bg-emerald-900 text-emerald-300" : "bg-amber-900 text-amber-300"
  return <span className={`rounded-full px-2 py-0.5 text-xs ${cor}`}>{tipo}</span>
}

export function Historico() {
  const [movs, setMovs] = useState<Movimentacao[]>([])
  const [tipo, setTipo] = useState("")

  useEffect(() => {
    listarMovimentacoes(tipo ? { tipo } : {}).then(setMovs).catch(() => setMovs([]))
  }, [tipo])

  return (
    <div className="flex-1 p-4 text-sm text-slate-200">
      <h2 className="mb-3 text-lg font-bold text-white">Histórico de movimentações</h2>
      <div className="mb-3 flex gap-2">
        <select
          value={tipo}
          onChange={(e) => setTipo(e.target.value)}
          className="rounded border border-slate-600 bg-slate-900 px-2 py-1"
        >
          {TIPOS.map((t) => (
            <option key={t} value={t}>{t === "" ? "Todos os tipos" : t}</option>
          ))}
        </select>
      </div>
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-slate-700 text-left text-xs uppercase opacity-60">
            <th className="py-2">Data / hora</th>
            <th>Produto</th>
            <th>Tipo</th>
            <th>Qtd</th>
            <th>Peso lido</th>
          </tr>
        </thead>
        <tbody>
          {movs.map((m) => (
            <tr key={m.id} className="border-b border-slate-800">
              <td className="py-2">{new Date(m.criado_em).toLocaleString("pt-BR")}</td>
              <td className="text-white">{m.produto_nome}</td>
              <td>{badge(m.tipo)}</td>
              <td className={m.quantidade > 0 ? "text-emerald-400" : "text-red-400"}>
                {m.quantidade > 0 ? `+${m.quantidade}` : m.quantidade}
              </td>
              <td>{m.peso_g ? `${m.peso_g} g` : "—"}</td>
            </tr>
          ))}
          {movs.length === 0 && (
            <tr><td colSpan={5} className="py-4 opacity-50">Nenhuma movimentação.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 5: Verificar** — vite serve sem erro; navegar Produtos↔Histórico.

- [ ] **Step 6: Commit**
```bash
git add app/frontend/src
# git commit -m "feat(frontend): navegação + página de Histórico"
```

---

## Task 4: Ajustar estoque pela tela de Produtos (gera histórico)

**Files:**
- Modify: `app/frontend/src/api.ts` (ajustarEstoque)
- Modify: `app/frontend/src/pages/Produtos.tsx` (input + botão por linha)

- [ ] **Step 1: api.ts**
```ts
export async function ajustarEstoque(produtoId: number, nova_quantidade: number): Promise<void> {
  const r = await fetch(`${BASE}/produtos/${produtoId}/ajustar-estoque`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nova_quantidade }),
  })
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}))
    throw new Error(corpo.detail ?? "falha ao ajustar estoque")
  }
}
```

- [ ] **Step 2: Produtos.tsx** — adicionar coluna "Ajustar" com input numérico + botão que chama `ajustarEstoque(p.id, valor)` e recarrega a lista. Importar `ajustarEstoque`. Estado local `ajustes: Record<number, string>`.

```tsx
// no topo, junto dos outros imports:
import { ajustarEstoque, criarProduto, listarProdutos, type NovoProduto, type Produto } from "../api"

// dentro do componente:
const [ajustes, setAjustes] = useState<Record<number, string>>({})

async function aplicarAjuste(id: number) {
  const v = ajustes[id]
  if (v === undefined || v === "") return
  setErro(null)
  try {
    await ajustarEstoque(id, Number(v))
    setAjustes({ ...ajustes, [id]: "" })
    await carregar()
  } catch (e) {
    setErro((e as Error).message)
  }
}
```

Na tabela, adicionar um `<th>Ajustar</th>` no cabeçalho e, em cada linha, uma célula:
```tsx
<td>
  <div className="flex gap-1">
    <input
      type="number"
      placeholder="novo"
      className="w-16 rounded border border-slate-600 bg-slate-900 px-1"
      value={ajustes[p.id] ?? ""}
      onChange={(e) => setAjustes({ ...ajustes, [p.id]: e.target.value })}
    />
    <button
      onClick={() => aplicarAjuste(p.id)}
      className="rounded bg-sky-600 px-2 text-xs text-white"
    >
      OK
    </button>
  </div>
</td>
```
(Atualizar o `colSpan` do estado vazio de 7 para 8.)

- [ ] **Step 3: Verificar de ponta a ponta** — ajustar o estoque de um produto na tela de Produtos; conferir que o saldo muda e que a movimentação aparece no Histórico.

- [ ] **Step 4: Commit**
```bash
git add app/frontend/src
# git commit -m "feat(frontend): ajuste de estoque inline na tela de Produtos"
```

---

## Self-Review
- Histórico (lista + filtro) → Tasks 2,3. Geração de dados (ajuste manual = lógica de confirmação §7.4) → Tasks 1,4. ✓
- Sem placeholders; código completo. ✓
- Tipos: `MovimentacaoRead` (backend) ↔ `Movimentacao` (front) com os mesmos campos; `aplicar_ajuste_estoque` reutilizável pelo fluxo da balança depois. ✓
- Nota: "estoque resultante" ausente (a DDL adotada não persiste saldo por movimento).
