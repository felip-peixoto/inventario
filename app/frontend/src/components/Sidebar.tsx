export type Pagina = "Operação" | "Produtos" | "Histórico"

const itens: Pagina[] = ["Operação", "Produtos", "Histórico"]

export function Sidebar({ ativa, onSelect }: { ativa: Pagina; onSelect: (p: Pagina) => void }) {
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
