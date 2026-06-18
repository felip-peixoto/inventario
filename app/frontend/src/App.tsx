import { useState } from "react"
import { Sidebar, type Pagina } from "./components/Sidebar"
import { Operacao } from "./pages/Operacao"
import { Produtos } from "./pages/Produtos"
import { Historico } from "./pages/Historico"

export default function App() {
  const [pagina, setPagina] = useState<Pagina>("Produtos")
  return (
    <div className="flex min-h-screen bg-slate-950">
      <Sidebar ativa={pagina} onSelect={setPagina} />
      {pagina === "Operação" && <Operacao />}
      {pagina === "Produtos" && <Produtos />}
      {pagina === "Histórico" && <Historico />}
    </div>
  )
}
