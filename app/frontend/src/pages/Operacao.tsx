import { useRef } from "react"
import { Carrinho, type CarrinhoHandle } from "../components/Carrinho"
import { EstacaoPesagem } from "../components/EstacaoPesagem"

export function Operacao() {
  const carrinhoRef = useRef<CarrinhoHandle>(null)

  function onVenda(produtoId: number, quantidade: number) {
    carrinhoRef.current?.adicionarLinha(produtoId, quantidade)
  }

  return (
    <div className="flex flex-1">
      <EstacaoPesagem onVenda={onVenda} />
      <Carrinho ref={carrinhoRef} />
    </div>
  )
}
