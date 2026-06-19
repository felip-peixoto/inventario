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
