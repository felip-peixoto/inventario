import { useState } from "react"
import { Sidebar, type Pagina } from "./components/Sidebar"
import { Produtos } from "./pages/Produtos"
import { Historico } from "./pages/Historico"

export default function App() {
  const [pagina, setPagina] = useState<Pagina>("Produtos")
  return (
    <div className="flex min-h-screen bg-slate-950">
      <Sidebar ativa={pagina} onSelect={setPagina} />
      {pagina === "Produtos" && <Produtos />}
      {pagina === "Histórico" && <Historico />}
      {pagina === "Operação" && (
        <div className="flex-1 p-6 text-slate-400">
          Operação — em breve (depende da balança).
        </div>
      )}
    </div>
  )
}
