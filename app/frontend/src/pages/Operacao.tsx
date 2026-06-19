import { Carrinho } from "../components/Carrinho"
import { MovimentoPorPeso } from "../components/MovimentoPorPeso"

export function Operacao() {
  return (
    <div className="flex flex-1">
      <MovimentoPorPeso />
      <Carrinho />
    </div>
  )
}
