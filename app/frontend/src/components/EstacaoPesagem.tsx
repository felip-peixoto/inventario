import { useEffect, useState } from "react"
import { operacaoConfirmar } from "../api"

const WS_URL = "ws://localhost:8000/ws/pesagem"

type EventoTag = { type: "tag"; uid: string; produto_id: number; produto_nome: string }
type EventoProdutoDesconhecido = { type: "produto_desconhecido"; uid: string }
type EventoPeso = { type: "peso"; valor_g: string }
type EventoPreview = {
  type: "preview"
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

type Props = {
  /** chamado quando o peso indica RETIRADA (venda) — não mexe no estoque ainda,
   *  só entra no carrinho; a reserva de fato acontece ao fechar o pedido. */
  onVenda: (produtoId: number, quantidade: number) => void
}

export function EstacaoPesagem({ onVenda }: Props) {
  const [conectado, setConectado] = useState(false)
  const [produtoAtivo, setProdutoAtivo] = useState<{ id: number; nome: string } | null>(null)
  const [tagDesconhecida, setTagDesconhecida] = useState<string | null>(null)
  const [pesoAtual, setPesoAtual] = useState<string | null>(null)
  const [preview, setPreview] = useState<EventoPreview | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [processando, setProcessando] = useState(false)

  useEffect(() => {
    let ws: WebSocket
    let tentativaReconectar: number | null = null

    function conectar() {
      ws = new WebSocket(WS_URL)
      ws.onopen = () => setConectado(true)
      ws.onclose = () => {
        setConectado(false)
        tentativaReconectar = window.setTimeout(conectar, 2000)
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (ev) => {
        const evento = JSON.parse(ev.data)
        if (evento.type === "tag") {
          const e = evento as EventoTag
          setProdutoAtivo({ id: e.produto_id, nome: e.produto_nome })
          setTagDesconhecida(null)
          setPreview(null)
        } else if (evento.type === "produto_desconhecido") {
          const e = evento as EventoProdutoDesconhecido
          setProdutoAtivo(null)
          setTagDesconhecida(e.uid)
          setPreview(null)
        } else if (evento.type === "peso") {
          setPesoAtual((evento as EventoPeso).valor_g)
        } else if (evento.type === "preview") {
          setPreview(evento as EventoPreview)
        }
      }
    }
    conectar()
    return () => {
      if (tentativaReconectar) window.clearTimeout(tentativaReconectar)
      ws?.close()
    }
  }, [])

  async function confirmar() {
    if (!preview || !produtoAtivo || preview.status !== "ok" || !preview.quantidade) return
    setProcessando(true)
    setMsg(null)
    try {
      if (preview.quantidade > 0) {
        // reposição: ajusta o estoque real na hora, sem gerar cobrança
        await operacaoConfirmar(produtoAtivo.id, preview.peso_g)
        setMsg(`Reposição confirmada: +${preview.quantidade} ${produtoAtivo.nome}`)
      } else {
        // venda: não mexe no estoque agora — só entra no carrinho
        onVenda(produtoAtivo.id, Math.abs(preview.quantidade))
        setMsg(`${Math.abs(preview.quantidade)}x ${produtoAtivo.nome} adicionado ao carrinho`)
      }
      setPreview(null)
    } catch (e) {
      setMsg((e as Error).message)
    } finally {
      setProcessando(false)
    }
  }

  const ok = preview?.status === "ok" && !!preview.quantidade
  const éReposição = ok && preview!.quantidade! > 0

  return (
    <div className="w-72 shrink-0 border-r border-slate-700 p-4 text-slate-200">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-bold text-white">Estação de pesagem</h2>
        <span
          title={conectado ? "conectado" : "desconectado"}
          className={`h-2 w-2 rounded-full ${conectado ? "bg-emerald-500" : "bg-red-500"}`}
        />
      </div>

      {!produtoAtivo && !tagDesconhecida && (
        <p className="text-xs opacity-50">Aproxime uma caixa com tag RFID da balança.</p>
      )}
      {tagDesconhecida && (
        <p className="text-xs text-amber-300">
          Tag {tagDesconhecida} não corresponde a nenhum produto cadastrado.
        </p>
      )}
      {produtoAtivo && (
        <div className="mb-3">
          <div className="text-sm font-bold text-white">{produtoAtivo.nome}</div>
          <div className="text-xs opacity-60">peso na balança: {pesoAtual ?? "—"} g</div>
        </div>
      )}

      <div className="rounded-lg border border-slate-700 p-3">
        {!ok && <p className="text-xs opacity-50">Aguardando peso estabilizar…</p>}
        {ok && (
          <div className="flex flex-col items-center gap-2">
            <span
              className={`rounded-full px-3 py-1 text-xs font-bold ${
                éReposição ? "bg-emerald-900 text-emerald-300" : "bg-sky-900 text-sky-300"
              }`}
            >
              {éReposição ? `Reposição +${preview!.quantidade}` : `Retirada ${preview!.quantidade}`}
            </span>
            <div className="text-xs opacity-70">
              estoque {preview!.estoque_atual} → <b className="text-white">{preview!.qtd_resultante}</b>
            </div>
            <button
              onClick={confirmar}
              disabled={processando}
              className="mt-1 rounded bg-emerald-500 px-4 py-1.5 text-sm font-bold text-emerald-950 disabled:opacity-50"
            >
              {éReposição ? "Confirmar reposição" : "Adicionar ao carrinho"}
            </button>
          </div>
        )}
        {preview && !ok && preview.status !== "no_change" && (
          <p className="text-xs text-amber-300">
            {preview.status === "empty" ? "Caixa fora da balança." : "Leitura imprecisa — confira a caixa."}
          </p>
        )}
      </div>

      {msg && <p className="mt-2 text-center text-xs text-sky-300">{msg}</p>}
    </div>
  )
}
