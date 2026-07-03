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

// campos editáveis de um produto existente — note que rfid_tag_id
// propositalmente NÃO faz parte deste tipo, pois não pode ser alterado
export type ProdutoEdicao = {
  nome: string
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

export async function atualizarProduto(
  produtoId: number,
  dados: Partial<ProdutoEdicao>,
): Promise<Produto> {
  const r = await fetch(`${BASE}/produtos/${produtoId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  })
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}))
    throw new Error(corpo.detail ?? "falha ao atualizar produto")
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

export type Preview = {
  status: "ok" | "empty" | "imprecise" | "no_change"
  produto_id: number
  produto_nome: string
  estoque_atual: number
  peso_g: string
  tipo: string | null
  quantidade: number | null
  qtd_fisica: number | null
  qtd_resultante: number | null
}

export async function operacaoPreview(produto_id: number, peso_g: string): Promise<Preview> {
  const r = await fetch(`${BASE}/operacao/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ produto_id, peso_g }),
  })
  if (!r.ok) throw new Error("falha no preview")
  return r.json()
}

export async function zerarBalanca(): Promise<void> {
  const r = await fetch(`${BASE}/operacao/tarar`, { method: "POST" })
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}))
    throw new Error(corpo.detail ?? "falha ao zerar balança")
  }
}

export async function operacaoConfirmar(produto_id: number, peso_g: string): Promise<void> {
  const r = await fetch(`${BASE}/operacao/confirmar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ produto_id, peso_g }),
  })
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}))
    throw new Error(corpo.detail ?? "falha ao confirmar")
  }
}

export type VendaItem = {
  produto_id: number
  produto_nome: string
  quantidade: number
  preco_unitario: string
  subtotal: string
}

export type Venda = {
  id: number
  status: string
  valor_total: string
  pix_copia_e_cola: string | null
  expira_em: string | null
  itens: VendaItem[]
  qr_code_base64?: string | null
}

export async function criarVenda(
  itens: { produto_id: number; quantidade: number }[],
): Promise<Venda> {
  const r = await fetch(`${BASE}/vendas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ itens }),
  })
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}))
    throw new Error(corpo.detail ?? "falha ao criar venda")
  }
  return r.json()
}

export async function getVenda(id: number): Promise<Venda> {
  const r = await fetch(`${BASE}/vendas/${id}`)
  if (!r.ok) throw new Error("falha ao consultar venda")
  return r.json()
}

export async function pagarVenda(id: number): Promise<Venda> {
  const r = await fetch(`${BASE}/vendas/${id}/pagamento`, { method: "POST" })
  if (!r.ok) throw new Error("falha ao registrar pagamento")
  return r.json()
}

export async function cancelarVenda(id: number): Promise<Venda> {
  const r = await fetch(`${BASE}/vendas/${id}/cancelar`, { method: "POST" })
  if (!r.ok) throw new Error("falha ao cancelar")
  return r.json()
}