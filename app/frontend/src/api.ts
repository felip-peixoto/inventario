const BASE = "http://localhost:8000"

export type Produto = {
  id: number
  nome: string
  rfid_tag_id: string
  peso_unitario_g: string
  tara_caixa_g: string
  preco_unitario: string
  estoque_disponivel: number
  estoque_reservado: number
  peso_total_g: string
}

export type NovoProduto = {
  nome: string
  rfid_tag_id: string
  peso_unitario_g: string
  tara_caixa_g: string
  preco_unitario: string
  estoque_disponivel: number
}

export async function listarProdutos(): Promise<Produto[]> {
  const r = await fetch(`${BASE}/produtos`)
  if (!r.ok) throw new Error("falha ao listar produtos")
  return r.json()
}

export async function criarProduto(p: NovoProduto): Promise<Produto> {
  const r = await fetch(`${BASE}/produtos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(p),
  })
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}))
    throw new Error(corpo.detail ?? "falha ao criar produto")
  }
  return r.json()
}
