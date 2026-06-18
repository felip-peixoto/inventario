# Fase 1 — Operação (beta manual, sem balança) — Implementation Plan

> **Commits são do usuário. Tudo roda em Docker.** Testes: `docker compose run --rm --no-deps backend pytest`.

**Goal:** Tela de Operação funcional com **entrada manual** no lugar da serial: escolher produto (dropdown) + digitar o peso → preview do movimento pendente (via `reconcile`) → Confirmar grava a movimentação (com `peso_g`) e atualiza o estoque. Quando a ESP32 entrar, ela só substitui os campos manuais pelo feed da serial; toda a lógica é reaproveitada.

**Architecture:** Dois endpoints novos — `/operacao/preview` (sem gravar, roda `reconcile`) e `/operacao/confirmar` (grava, transacional). Reaproveita `inventario.domain.inventory.reconcile` e o serviço de movimento (generalizado para registrar `peso_g`). Frontend: página Operação consumindo esses endpoints.

**Depende de:** domínio `reconcile` (Plano 1) e serviço de movimento (fatia Histórico) — prontos.

---

## Task 1: Backend — preview e confirmação por peso

**Files:**
- Modify: `app/backend/src/inventario/services.py` (peso_g opcional)
- Modify: `app/backend/src/inventario/schemas.py` (OperacaoIn, OperacaoPreviewOut)
- Create: `app/backend/src/inventario/api/operacao.py`
- Modify: `app/backend/src/inventario/main.py` (incluir router)
- Test: `app/backend/tests/test_operacao_api.py`

- [ ] **Step 1: Testes que falham** (`tests/test_operacao_api.py`)

```python
def _produto(client, **over):
    p = {"nome": "Parafuso", "rfid_tag_id": "T1", "peso_unitario_g": "3.2",
         "tara_caixa_g": "40", "preco_unitario": "0.15", "estoque_disponivel": 20}
    p.update(over)
    return client.post("/produtos", json=p).json()


def test_preview_entrada(client):
    pid = _produto(client)["id"]
    r = client.post("/operacao/preview", json={"produto_id": pid, "peso_g": "120"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "ok"
    assert b["tipo"] == "REPOSICAO"
    assert b["quantidade"] == 5
    assert b["qtd_fisica"] == 25
    assert b["qtd_resultante"] == 25
    assert b["estoque_atual"] == 20


def test_preview_caixa_fora(client):
    pid = _produto(client)["id"]
    r = client.post("/operacao/preview", json={"produto_id": pid, "peso_g": "30"})
    assert r.json()["status"] == "empty"
    assert r.json()["tipo"] is None


def test_preview_imprecisa(client):
    pid = _produto(client)["id"]
    r = client.post("/operacao/preview", json={"produto_id": pid, "peso_g": "121.5"})
    assert r.json()["status"] == "imprecise"


def test_confirmar_grava_com_peso(client):
    pid = _produto(client)["id"]
    r = client.post("/operacao/confirmar", json={"produto_id": pid, "peso_g": "110.4"})
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["tipo"] == "AJUSTE"
    assert m["quantidade"] == -2  # (110.4-40)/3.2 = 22 ; 22-20 = +2 -> espera AJUSTE? ver nota
    # estoque atualizado e peso registrado
    assert client.get(f"/produtos/{pid}").json()["estoque_disponivel"] == 22
    assert m["peso_g"] == "110.400"
    movs = client.get("/movimentacoes").json()
    assert movs[0]["peso_g"] == "110.400"


def test_confirmar_sem_mudanca_400(client):
    pid = _produto(client)["id"]  # estoque 20; peso p/ 20 unidades = 40 + 20*3.2 = 104
    r = client.post("/operacao/confirmar", json={"produto_id": pid, "peso_g": "104"})
    assert r.status_code == 400


def test_confirmar_produto_inexistente_404(client):
    r = client.post("/operacao/confirmar", json={"produto_id": 999, "peso_g": "120"})
    assert r.status_code == 404
```

> Nota de cálculo: peso 110.4 → (110.4−40)/3.2 = 22 unidades; estoque 20 → delta **+2** → tipo **REPOSICAO**, quantidade **+2**, estoque vira 22. **Corrigir o teste** para `tipo == "REPOSICAO"` e `quantidade == 2` no Step de escrita (o comentário acima registra o raciocínio; usar os valores certos no assert).

- [ ] **Step 2: Rodar (RED)** — `... pytest tests/test_operacao_api.py -v`

- [ ] **Step 3: Generalizar o serviço** (`services.py`) — adicionar `peso_g` opcional:

```python
from decimal import Decimal
from typing import Optional
from sqlmodel import Session
from .models import Movimentacao, Produto


class SemMudanca(Exception):
    """Levantada quando o ajuste não altera o estoque (delta zero)."""


def aplicar_ajuste_estoque(
    session: Session,
    produto: Produto,
    nova_quantidade: int,
    peso_g: Optional[Decimal] = None,
) -> Movimentacao:
    delta = nova_quantidade - produto.estoque_disponivel
    if delta == 0:
        raise SemMudanca()
    mov = Movimentacao(
        produto_id=produto.id,
        tipo="REPOSICAO" if delta > 0 else "AJUSTE",
        quantidade=delta,
        peso_g=peso_g,
    )
    produto.estoque_disponivel = nova_quantidade
    session.add(mov)
    session.add(produto)
    session.commit()
    session.refresh(mov)
    return mov
```

- [ ] **Step 4: Schemas** (`schemas.py`) — adicionar:

```python
class OperacaoIn(BaseModel):
    produto_id: int
    peso_g: Decimal


class OperacaoPreviewOut(BaseModel):
    status: str  # "ok" | "empty" | "imprecise" | "no_change"
    produto_id: int
    produto_nome: str
    estoque_atual: int
    peso_g: Decimal
    tipo: Optional[str] = None
    quantidade: Optional[int] = None
    qtd_fisica: Optional[int] = None
    qtd_resultante: Optional[int] = None
```

- [ ] **Step 5: Router** (`api/operacao.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..db import get_session, settings
from ..domain.inventory import ReconcileStatus, reconcile
from ..models import Produto
from ..schemas import MovimentacaoRead, OperacaoIn, OperacaoPreviewOut
from ..services import aplicar_ajuste_estoque

router = APIRouter(prefix="/operacao", tags=["operacao"])


def _reconciliar(produto: Produto, peso_g):
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
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"leitura não confirmável: {r.status.value}")
    mov = aplicar_ajuste_estoque(session, produto, r.movement.qtd_fisica, peso_g=dados.peso_g)
    return MovimentacaoRead(
        id=mov.id, produto_id=mov.produto_id, produto_nome=produto.nome,
        tipo=mov.tipo, quantidade=mov.quantidade, peso_g=mov.peso_g, criado_em=mov.criado_em,
    )
```

- [ ] **Step 6: Registrar em `main.py`**:
```python
    from .api.operacao import router as operacao_router
    app.include_router(operacao_router)
```

- [ ] **Step 7: Rodar (GREEN)** + suíte completa.

- [ ] **Step 8: Commit**
```bash
git add app/backend/src/inventario/services.py app/backend/src/inventario/schemas.py \
        app/backend/src/inventario/api/operacao.py app/backend/src/inventario/main.py \
        app/backend/tests/test_operacao_api.py
# git commit -m "feat(api): operação por peso (preview + confirmar), registra peso_g"
```

---

## Task 2: Frontend — tela de Operação (beta manual)

**Files:**
- Modify: `app/frontend/src/api.ts`
- Create: `app/frontend/src/pages/Operacao.tsx`
- Modify: `app/frontend/src/App.tsx`

- [ ] **Step 1: api.ts** — tipos e funções:
```ts
export type Preview = {
  status: "ok" | "empty" | "imprecise" | "no_change"
  produto_id: number
  produto_nome: string
  estoque_atual: number
  peso_g: string
  tipo: string | null
  quantidade: number | null
  qtd_fisica: number | null
  qtd_resultante: number | null
}

export async function operacaoPreview(produto_id: number, peso_g: string): Promise<Preview> {
  const r = await fetch(`${BASE}/operacao/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ produto_id, peso_g }),
  })
  if (!r.ok) throw new Error("falha no preview")
  return r.json()
}

export async function operacaoConfirmar(produto_id: number, peso_g: string): Promise<void> {
  const r = await fetch(`${BASE}/operacao/confirmar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ produto_id, peso_g }),
  })
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}))
    throw new Error(corpo.detail ?? "falha ao confirmar")
  }
}
```

- [ ] **Step 2: Página `pages/Operacao.tsx`**
```tsx
import { useEffect, useState } from "react"
import {
  listarProdutos, operacaoConfirmar, operacaoPreview, type Preview, type Produto,
} from "../api"

const STATUS_MSG: Record<string, string> = {
  empty: "Caixa fora da balança (peso abaixo da tara).",
  imprecise: "Leitura imprecisa — confira a caixa.",
  no_change: "Sem mudança no estoque.",
}

export function Operacao() {
  const [produtos, setProdutos] = useState<Produto[]>([])
  const [produtoId, setProdutoId] = useState<number | "">("")
  const [peso, setPeso] = useState("")
  const [preview, setPreview] = useState<Preview | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  useEffect(() => {
    listarProdutos().then(setProdutos).catch(() => {})
  }, [])

  useEffect(() => {
    if (produtoId === "" || peso === "") {
      setPreview(null)
      return
    }
    operacaoPreview(Number(produtoId), peso).then(setPreview).catch(() => setPreview(null))
  }, [produtoId, peso])

  async function confirmar() {
    if (produtoId === "" || peso === "") return
    setMsg(null)
    try {
      await operacaoConfirmar(Number(produtoId), peso)
      setMsg("Movimento confirmado!")
      setPeso("")
      setPreview(null)
      setProdutos(await listarProdutos())
    } catch (e) {
      setMsg((e as Error).message)
    }
  }

  const ok = preview?.status === "ok"

  return (
    <div className="flex-1 p-6 text-slate-200">
      <h2 className="mb-4 text-lg font-bold text-white">Operação (beta manual)</h2>

      <div className="mb-4 flex gap-3">
        <label className="block">
          <span className="mb-1 block text-xs opacity-60">Produto (simula a tag RFID)</span>
          <select
            value={produtoId}
            onChange={(e) => setProdutoId(e.target.value === "" ? "" : Number(e.target.value))}
            className="w-56 rounded border border-slate-600 bg-slate-900 px-2 py-1"
          >
            <option value="">— selecione —</option>
            {produtos.map((p) => (
              <option key={p.id} value={p.id}>{p.nome} ({p.rfid_tag_id})</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs opacity-60">Peso na balança (g)</span>
          <input
            type="number"
            value={peso}
            onChange={(e) => setPeso(e.target.value)}
            className="w-40 rounded border border-slate-600 bg-slate-900 px-2 py-1"
          />
        </label>
      </div>

      <div className="max-w-md rounded-lg border border-slate-700 p-5">
        {!preview && <p className="opacity-50">Selecione um produto e digite o peso.</p>}
        {preview && !ok && (
          <p className="text-amber-300">{STATUS_MSG[preview.status] ?? preview.status}</p>
        )}
        {preview && ok && (
          <div className="flex flex-col items-center gap-2">
            <div className="text-sm opacity-60">{preview.produto_nome}</div>
            <span
              className={`rounded-full px-3 py-1 font-bold ${
                preview.quantidade! > 0
                  ? "bg-emerald-900 text-emerald-300"
                  : "bg-amber-900 text-amber-300"
              }`}
            >
              {preview.tipo} {preview.quantidade! > 0 ? `+${preview.quantidade}` : preview.quantidade}
            </span>
            <div className="opacity-70">
              estoque {preview.estoque_atual} → <b className="text-white">{preview.qtd_resultante}</b>
            </div>
            <button
              onClick={confirmar}
              className="mt-2 rounded bg-emerald-500 px-6 py-2 font-bold text-emerald-950"
            >
              Confirmar
            </button>
          </div>
        )}
        {msg && <p className="mt-3 text-center text-sm text-sky-300">{msg}</p>}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: App.tsx** — trocar o placeholder de Operação:
```tsx
import { Operacao } from "./pages/Operacao"
// ...
{pagina === "Operação" && <Operacao />}
```
(remover o `<div>...em breve...</div>`)

- [ ] **Step 4: Verificar** — selecionar produto, digitar peso, ver o pendente, confirmar, e checar que aparece no Histórico **com o peso**.

- [ ] **Step 5: Commit**
```bash
git add app/frontend/src
# git commit -m "feat(frontend): tela de Operação (beta manual por peso)"
```

---

## Self-Review
- Preview (reconcile sem gravar) + Confirmar (transacional, com peso_g) → Task 1. Tela consumindo → Task 2. ✓
- Reaproveita `reconcile` e o serviço de movimento (generalizado p/ peso_g). ✓
- Quando a ESP32 entrar: substitui o dropdown pela tag lida e o input de peso pelo `PESO:` da serial; preview/confirmar permanecem. ✓
