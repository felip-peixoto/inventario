import { useEffect, useState } from "react"
import {
  atualizarProduto,
  criarProduto,
  listarProdutos,
  zerarBalanca,
  type NovoProduto,
  type Produto,
  type ProdutoEdicao,
} from "../api"

const WS_URL = "ws://localhost:8000/ws/pesagem"

const vazio: NovoProduto = {
  nome: "",
  rfid_tag_id: "",
  peso_unitario_g: "",
  tara_caixa_g: "0",
  preco_unitario: "",
  estoque_disponivel: 0,
}

const campos = [
  ["nome", "Nome", "text"],
  ["rfid_tag_id", "Tag RFID", "text"],
  ["peso_unitario_g", "Peso unitário (g)", "text"],
  ["tara_caixa_g", "Tara (g)", "text"],
  ["preco_unitario", "Preço (R$)", "text"],
  ["estoque_disponivel", "Estoque inicial", "number"],
] as const

// campos permitidos no formulário de edição — rfid_tag_id fica de fora
// de propósito, pois a tag nunca pode ser alterada por aqui
const camposEdicao = [
  ["nome", "Nome", "text"],
  ["peso_unitario_g", "Peso unitário (g)", "text"],
  ["tara_caixa_g", "Tara (g)", "text"],
  ["preco_unitario", "Preço (R$)", "text"],
  ["estoque_disponivel", "Estoque disponível", "number"],
] as const

const inputClasses =
  "w-full rounded-lg border border-slate-600 bg-slate-950 px-2.5 py-1.5 text-slate-100 " +
  "outline-none transition-colors focus:border-emerald-500/60 focus:ring-2 focus:ring-emerald-500/20"

const inputDisabledClasses =
  "w-full rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-slate-400 " +
  "outline-none cursor-not-allowed"

export function Produtos() {
  const [produtos, setProdutos] = useState<Produto[]>([])
  const [erro, setErro] = useState<string | null>(null)
  const [modalAberto, setModalAberto] = useState(false)
  const [produtoEditando, setProdutoEditando] = useState<Produto | null>(null)
  const [modoAdmin, setModoAdmin] = useState(false)

  async function carregar() {
    try {
      setProdutos(await listarProdutos())
    } catch (e) {
      setErro((e as Error).message)
    }
  }

  useEffect(() => {
    carregar()
  }, [])

  return (
    <div className="flex-1 p-4 text-sm text-slate-200">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <h2 className="text-lg font-bold text-white">Produtos</h2>
          {modoAdmin && (
            <span className="rounded-full border border-amber-700/60 bg-amber-950/40 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-amber-300">
              Modo Admin ativo
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setModoAdmin((v) => !v)}
            title="Habilita a edição de produtos (dados e estoque)"
            className={`rounded-lg border px-3.5 py-2 text-sm font-bold transition-colors ${modoAdmin
              ? "border-amber-500/60 bg-amber-500/15 text-amber-300 hover:bg-amber-500/25"
              : "border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700"
              }`}
          >
            Modo Admin
          </button>
          <button
            onClick={() => setModalAberto(true)}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3.5 py-2 text-sm font-bold text-emerald-950 transition-colors hover:bg-emerald-400"
          >
            <span className="text-base leading-none">+</span> Novo produto
          </button>
        </div>
      </div>

      {erro && <p className="mb-3 text-xs text-red-400">{erro}</p>}

      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-slate-700 text-left text-xs uppercase opacity-60">
            <th className="py-2">Nome</th>
            <th>Tag</th>
            <th>Peso u.</th>
            <th>Tara</th>
            <th className="text-sky-300">Peso total</th>
            <th>Preço</th>
            <th>Estoque</th>
            {modoAdmin && <th>Editar</th>}
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
              {modoAdmin && (
                <td>
                  <button
                    onClick={() => setProdutoEditando(p)}
                    className="rounded bg-slate-700 px-2 py-1 text-xs font-semibold text-white transition-colors hover:bg-slate-600"
                  >
                    Editar
                  </button>
                </td>
              )}
            </tr>
          ))}
          {produtos.length === 0 && (
            <tr>
              <td colSpan={modoAdmin ? 8 : 7} className="py-4 opacity-50">
                Nenhum produto ainda.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {modalAberto && (
        <ModalNovoProduto
          onClose={() => setModalAberto(false)}
          onCriado={() => {
            setModalAberto(false)
            carregar()
          }}
        />
      )}

      {produtoEditando && (
        <ModalEditarProduto
          produto={produtoEditando}
          onClose={() => setProdutoEditando(null)}
          onSalvo={() => {
            setProdutoEditando(null)
            carregar()
          }}
        />
      )}
    </div>
  )
}

function ModalNovoProduto({ onClose, onCriado }: { onClose: () => void; onCriado: () => void }) {
  const [visivel, setVisivel] = useState(false)
  const [form, setForm] = useState<NovoProduto>(vazio)
  const [erro, setErro] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)

  // estado "ao vivo" da balança, usado só enquanto o modal está aberto
  const [conectado, setConectado] = useState(false)
  const [pesoAoVivo, setPesoAoVivo] = useState<string | null>(null)
  const [zerando, setZerando] = useState(false)
  const [tagEmUso, setTagEmUso] = useState<{ uid: string; produtoNome: string } | null>(null)

  useEffect(() => {
    const raf = requestAnimationFrame(() => setVisivel(true))
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener("keydown", onKey)
    }
  }, [onClose])

  // conecta na balança só enquanto o cadastro está aberto na tela
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
        if (evento.type === "peso") {
          setPesoAoVivo(evento.valor_g)
        } else if (evento.type === "produto_desconhecido") {
          // tag nova na balança: já preenche o campo pro usuário não digitar
          setTagEmUso(null)
          setForm((f) => ({ ...f, rfid_tag_id: evento.uid }))
        } else if (evento.type === "tag") {
          // tag já pertence a um produto existente: não preenche (evitaria
          // duplicidade), só avisa o usuário pra trocar de caixa/tag
          setTagEmUso({ uid: evento.uid, produtoNome: evento.produto_nome })
        }
      }
    }
    conectar()
    return () => {
      if (tentativaReconectar) window.clearTimeout(tentativaReconectar)
      ws?.close()
    }
  }, [])

  async function salvar(e: React.FormEvent) {
    e.preventDefault()
    setErro(null)
    setSalvando(true)
    try {
      await criarProduto({ ...form, estoque_disponivel: Number(form.estoque_disponivel) })
      onCriado()
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      setSalvando(false)
    }
  }

  async function handleZerarBalanca() {
    setErro(null)
    setZerando(true)
    try {
      await zerarBalanca()
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setZerando(false)
    }
  }

  function capturarTara() {
    if (pesoAoVivo === null) return
    setForm((f) => ({ ...f, tara_caixa_g: pesoAoVivo }))
  }

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm transition-opacity duration-200 ${visivel ? "opacity-100" : "opacity-0"
        }`}
      onClick={onClose}
    >
      <form
        onSubmit={salvar}
        onClick={(e) => e.stopPropagation()}
        className={`flex max-h-[90vh] w-full max-w-md flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-900 shadow-2xl shadow-black/50 transition-all duration-200 ${visivel ? "translate-y-0 scale-100 opacity-100" : "translate-y-3 scale-95 opacity-0"
          }`}
      >
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div>
            <h3 className="text-base font-bold text-white">Novo produto</h3>
            <p className="text-xs opacity-50">Cadastre um item no inventário</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="rounded-md p-1 text-lg leading-none text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div className="mb-4 flex items-center justify-between rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2">
            <div className="flex items-center gap-2">
              <span
                title={conectado ? "balança conectada" : "balança desconectada"}
                className={`h-2 w-2 rounded-full ${conectado ? "bg-emerald-500" : "bg-red-500"}`}
              />
              <span className="text-xs opacity-70">
                peso ao vivo: <b className="text-white">{pesoAoVivo ?? "—"} g</b>
              </span>
            </div>
            <button
              type="button"
              onClick={handleZerarBalanca}
              disabled={zerando || !conectado}
              className="rounded-md bg-slate-700 px-2.5 py-1 text-xs font-semibold text-white transition-colors hover:bg-slate-600 disabled:opacity-50"
            >
              {zerando ? "Zerando…" : "Zerar balança"}
            </button>
          </div>

          {tagEmUso && (
            <p className="mb-4 rounded-lg border border-amber-800/60 bg-amber-950/40 px-3 py-2 text-xs text-amber-300">
              Essa tag já pertence a <b>{tagEmUso.produtoNome}</b>. Use outra caixa/tag para este
              novo produto.
            </p>
          )}

          <div className="grid grid-cols-2 gap-x-3">
            {campos.map(([campo, rotulo, tipo]) => (
              <label
                key={campo}
                className={`mb-3 block ${campo === "nome" ? "col-span-2" : ""}`}
              >
                <span className="mb-1 block text-xs opacity-60">{rotulo}</span>
                {campo === "tara_caixa_g" ? (
                  <div className="flex gap-1">
                    <input
                      type={tipo}
                      className={inputClasses}
                      value={form.tara_caixa_g}
                      onChange={(e) => setForm({ ...form, tara_caixa_g: e.target.value })}
                    />
                    <button
                      type="button"
                      onClick={capturarTara}
                      disabled={pesoAoVivo === null}
                      className="shrink-0 rounded-lg bg-sky-600 px-2.5 text-xs font-semibold text-white transition-colors hover:bg-sky-500 disabled:opacity-50"
                    >
                      Capturar
                    </button>
                  </div>
                ) : (
                  <input
                    type={tipo}
                    className={inputClasses}
                    value={(form as Record<string, string | number>)[campo]}
                    onChange={(e) => setForm({ ...form, [campo]: e.target.value })}
                    required={campo !== "tara_caixa_g"}
                  />
                )}
              </label>
            ))}
          </div>

          {erro && <p className="text-xs text-red-400">{erro}</p>}
        </div>

        <div className="flex justify-end gap-2 border-t border-slate-800 px-5 py-3.5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-300 transition-colors hover:bg-slate-800"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={salvando}
            className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-bold text-emerald-950 transition-colors hover:bg-emerald-400 disabled:opacity-50"
          >
            {salvando ? "Salvando…" : "Salvar produto"}
          </button>
        </div>
      </form>
    </div>
  )
}

function ModalEditarProduto({
  produto,
  onClose,
  onSalvo,
}: {
  produto: Produto
  onClose: () => void
  onSalvo: () => void
}) {
  const [visivel, setVisivel] = useState(false)
  const [form, setForm] = useState<ProdutoEdicao>({
    nome: produto.nome,
    peso_unitario_g: produto.peso_unitario_g,
    tara_caixa_g: produto.tara_caixa_g,
    preco_unitario: produto.preco_unitario,
    estoque_disponivel: produto.estoque_disponivel,
  })
  const [erro, setErro] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    const raf = requestAnimationFrame(() => setVisivel(true))
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener("keydown", onKey)
    }
  }, [onClose])

  async function salvar(e: React.FormEvent) {
    e.preventDefault()
    setErro(null)
    setSalvando(true)
    try {
      await atualizarProduto(produto.id, {
        ...form,
        estoque_disponivel: Number(form.estoque_disponivel),
      })
      onSalvo()
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm transition-opacity duration-200 ${visivel ? "opacity-100" : "opacity-0"
        }`}
      onClick={onClose}
    >
      <form
        onSubmit={salvar}
        onClick={(e) => e.stopPropagation()}
        className={`flex max-h-[90vh] w-full max-w-md flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-900 shadow-2xl shadow-black/50 transition-all duration-200 ${visivel ? "translate-y-0 scale-100 opacity-100" : "translate-y-3 scale-95 opacity-0"
          }`}
      >
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div>
            <h3 className="text-base font-bold text-white">Editar produto</h3>
            <p className="text-xs opacity-50">Atualize os dados de "{produto.nome}"</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="rounded-md p-1 text-lg leading-none text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {/* Tag RFID é somente leitura aqui: nunca pode ser alterada na edição */}
          <label className="mb-3 block">
            <span className="mb-1 block text-xs opacity-60">Tag RFID (não editável)</span>
            <input
              type="text"
              className={inputDisabledClasses}
              value={produto.rfid_tag_id}
              disabled
              readOnly
            />
          </label>

          <div className="grid grid-cols-2 gap-x-3">
            {camposEdicao.map(([campo, rotulo, tipo]) => (
              <label
                key={campo}
                className={`mb-3 block ${campo === "nome" ? "col-span-2" : ""}`}
              >
                <span className="mb-1 block text-xs opacity-60">{rotulo}</span>
                <input
                  type={tipo}
                  className={inputClasses}
                  value={(form as Record<string, string | number>)[campo]}
                  onChange={(e) => setForm({ ...form, [campo]: e.target.value })}
                  required
                />
              </label>
            ))}
          </div>

          <p className="text-[11px] leading-snug opacity-50">
            Alterar o estoque disponível aqui atualiza o valor diretamente, sem passar pelo
            fluxo de ajuste com balança/movimentação. Use com cuidado.
          </p>

          {erro && <p className="text-xs text-red-400">{erro}</p>}
        </div>

        <div className="flex justify-end gap-2 border-t border-slate-800 px-5 py-3.5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-300 transition-colors hover:bg-slate-800"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={salvando}
            className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-bold text-emerald-950 transition-colors hover:bg-emerald-400 disabled:opacity-50"
          >
            {salvando ? "Salvando…" : "Salvar alterações"}
          </button>
        </div>
      </form>
    </div>
  )
}