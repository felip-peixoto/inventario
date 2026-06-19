# Fase 2 — Vendas com Pagamento Pix (Mercado Pago) — Design

**Data:** 2026-06-18
**Status:** Aprovado para planejamento de implementação
**Contexto:** projeto de disciplina de faculdade (Oficina de Integração); roda localmente para apresentação.

## 1. Visão geral

Adiciona o fluxo de **venda com pagamento via Pix** (Mercado Pago) ao sistema de inventário.
O operador monta um **carrinho** (vários itens), fecha o pedido e o sistema **reserva** o
estoque, gera um **Pix** e mostra o QR Code. Quando o pagamento é confirmado, a baixa de
estoque vira **definitiva**; se o Pix expira ou é cancelado, os itens **voltam** ao estoque.

Tudo é implementado em **Python**, no backend FastAPI existente. O app Node do colega
(`index.js`) serviu como prova de que a integração com o Mercado Pago funciona; a lógica é
reescrita em Python para ficar coesa com o restante (venda, reserva, polling e transações
de banco no mesmo lugar). O `index.js`/`package.json`/`package-lock.json` da raiz podem ser
removidos numa limpeza futura (fora do escopo desta spec).

## 2. Escopo

### Dentro do escopo
- Carrinho de venda (múltiplos itens) na tela de **Operação**.
- Reserva de estoque ao fechar o pedido (máquina de estados RESERVA → CONFIRMACAO/REVERSAO).
- Geração do Pix no Mercado Pago e exibição do QR Code + copia-e-cola.
- Detecção de pagamento por **polling** guiado pela tela.
- Botão **Pagamento** (demo) que confirma a venda sem depender do sandbox.
- Botão **Cancelar** e expiração automática (devolvem o estoque).
- Os movimentos de venda aparecem no **Histórico** existente.

### Fora do escopo
- Webhook do Mercado Pago (escolhido polling).
- Tarefa em segundo plano para reconciliar vendas sem a tela aberta.
- Carrinho alimentado pela balança/RFID (a coluna de movimento por peso permanece
  independente nesta fase).
- Reorganização do app Node do colega.

## 3. Arquitetura

Novos módulos em `app/backend/src/inventario/`:

- **`pagamentos/mercadopago.py`** — único ponto que importa o SDK do Mercado Pago. Expõe:
  - `criar_pagamento_pix(valor, descricao) -> PagamentoPix` (com `id`, `status`, `qr_code`
    copia-e-cola, `qr_code_base64`, `expira_em`);
  - `consultar_pagamento(payment_id) -> str` (status, ex.: `"approved"`, `"pending"`).
- **`services_venda.py`** — ciclo de vida da venda (criar/reservar, confirmar, reverter,
  reconciliar). Recebe o cliente do Mercado Pago por **injeção de dependência** (testável
  com um cliente falso, sem rede).
- **`api/vendas.py`** — endpoints REST.
- **`schemas.py`** (estender) — schemas de entrada/saída de venda.
- **`config.py`** (estender) — `mercadopago_access_token`, `venda_expiracao_minutos`.

O front consome os endpoints na **tela de Operação** (três colunas).

## 4. Modelo de dados (reutiliza o schema existente)

Sem tabelas novas. A Fase 2 usa o que já existe:

- **`vendas`** — uma linha por pedido: `status` (`PENDENTE`/`CONFIRMADO`/`CANCELADO`/
  `EXPIRADO`), `valor_total`, `pix_txid`, `pix_qrcode` (copia-e-cola), `criado_em`,
  `confirmado_em`, `expira_em`.
- **`movimentacoes`** — os **itens do carrinho são as próprias movimentações `RESERVA`**
  da venda. Cada uma carrega `venda_id`, `produto_id`, `quantidade` e
  `preco_unitario_snapshot`. Não há tabela `venda_itens`.
- **`produtos`** — `estoque_disponivel` (livre para vender) e `estoque_reservado`.

### Convenção do `quantidade` (auditoria)
A fonte da verdade do estoque são as colunas `estoque_disponivel`/`estoque_reservado`,
atualizadas em transação a cada movimento. `movimentacoes` é o **log de auditoria**:

| Tipo | Efeito no estoque | `quantidade` |
|---|---|---|
| `RESERVA` | `disponivel −= q`, `reservado += q` | `−q` |
| `CONFIRMACAO` | `reservado −= q` | `−q` |
| `REVERSAO` | `reservado −= q`, `disponivel += q` | `+q` |

(Não somar `quantidade` para derivar estoque — as colunas são a verdade.)

## 5. Máquina de estados da venda

```
montar carrinho
   │  POST /vendas  (valida estoque de TODOS os itens antes de reservar)
   ▼
PENDENTE ── RESERVA por item (transação) + cria Pix no MP (pix_txid, qr, expira_em)
   │
   ├── pago: polling vê "approved"  OU  botão "Pagamento"
   │        └─► CONFIRMACAO por item  →  CONFIRMADO  (confirmado_em)
   │
   ├── agora > expira_em ──────┐
   └── botão "Cancelar" ───────┴─► REVERSAO por item  →  EXPIRADO / CANCELADO
```

Confirmação e reversão **só agem sobre venda `PENDENTE`** (idempotência — evita processar
duas vezes).

## 6. Fluxo de dados — exemplo

Início: Refrigerante (R$5,00, disp 8) e Salgadinho (R$8,00, disp 5). Carrinho: 3× Refri + 2× Salg.

1. **`POST /vendas`** — valida (8≥3, 5≥2); reserva:
   - Refri: disp 8→5, reserv 0→3 (`RESERVA −3`); Salg: disp 5→3, reserv 0→2 (`RESERVA −2`).
   - Venda `PENDENTE`, `valor_total = R$31,00`, Pix gerado, `expira_em = agora+30min`.
2A. **Pago** (polling/`Pagamento`): Refri reserv 3→0, Salg reserv 2→0 (`CONFIRMACAO`). Venda `CONFIRMADO`. Disp final 5 e 3.
2B. **Expira/Cancela**: Refri reserv 3→0 disp 5→8, Salg reserv 2→0 disp 3→5 (`REVERSAO`). Venda `EXPIRADO`/`CANCELADO`. Estoque volta a 8 e 5.

## 7. Endpoints (`api/vendas.py`)

- **`POST /vendas`** — body `{ "itens": [ { "produto_id": int, "quantidade": int }, ... ] }`.
  Valida estoque de todos os itens (senão **409**, nada reservado). Em transação: reserva
  cada item (RESERVA) e cria a `venda`. Chama o Mercado Pago **antes** de gravar; se o MP
  falhar, a venda não é criada e nada é reservado. Retorna `VendaRead` + `qr_code_base64`.
- **`GET /vendas/{id}`** — retorna a venda (status, total, copia-e-cola, expira_em, itens).
  **Reconcilia** quando `PENDENTE`: consulta o MP → `approved` dispara CONFIRMACAO/CONFIRMADO;
  `agora > expira_em` dispara REVERSAO/EXPIRADO. É o endpoint do polling. 404 se não existir.
- **`POST /vendas/{id}/pagamento`** — botão **Pagamento** (demo): confirma direto
  (CONFIRMACAO/CONFIRMADO) sem consultar o MP. 409 se a venda não estiver PENDENTE.
- **`POST /vendas/{id}/cancelar`** — botão **Cancelar**: REVERSAO/CANCELADO. 409 se não PENDENTE.

### Schemas
- `VendaItemIn { produto_id: int, quantidade: int }`
- `VendaCreate { itens: list[VendaItemIn] }`
- `VendaItemRead { produto_id, produto_nome, quantidade, preco_unitario, subtotal }`
  (reconstruído a partir das movimentações `RESERVA` da venda; `quantidade` exibida = valor
  absoluto do `−q` da RESERVA; `preco_unitario` = `preco_unitario_snapshot`; `subtotal =
  quantidade × preco_unitario`)
- `VendaRead { id, status, valor_total, pix_copia_e_cola, expira_em, itens: list[VendaItemRead] }`
- `qr_code_base64` é retornado **apenas** na resposta do `POST /vendas` (a imagem não é
  persistida; o front a guarda em memória enquanto a tela está aberta).

## 8. Serviços (`services_venda.py`)

- `criar_venda(session, itens, mp) -> Venda` — valida estoque (levanta `EstoqueInsuficiente`
  → 409); calcula `valor_total`; chama `mp.criar_pagamento_pix`; em transação grava as
  RESERVA (com `preco_unitario_snapshot`), atualiza estoques e cria a `venda`.
- `confirmar_pagamento(session, venda)` — para cada RESERVA da venda: CONFIRMACAO,
  `reservado −= q`; venda `CONFIRMADO`, `confirmado_em`. Só se `PENDENTE`.
- `reverter_venda(session, venda, status)` — para cada RESERVA: REVERSAO, `reservado −= q`,
  `disponivel += q`; venda `EXPIRADO`/`CANCELADO`. Só se `PENDENTE`.
- `reconciliar(session, venda, mp)` — se não `PENDENTE`, retorna; se `agora > expira_em`,
  reverte (EXPIRADO); senão consulta o MP e confirma se `approved`.

Os itens de uma venda são obtidos por `SELECT ... FROM movimentacoes WHERE venda_id = ? AND
tipo = 'RESERVA'`.

> Concorrência: para o cenário de apresentação (operador único) não há trava de linha.
> Em produção, `SELECT ... FOR UPDATE` no produto evitaria reservas concorrentes — fora do
> escopo aqui.

## 9. Cliente Mercado Pago (`pagamentos/mercadopago.py`)

- Usa o SDK `mercadopago` com `settings.mercadopago_access_token`.
- `criar_pagamento_pix(valor, descricao)`: cria pagamento `payment_method_id="pix"`,
  `transaction_amount=valor`, `date_of_expiration = agora + venda_expiracao_minutos`.
  Extrai `id`, `status`, `point_of_interaction.transaction_data.qr_code` (copia-e-cola),
  `qr_code_base64` e a expiração.
- `consultar_pagamento(payment_id)`: retorna o `status` do pagamento.
- Interface estável (não vaza "Mercado Pago" para o resto do sistema), injetável nos testes.

## 10. Interface — tela de Operação (três colunas)

- **Esquerda (inalterada):** movimento por peso (beta manual atual).
- **Meio:** **carrinho**, sempre visível — seletor de produto + quantidade + "adicionar",
  lista de itens com subtotal e remoção, total, e botão **"Fechar pedido · gerar Pix"**.
- **Direita:** antes de fechar, um aviso ("feche o pedido para gerar o Pix"); depois de
  fechar, o **QR Code** + copia-e-cola + status ("aguardando pagamento", com contador até
  `expira_em`) + botões **Pagamento** e **Cancelar**. O carrinho **continua visível** ao lado.
- Enquanto a venda está `PENDENTE`, o front faz **polling** em `GET /vendas/{id}` a cada
  ~3s e reage: `CONFIRMADO` → "Pago ✅"; `EXPIRADO`/`CANCELADO` → "itens devolvidos ↩️".
- O **Histórico** existente passa a exibir RESERVA/CONFIRMACAO/REVERSAO (adicionar os tipos
  ao filtro e às cores de badge).

## 11. Tratamento de erros

- Estoque insuficiente em qualquer item → **409**, nada reservado (validação prévia).
- Falha na chamada ao Mercado Pago → venda não criada, nada reservado.
- Confirmar/cancelar venda não-`PENDENTE` → **409** (ou no-op idempotente).
- Venda inexistente → **404**.

## 12. Testes (Mercado Pago mockado)

Backend com o `conftest` SQLite existente, injetando um **cliente MP falso** (sem rede):
- criar venda: reserva todos os itens, calcula `valor_total`, cria `PENDENTE` com os campos
  de Pix preenchidos pelo cliente falso, gera as RESERVA.
- estoque insuficiente: 409, estoques inalterados.
- confirmar: CONFIRMACAO, `reservado` volta a 0, `disponivel` permanece abatido, `CONFIRMADO`.
- cancelar/expirar: REVERSAO, estoques restaurados, `CANCELADO`/`EXPIRADO`.
- reconciliar: MP falso `approved` → confirma; `agora > expira_em` → reverte.
- endpoint `pagamento`: confirma a venda.

## 13. Configuração

`.env`/`Settings`:
- `MERCADOPAGO_ACCESS_TOKEN` — token de teste do Mercado Pago (padroniza o nome; o app Node
  usava `ACCESS_TOKEN`).
- `VENDA_EXPIRACAO_MINUTOS=30` — expiração do Pix (pode encurtar para demonstrar a expiração).

## 14. Critérios de sucesso

1. Montar um carrinho com vários itens e fechar o pedido, reservando o estoque (disponível cai na hora).
2. Ver o QR Code + copia-e-cola gerados pelo Mercado Pago (token de teste).
3. Confirmar o pagamento (real no sandbox **ou** pelo botão **Pagamento**) → baixa definitiva, venda `CONFIRMADO`.
4. Cancelar ou deixar expirar → estoque devolvido, venda `CANCELADO`/`EXPIRADO`.
5. Ver RESERVA/CONFIRMACAO/REVERSAO no Histórico.
6. Tudo rodando em Docker, com os testes (MP mockado) passando.
