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
          Carrinho{" "}
          {venda && <span className="text-xs opacity-50">(pedido {venda.status.toLowerCase()})</span>}
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
            <button onClick={adicionar} className="rounded bg-blue-600 px-3 font-bold text-white">
              +
            </button>
          </div>
        )}

        <div className="grid grid-cols-[1.5fr_.4fr_.8fr_.3fr] gap-2 border-b border-slate-700 pb-1 text-xs uppercase opacity-60">
          <span>Item</span>
          <span>Qtd</span>
          <span>Subtotal</span>
          <span></span>
        </div>
        {linhas.map((l) => (
          <div
            key={l.produto_id}
            className="grid grid-cols-[1.5fr_.4fr_.8fr_.3fr] gap-2 border-b border-slate-800 py-1.5"
          >
            <span className="text-white">{l.nome}</span>
            <span>{l.quantidade}</span>
            <span>R$ {(l.preco * l.quantidade).toFixed(2)}</span>
            {!venda ? (
              <button onClick={() => remover(l.produto_id)} className="opacity-50 hover:opacity-100">
                ✕
              </button>
            ) : (
              <span />
            )}
          </div>
        ))}
        {linhas.length === 0 && <p className="py-3 opacity-50">Carrinho vazio.</p>}

        <div className="mt-4 text-white">
          Total: <b>R$ {total.toFixed(2)}</b>
        </div>
        {erro && <p className="mt-2 text-xs text-red-400">{erro}</p>}
        {!venda && linhas.length > 0 && (
          <button
            onClick={fechar}
            className="mt-3 rounded bg-emerald-500 px-4 py-2 font-bold text-emerald-950"
          >
            Fechar pedido · gerar Pix
          </button>
        )}
      </div>

      {/* DIREITA: pagamento */}
      <div className="w-64 shrink-0 p-4">
        {!venda && <p className="mt-10 text-center opacity-40">Feche o pedido para gerar o Pix.</p>}
        {venda && (
          <div className="flex flex-col items-center gap-2">
            <div className="font-bold text-white">
              Pagamento — R$ {Number(venda.valor_total).toFixed(2)}
            </div>
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
                <span className="rounded-full bg-amber-900 px-2 py-0.5 text-xs text-amber-300">
                  ● aguardando pagamento
                </span>
                <div className="mt-1 flex gap-2">
                  <button
                    onClick={pagar}
                    className="rounded bg-emerald-500 px-4 py-1.5 font-bold text-emerald-950"
                  >
                    Pagamento
                  </button>
                  <button onClick={cancelar} className="rounded border border-slate-600 px-3 py-1.5">
                    Cancelar
                  </button>
                </div>
              </>
            )}
            {venda.status === "CONFIRMADO" && <p className="text-emerald-400">Pago ✅</p>}
            {(venda.status === "EXPIRADO" || venda.status === "CANCELADO") && (
              <p className="text-amber-300">
                {venda.status === "EXPIRADO" ? "Expirado" : "Cancelado"} — itens devolvidos ↩️
              </p>
            )}
            {STATUS_FINAL.includes(venda.status) && (
              <button
                onClick={novaVenda}
                className="mt-2 rounded bg-blue-600 px-4 py-1.5 font-bold text-white"
              >
                Nova venda
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
