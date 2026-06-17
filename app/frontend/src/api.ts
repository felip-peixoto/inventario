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

export type Movimentacao = {
  id: number
  produto_id: number
  produto_nome: string
  tipo: string
  quantidade: number
  peso_g: string | null
  criado_em: string
}

export async function listarMovimentacoes(
  filtros: { produto_id?: number; tipo?: string } = {},
): Promise<Movimentacao[]> {
  const qs = new URLSearchParams()
  if (filtros.produto_id) qs.set("produto_id", String(filtros.produto_id))
  if (filtros.tipo) qs.set("tipo", filtros.tipo)
  const r = await fetch(`${BASE}/movimentacoes?${qs.toString()}`)
  if (!r.ok) throw new Error("falha ao listar movimentações")
  return r.json()
}

export async function ajustarEstoque(produtoId: number, nova_quantidade: number): Promise<void> {
  const r = await fetch(`${BASE}/produtos/${produtoId}/ajustar-estoque`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nova_quantidade }),
  })
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}))
    throw new Error(corpo.detail ?? "falha ao ajustar estoque")
  }
}
