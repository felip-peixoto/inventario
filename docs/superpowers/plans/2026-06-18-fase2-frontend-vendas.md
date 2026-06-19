# Fase 2 — Frontend de Vendas (carrinho + QR na Operação) — Implementation Plan

> **For agentic workers:** Steps usam checkbox. **Commits são do usuário.** **Tudo em Docker.** Verificação do front: o Vite transpila sem erro (`curl -s -o /dev/null -w "%{http_code}" localhost:5173/src/<arquivo>.tsx` → 200) + checagem visual em http://localhost:5173.

**Goal:** A tela de Operação ganha o **carrinho** (meio) e o **QR de pagamento** (direita, após fechar), consumindo os endpoints de venda; o Histórico passa a mostrar os tipos `RESERVA`/`CONFIRMACAO`/`REVERSAO`.

**Architecture:** A Operação vira três zonas: o movimento por peso atual (extraído para `MovimentoPorPeso`) à esquerda, e o `Carrinho` (lista + pagamento com QR e polling) à direita. `api.ts` ganha as funções de venda.

**Tech Stack:** React + TypeScript + Tailwind (Vite, em Docker).

## Global Constraints
- Backend já no ar via compose (`backend` na 8000). `BASE = http://localhost:8000`.
- Comando base: `DC="docker compose --project-directory /home/joao/Repos/Oficinas2/inventario -f /home/joao/Repos/Oficinas2/inventario/docker-compose.yml"`.

---

## File Structure
```
app/frontend/src/
├── api.ts                              # + tipos/funções de venda
├── pages/Operacao.tsx                  # vira composição (MovimentoPorPeso + Carrinho)
├── pages/Historico.tsx                 # + tipos novos no filtro e nas cores
└── components/
    ├── MovimentoPorPeso.tsx            # NOVO — extraído do Operacao atual
    └── Carrinho.tsx                    # NOVO — carrinho + QR + polling
```

---

## Task 1: `api.ts` (funções de venda) + tipos novos no Histórico

**Files:**
- Modify: `app/frontend/src/api.ts`
- Modify: `app/frontend/src/pages/Historico.tsx`

- [ ] **Step 1: Adicionar ao fim de `api.ts`**
```ts
export type VendaItem = {
  produto_id: number
  produto_nome: string
  quantidade: number
  preco_unitario: string
  subtotal: string
}

export type Venda = {
  id: number
  status: string
  valor_total: string
  pix_copia_e_cola: string | null
  expira_em: string | null
  itens: VendaItem[]
  qr_code_base64?: string | null
}

export async function criarVenda(
  itens: { produto_id: number; quantidade: number }[],
): Promise<Venda> {
  const r = await fetch(`${BASE}/vendas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ itens }),
  })
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}))
    throw new Error(corpo.detail ?? "falha ao criar venda")
  }
  return r.json()
}

export async function getVenda(id: number): Promise<Venda> {
  const r = await fetch(`${BASE}/vendas/${id}`)
  if (!r.ok) throw new Error("falha ao consultar venda")
  return r.json()
}

export async function pagarVenda(id: number): Promise<Venda> {
  const r = await fetch(`${BASE}/vendas/${id}/pagamento`, { method: "POST" })
  if (!r.ok) throw new Error("falha ao registrar pagamento")
  return r.json()
}

export async function cancelarVenda(id: number): Promise<Venda> {
  const r = await fetch(`${BASE}/vendas/${id}/cancelar`, { method: "POST" })
  if (!r.ok) throw new Error("falha ao cancelar")
  return r.json()
}
```

- [ ] **Step 2: Atualizar `pages/Historico.tsx`** — incluir os tipos novos no filtro e cobrir as cores. Trocar a constante `TIPOS` e a função `badge`:
```tsx
const TIPOS = ["", "REPOSICAO", "AJUSTE", "RESERVA", "CONFIRMACAO", "REVERSAO"]

const CORES: Record<string, string> = {
  REPOSICAO: "bg-emerald-900 text-emerald-300",
  CONFIRMACAO: "bg-emerald-900 text-emerald-300",
  RESERVA: "bg-sky-900 text-sky-300",
  AJUSTE: "bg-amber-900 text-amber-300",
  REVERSAO: "bg-amber-900 text-amber-300",
}

function badge(tipo: string) {
  const cor = CORES[tipo] ?? "bg-slate-700 text-slate-200"
  return <span className={`rounded-full px-2 py-0.5 text-xs ${cor}`}>{tipo}</span>
}
```

- [ ] **Step 3: Verificar** — `curl -s -o /dev/null -w "%{http_code}\n" localhost:5173/src/api.ts localhost:5173/src/pages/Historico.tsx` → 200 nos dois; sem erro no `$DC logs frontend`.

- [ ] **Step 4: Commit**
```bash
git add app/frontend/src/api.ts app/frontend/src/pages/Historico.tsx
# git commit -m "feat(frontend): funções de venda na api + tipos de venda no Histórico"
```

---

## Task 2: Extrair `MovimentoPorPeso` da Operação

A Operação atual vira um componente reutilizável (sem mudar comportamento), pra liberar espaço pro carrinho.

**Files:**
- Create: `app/frontend/src/components/MovimentoPorPeso.tsx`
- Modify: `app/frontend/src/pages/Operacao.tsx`

- [ ] **Step 1: Criar `components/MovimentoPorPeso.tsx`** com o conteúdo atual da Operação (mesma lógica), como coluna:
```tsx
import { useEffect, useState } from "react"
import {
  listarProdutos,
  operacaoConfirmar,
  operacaoPreview,
  type Preview,
  type Produto,
} from "../api"

const STATUS_MSG: Record<string, string> = {
  empty: "Caixa fora da balança (peso abaixo da tara).",
  imprecise: "Leitura imprecisa — confira a caixa.",
  no_change: "Sem mudança no estoque.",
}

export function MovimentoPorPeso() {
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
    } catch (e) {
      setMsg((e as Error).message)
    }
  }

  const ok = preview?.status === "ok"

  return (
    <div className="w-64 shrink-0 border-r border-slate-700 p-4">
      <h2 className="mb-3 text-base font-bold text-white">Movimento por peso</h2>
      <label className="mb-2 block">
        <span className="mb-1 block text-xs opacity-60">Produto (tag)</span>
        <select
          value={produtoId}
          onChange={(e) => setProdutoId(e.target.value === "" ? "" : Number(e.target.value))}
          className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1"
        >
          <option value="">— selecione —</option>
          {produtos.map((p) => (
            <option key={p.id} value={p.id}>{p.nome}</option>
          ))}
        </select>
      </label>
      <label className="mb-3 block">
        <span className="mb-1 block text-xs opacity-60">Peso (g)</span>
        <input
          type="number"
          value={peso}
          onChange={(e) => setPeso(e.target.value)}
          className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1"
        />
      </label>
      <div className="rounded-lg border border-slate-700 p-3">
        {!preview && <p className="text-xs opacity-50">Selecione produto e peso.</p>}
        {preview && !ok && (
          <p className="text-xs text-amber-300">{STATUS_MSG[preview.status] ?? preview.status}</p>
        )}
        {preview && ok && (
          <div className="flex flex-col items-center gap-2">
            <span
              className={`rounded-full px-3 py-1 text-xs font-bold ${
                preview.quantidade! > 0
                  ? "bg-emerald-900 text-emerald-300"
                  : "bg-amber-900 text-amber-300"
              }`}
            >
              {preview.tipo} {preview.quantidade! > 0 ? `+${preview.quantidade}` : preview.quantidade}
            </span>
            <div className="text-xs opacity-70">
              estoque {preview.estoque_atual} → <b className="text-white">{preview.qtd_resultante}</b>
            </div>
            <button
              onClick={confirmar}
              className="mt-1 rounded bg-emerald-500 px-4 py-1.5 text-sm font-bold text-emerald-950"
            >
              Confirmar
            </button>
          </div>
        )}
        {msg && <p className="mt-2 text-center text-xs text-sky-300">{msg}</p>}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Reduzir `pages/Operacao.tsx`** a uma composição (Carrinho entra na Task 3):
```tsx
import { MovimentoPorPeso } from "../components/MovimentoPorPeso"

export function Operacao() {
  return (
    <div className="flex flex-1">
      <MovimentoPorPeso />
      <div className="flex-1 p-4 text-slate-400">Carrinho — em construção…</div>
    </div>
  )
}
```

- [ ] **Step 3: Verificar** — `curl` 200 em `src/pages/Operacao.tsx` e `src/components/MovimentoPorPeso.tsx`; abrir a aba Operação e confirmar que o movimento por peso ainda funciona à esquerda.

- [ ] **Step 4: Commit**
```bash
git add app/frontend/src/components/MovimentoPorPeso.tsx app/frontend/src/pages/Operacao.tsx
# git commit -m "refactor(frontend): extrai MovimentoPorPeso da Operação"
```

---

## Task 3: Componente `Carrinho` (lista + QR + polling)

**Files:**
- Create: `app/frontend/src/components/Carrinho.tsx`
- Modify: `app/frontend/src/pages/Operacao.tsx`

- [ ] **Step 1: Criar `components/Carrinho.tsx`**
```tsx
import { useEffect, useRef, useState } from "react"
import {
  cancelarVenda,
  criarVenda,
  getVenda,
  listarProdutos,
  pagarVenda,
  type Produto,
  type Venda,
} from "../api"

type Linha = { produto_id: number; nome: string; preco: number; quantidade: number }

const STATUS_FINAL = ["CONFIRMADO", "CANCELADO", "EXPIRADO"]

export function Carrinho() {
  const [produtos, setProdutos] = useState<Produto[]>([])
  const [sel, setSel] = useState<number | "">("")
  const [qtd, setQtd] = useState("1")
  const [linhas, setLinhas] = useState<Linha[]>([])
  const [venda, setVenda] = useState<Venda | null>(null)
  const [qrBase64, setQrBase64] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const timer = useRef<number | null>(null)

  async function carregarProdutos() {
    setProdutos(await listarProdutos())
  }
  useEffect(() => {
    carregarProdutos().catch(() => {})
  }, [])

  // polling enquanto a venda estiver pendente
  useEffect(() => {
    if (!venda || venda.status !== "PENDENTE") return
    timer.current = window.setInterval(async () => {
      try {
        const atual = await getVenda(venda.id)
        setVenda(atual)
        if (STATUS_FINAL.includes(atual.status)) {
          if (timer.current) window.clearInterval(timer.current)
          carregarProdutos().catch(() => {})
        }
      } catch {
        /* ignora */
      }
    }, 3000)
    return () => {
      if (timer.current) window.clearInterval(timer.current)
    }
  }, [venda])

  function adicionar() {
    if (sel === "") return
    const p = produtos.find((x) => x.id === sel)!
    const n = Number(qtd)
    if (n <= 0) return
    setLinhas((ls) => {
      const existe = ls.find((l) => l.produto_id === p.id)
      if (existe) {
        return ls.map((l) =>
          l.produto_id === p.id ? { ...l, quantidade: l.quantidade + n } : l,
        )
      }
      return [...ls, { produto_id: p.id, nome: p.nome, preco: Number(p.preco_unitario), quantidade: n }]
    })
  }

  function remover(id: number) {
    setLinhas((ls) => ls.filter((l) => l.produto_id !== id))
  }

  const total = linhas.reduce((s, l) => s + l.preco * l.quantidade, 0)

  async function fechar() {
    setErro(null)
    try {
      const v = await criarVenda(
        linhas.map((l) => ({ produto_id: l.produto_id, quantidade: l.quantidade })),
      )
      setVenda(v)
      setQrBase64(v.qr_code_base64 ?? null)
      await carregarProdutos()
    } catch (e) {
      setErro((e as Error).message)
    }
  }

  async function pagar() {
    if (!venda) return
    setVenda(await pagarVenda(venda.id))
    await carregarProdutos()
  }
  async function cancelar() {
    if (!venda) return
    setVenda(await cancelarVenda(venda.id))
    await carregarProdutos()
  }
  function novaVenda() {
    setVenda(null)
    setQrBase64(null)
    setLinhas([])
  }

  const pendente = venda?.status === "PENDENTE"

  return (
    <div className="flex flex-1 text-sm text-slate-200">
      {/* MEIO: carrinho */}
      <div className="flex-1 border-r border-slate-700 p-4">
        <h2 className="mb-3 text-base font-bold text-white">
          Carrinho {venda && <span className="text-xs opacity-50">(pedido {venda.status.toLowerCase()})</span>}
        </h2>
        {!venda && (
          <div className="mb-3 flex gap-2">
            <select
              value={sel}
              onChange={(e) => setSel(e.target.value === "" ? "" : Number(e.target.value))}
              className="flex-1 rounded border border-slate-600 bg-slate-900 px-2 py-1"
            >
              <option value="">Selecionar produto</option>
              {produtos.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nome} (R$ {p.preco_unitario}) · {p.estoque_disponivel} disp.
                </option>
              ))}
            </select>
            <input
              type="number"
              value={qtd}
              onChange={(e) => setQtd(e.target.value)}
              className="w-14 rounded border border-slate-600 bg-slate-900 px-1 text-center"
            />
            <button onClick={adicionar} className="rounded bg-blue-600 px-3 font-bold text-white">+</button>
          </div>
        )}

        <div className="grid grid-cols-[1.5fr_.4fr_.8fr_.3fr] gap-2 border-b border-slate-700 pb-1 text-xs uppercase opacity-60">
          <span>Item</span><span>Qtd</span><span>Subtotal</span><span></span>
        </div>
        {linhas.map((l) => (
          <div key={l.produto_id} className="grid grid-cols-[1.5fr_.4fr_.8fr_.3fr] gap-2 border-b border-slate-800 py-1.5">
            <span className="text-white">{l.nome}</span>
            <span>{l.quantidade}</span>
            <span>R$ {(l.preco * l.quantidade).toFixed(2)}</span>
            {!venda ? (
              <button onClick={() => remover(l.produto_id)} className="opacity-50 hover:opacity-100">✕</button>
            ) : (
              <span />
            )}
          </div>
        ))}
        {linhas.length === 0 && <p className="py-3 opacity-50">Carrinho vazio.</p>}

        <div className="mt-4 text-white">Total: <b>R$ {total.toFixed(2)}</b></div>
        {erro && <p className="mt-2 text-xs text-red-400">{erro}</p>}
        {!venda && linhas.length > 0 && (
          <button onClick={fechar} className="mt-3 rounded bg-emerald-500 px-4 py-2 font-bold text-emerald-950">
            Fechar pedido · gerar Pix
          </button>
        )}
      </div>

      {/* DIREITA: pagamento */}
      <div className="w-64 shrink-0 p-4">
        {!venda && <p className="mt-10 text-center opacity-40">Feche o pedido para gerar o Pix.</p>}
        {venda && (
          <div className="flex flex-col items-center gap-2">
            <div className="font-bold text-white">Pagamento — R$ {Number(venda.valor_total).toFixed(2)}</div>
            {pendente && qrBase64 && (
              <img
                src={`data:image/png;base64,${qrBase64}`}
                alt="QR Pix"
                className="h-36 w-36 rounded border-4 border-white"
              />
            )}
            {pendente && venda.pix_copia_e_cola && (
              <div className="max-w-full overflow-hidden text-ellipsis whitespace-nowrap rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-[9px]">
                {venda.pix_copia_e_cola}
              </div>
            )}
            {pendente && (
              <>
                <span className="rounded-full bg-amber-900 px-2 py-0.5 text-xs text-amber-300">● aguardando pagamento</span>
                <div className="mt-1 flex gap-2">
                  <button onClick={pagar} className="rounded bg-emerald-500 px-4 py-1.5 font-bold text-emerald-950">Pagamento</button>
                  <button onClick={cancelar} className="rounded border border-slate-600 px-3 py-1.5">Cancelar</button>
                </div>
              </>
            )}
            {venda.status === "CONFIRMADO" && <p className="text-emerald-400">Pago ✅</p>}
            {(venda.status === "EXPIRADO" || venda.status === "CANCELADO") && (
              <p className="text-amber-300">{venda.status === "EXPIRADO" ? "Expirado" : "Cancelado"} — itens devolvidos ↩️</p>
            )}
            {STATUS_FINAL.includes(venda.status) && (
              <button onClick={novaVenda} className="mt-2 rounded bg-blue-600 px-4 py-1.5 font-bold text-white">Nova venda</button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Compor na `pages/Operacao.tsx`**
```tsx
import { Carrinho } from "../components/Carrinho"
import { MovimentoPorPeso } from "../components/MovimentoPorPeso"

export function Operacao() {
  return (
    <div className="flex flex-1">
      <MovimentoPorPeso />
      <Carrinho />
    </div>
  )
}
```

- [ ] **Step 3: Verificar de ponta a ponta**
```bash
$DC up -d 2>&1 | tail -1
# transpila sem erro:
for f in pages/Operacao components/Carrinho components/MovimentoPorPeso; do
  curl -s -o /dev/null -w "$f.tsx -> %{http_code}\n" "localhost:5173/src/$f.tsx"; done
```
Abrir http://localhost:5173 → Operação: montar carrinho, **Fechar pedido**, ver o QR (com `MERCADOPAGO_ACCESS_TOKEN` de teste no `.env`; sem token real, o backend mockado não roda — ver nota), clicar **Pagamento** → "Pago ✅" e o estoque baixar; testar **Cancelar** devolvendo. Conferir no Histórico as movimentações RESERVA/CONFIRMACAO/REVERSAO.

> Nota: o e2e real precisa do token de teste no `.env`. Sem ele, o `POST /vendas` falha ao chamar o Mercado Pago. Se o token ainda não estiver no `.env`, validar o fluxo de UI assim que ele for plugado (parte final da Fase 2).

- [ ] **Step 4: Commit**
```bash
git add app/frontend/src/components/Carrinho.tsx app/frontend/src/pages/Operacao.tsx
# git commit -m "feat(frontend): carrinho + QR de pagamento na Operação"
```

---

## Self-Review
- Carrinho (meio) + QR (direita) na Operação, esquerda inalterada → Tasks 2,3 ✓
- Polling enquanto PENDENTE, botões Pagamento/Cancelar, Nova venda → Task 3 ✓
- Tipos novos no Histórico → Task 1 ✓
- Tipos: `Venda`/`VendaItem` (api) batem com `VendaRead`/`VendaItemRead` do backend; `qr_code_base64` só vem no POST (criarVenda) e é guardado em estado. ✓
- Sem placeholders; código completo.
