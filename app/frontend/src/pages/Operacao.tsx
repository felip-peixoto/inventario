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
    operacaoPreview(Number(produtoId), peso)
      .then(setPreview)
      .catch(() => setPreview(null))
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
              <option key={p.id} value={p.id}>
                {p.nome} ({p.rfid_tag_id})
              </option>
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
              estoque {preview.estoque_atual} →{" "}
              <b className="text-white">{preview.qtd_resultante}</b>
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
