const itens = [
  { label: "Operação", ativo: false },
  { label: "Produtos", ativo: true },
  { label: "Histórico", ativo: false },
]

export function Sidebar() {
  return (
    <aside className="w-48 shrink-0 border-r border-slate-700 bg-slate-900 p-3 text-slate-300">
      <div className="mb-4 font-bold text-white">≡ Inventário</div>
      <nav className="flex flex-col gap-1">
        {itens.map((i) => (
          <div
            key={i.label}
            className={`rounded-md px-3 py-2 ${
              i.ativo ? "bg-slate-700 text-white" : "opacity-60"
            }`}
          >
            {i.label}
          </div>
        ))}
      </nav>
    </aside>
  )
}
