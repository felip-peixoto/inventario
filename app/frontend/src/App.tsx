import { Sidebar } from "./components/Sidebar"
import { Produtos } from "./pages/Produtos"

export default function App() {
  return (
    <div className="flex min-h-screen bg-slate-950">
      <Sidebar />
      <Produtos />
    </div>
  )
}
