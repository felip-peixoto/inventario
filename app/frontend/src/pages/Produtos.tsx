import { useEffect, useState } from "react"
import { criarProduto, listarProdutos, type NovoProduto, type Produto } from "../api"

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

export function Produtos() {
  const [produtos, setProdutos] = useState<Produto[]>([])
  const [form, setForm] = useState<NovoProduto>(vazio)
  const [erro, setErro] = useState<string | null>(null)

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
              <th className="py-2">Nome</th>
              <th>Tag</th>
              <th>Peso u.</th>
              <th>Tara</th>
              <th className="text-sky-300">Peso total</th>
              <th>Preço</th>
              <th>Estoque</th>
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
              <tr>
                <td colSpan={7} className="py-4 opacity-50">
                  Nenhum produto ainda.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <form onSubmit={salvar} className="w-64 rounded-lg border border-slate-700 p-4">
        <h3 className="mb-3 font-semibold text-white">Novo produto</h3>
        {campos.map(([campo, rotulo, tipo]) => (
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
