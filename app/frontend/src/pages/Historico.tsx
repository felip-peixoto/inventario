import { useEffect, useState } from "react"
import { listarMovimentacoes, type Movimentacao } from "../api"

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

export function Historico() {
  const [movs, setMovs] = useState<Movimentacao[]>([])
  const [tipo, setTipo] = useState("")

  useEffect(() => {
    listarMovimentacoes(tipo ? { tipo } : {})
      .then(setMovs)
      .catch(() => setMovs([]))
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
            <option key={t} value={t}>
              {t === "" ? "Todos os tipos" : t}
            </option>
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
            <tr>
              <td colSpan={5} className="py-4 opacity-50">
                Nenhuma movimentação.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
