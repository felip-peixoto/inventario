# Sistema de Inventário com Balança RFID — Design (Fase 1)

**Data:** 2026-06-14
**Status:** Aprovado para planejamento de implementação

## 1. Visão geral

Software de gestão de inventário que recebe leituras de um dispositivo físico (ESP32 +
leitor RFID RC522 montado como balança) e mantém o estoque de produtos atualizado em
tempo real. Cada produto fica numa caixa com uma tag RFID; a balança informa o peso, e o
software calcula a quantidade de unidades a partir do peso.

O projeto tem **duas fases**:

- **Fase 1 (este documento):** gestão de inventário — cadastro de produtos, leitura em
  tempo real pela balança, registro de entradas/saídas e histórico.
- **Fase 2 (fora de escopo aqui):** transações de venda via PIX (Mercado Pago), com
  reserva de estoque. O modelo de dados já contempla a Fase 2, mas nada dela é
  implementado agora.

## 2. Escopo

### Dentro do escopo (Fase 1)

- CRUD de produtos, com captura de tag e tara direto da balança.
- Leitura serial contínua da ESP32 (peso 1×/s) e esporádica (tag RFID).
- Cálculo de quantidade por peso e reconciliação automática contra o último estoque.
- Detecção automática de entrada/saída pelo sinal da diferença, com **confirmação manual**
  antes de gravar.
- Histórico imutável de movimentações, com filtros.
- Empacotamento via Docker Compose para rodar com `git clone` + `docker compose up`.

### Fora do escopo (Fase 2)

- Integração de pagamento PIX / Mercado Pago, geração de QR Code/Copia e Cola.
- Ciclo de venda: reserva, confirmação via webhook, reversão por expiração.
- Tipos de movimentação `RESERVA`, `CONFIRMACAO`, `REVERSAO`.
- Uso da tabela `vendas` e da coluna `estoque_reservado`.

### Premissas e dependências

- **Firmware fora do escopo deste plano.** Assume-se que a ESP32 já emitirá o protocolo
  serial (`PESO:`/`TAG:`) com o **peso já em gramas**. Hoje o repositório só tem sketches
  de teste isolados (`teste_hx711.cpp` lê o valor bruto da célula, sem calibração;
  `teste_rc522.cpp` imprime o UID; `main.cpp` vazio). A integração dos sensores, a
  calibração do HX711 (bruto → gramas) e a emissão do protocolo são responsabilidade da
  equipe de hardware, à parte.
- O software depende apenas do **contrato do protocolo** (§6), não da implementação do firmware.

## 3. Arquitetura

Três containers num único `docker-compose.yml`, rodando no notebook Linux da apresentação.
O banco é **local** (containerizado) — não há dependência de serviço externo.

```
┌─────────────────────────────────────────────────────────────┐
│  Notebook Linux                                              │
│                                                             │
│   ESP32 ──/dev/ttyUSB0──┐ (passado ao container via --device) │
│                         │                                    │
│   ┌─────────────────────▼───────────────┐                    │
│   │ Container: backend (FastAPI/Python)  │                   │
│   │  • serial_reader (thread pyserial)   │                   │
│   │  • inventory_state (peso/conexão)    │                   │
│   │  • inventory_service (regras)        │── psycopg ──┐     │
│   │  • REST API + WebSocket              │             │     │
│   └──────────────▲───────────────────────┘             ▼     │
│                  │ HTTP + WS              ┌──────────────────┐│
│   ┌──────────────┴──────────────┐        │ Container: db    ││
│   │ Container: frontend (React) │        │ Postgres + volume││
│   │  build estático via Nginx   │        └──────────────────┘│
│   └─────────────────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

- `db`: Postgres com volume nomeado para persistência. Migrations rodam no startup do backend.
- `backend`: recebe `--device=${SERIAL_PORT}` e as variáveis do `.env`.
- `frontend`: build estático do React servido por Nginx.

### 3.1 Estrutura do repositório

Monorepo (repo `inventario`), reorganizado a partir do setup inicial genérico:

```
inventario/
├── firmware/                 # código da ESP32 (mantido; flashado no chip, fora do Docker)
├── app/
│   ├── backend/              # FastAPI: serial, inventário, e pagamentos/ (Fase 2)
│   └── frontend/             # React (substitui o stub Tkinter de app/ui)
├── database/                 # migrations Alembic (substitui a schema.sql genérica)
├── docs/                     # esta spec
├── docker-compose.yml        # sobe db + backend + frontend
├── .env.example              # atualizado para Postgres local
└── README.md                 # atualizado com o setup real
```

**Reaproveitamento do setup inicial:** `app/serial_reader.py` (pyserial, baud 115200) e
`app/pix.py` (SDK Mercado Pago, para a Fase 2) servem de ponto de partida. São
descartados/substituídos: o stub Tkinter (`app/ui`), a `database/schema.sql` genérica e o
`DATABASE_URL` do Supabase no `.env.example`. Nenhum conteúdo pré-existente do repositório
sobrepõe as decisões deste design.

## 4. Stack tecnológica

| Camada      | Tecnologia                                              |
|-------------|---------------------------------------------------------|
| Backend     | Python + FastAPI (REST + WebSocket)                      |
| Serial      | `pyserial` em thread dedicada                            |
| ORM         | SQLAlchemy / SQLModel                                    |
| Migrations  | Alembic (rodam no startup do container backend)          |
| Banco       | PostgreSQL (containerizado, com volume)                  |
| Frontend    | React + Vite + TypeScript + Tailwind + shadcn/ui         |
| Empacotamento | Docker + Docker Compose                               |

## 5. Modelo de dados

DDL definitiva (PostgreSQL). Inclui tabelas e colunas da Fase 2, que ficam inertes na
Fase 1.

```sql
CREATE TABLE produtos (
    id                  SERIAL          PRIMARY KEY,
    nome                VARCHAR(150)    NOT NULL,
    rfid_tag_id         VARCHAR(50)     NOT NULL UNIQUE,
    peso_unitario_g     NUMERIC(10,3)   NOT NULL,
    tara_caixa_g        NUMERIC(10,3)   NOT NULL DEFAULT 0,
    preco_unitario      NUMERIC(10,2)   NOT NULL,
    estoque_disponivel  INT             NOT NULL DEFAULT 0 CHECK (estoque_disponivel >= 0),
    estoque_reservado   INT             NOT NULL DEFAULT 0 CHECK (estoque_reservado  >= 0),
    criado_em           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Fase 2: uma linha por sessão de compra (geração + confirmação do Pix)
CREATE TABLE vendas (
    id              SERIAL          PRIMARY KEY,
    status          VARCHAR(20)     NOT NULL DEFAULT 'PENDENTE'
                        CHECK (status IN ('PENDENTE','CONFIRMADO','CANCELADO','EXPIRADO')),
    valor_total     NUMERIC(10,2)   NOT NULL DEFAULT 0,
    pix_txid        VARCHAR(100)    UNIQUE,
    pix_qrcode      TEXT,
    criado_em       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    confirmado_em   TIMESTAMPTZ,
    expira_em       TIMESTAMPTZ
);

-- Toda movimentação de estoque passa por aqui
CREATE TABLE movimentacoes (
    id                      SERIAL          PRIMARY KEY,
    produto_id              INT             NOT NULL REFERENCES produtos(id),
    venda_id                INT             REFERENCES vendas(id),  -- NULL em reposições/ajustes
    tipo                    VARCHAR(20)     NOT NULL
                                CHECK (tipo IN (
                                    'RESERVA',      -- Fase 2
                                    'CONFIRMACAO',  -- Fase 2
                                    'REVERSAO',     -- Fase 2
                                    'REPOSICAO',    -- Fase 1: entrada (peso subiu)
                                    'AJUSTE'        -- Fase 1: saída/correção (peso desceu)
                                )),
    quantidade              INT             NOT NULL,  -- positivo = entrada, negativo = saída
    peso_g                  NUMERIC(10,3),             -- peso lido na operação
    preco_unitario_snapshot NUMERIC(10,2),             -- só em vendas (Fase 2)
    criado_em               TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_produtos_rfid ON produtos(rfid_tag_id);
CREATE INDEX idx_vendas_status ON vendas(status);
CREATE INDEX idx_vendas_pix    ON vendas(pix_txid);
CREATE INDEX idx_mov_produto   ON movimentacoes(produto_id);
CREATE INDEX idx_mov_venda     ON movimentacoes(venda_id);

CREATE OR REPLACE FUNCTION fn_atualizar_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_produtos_ts
    BEFORE UPDATE ON produtos
    FOR EACH ROW EXECUTE FUNCTION fn_atualizar_timestamp();
```

### Decisões de modelagem

- **1 produto = 1 tag = 1 caixa.** A tag e a tara ficam no próprio produto; não existe tabela
  de caixas. Não há suporte a múltiplas caixas do mesmo produto (simplificação assumida).
- **Estoque é armazenado**, não derivado: `estoque_disponivel` é mantido pelas
  movimentações dentro de transações. Na Fase 1, `estoque_reservado` é sempre 0.
- **`movimentacoes.quantidade` é com sinal** (positivo = entrada, negativo = saída); `tipo`
  rotula a natureza do movimento.
- Migrations Alembic reproduzem exatamente esta DDL (incluindo função e trigger).

## 6. Protocolo serial (ESP32 → software)

```
Transporte : serial USB, ASCII, cada mensagem terminada em '\n'
Baud rate  : 115200  (configurável via SERIAL_BAUD)

Mensagens:
  PESO:<float 1 casa>      ex.:  PESO:1234.5     → enviada 1×/segundo
  TAG:<hex sem espaços>    ex.:  TAG:A1B2C3D4    → enviada ao ler uma tag

Regras do parser:
  • trim de espaços; prefixo case-insensitive
  • linhas que não casam com PESO:/TAG: são ignoradas (ruído de boot da ESP32)
  • TAG normalizada (maiúsculas, sem espaços) antes de virar rfid_tag_id
  • sem nenhum PESO por > DEVICE_TIMEOUT_S → estado "desconectado"
```

O firmware da ESP32 deve terminar cada mensagem com `\n` (`Serial.println`).

## 7. Lógica de inventário

### 7.1 Estado em memória

O backend mantém, alimentado pela thread serial:

- **peso atual** (último valor do stream);
- **buffer das últimas N leituras** para avaliar estabilidade;
- **timestamp da última leitura de peso** (para o heartbeat de conexão).

### 7.2 Estabilização do peso

O peso só é considerado **estável** quando as últimas `WEIGHT_STABILITY_SAMPLES` leituras
variam menos que `WEIGHT_STABILITY_TOLERANCE_G`. O cálculo de quantidade usa apenas o peso
estável, evitando registrar leituras durante a oscilação ao apoiar a caixa.

### 7.3 Cálculo e reconciliação (ao ler uma tag)

1. Normaliza a tag e busca o produto por `rfid_tag_id`.
   - **Não encontrado** → emite evento `tag_desconhecida` (a UI oferece cadastrar com a tag).
   - **Caixa não está (totalmente) na balança** (peso < tara − tolerância) → emite aviso,
     não calcula. Observação: peso ≈ tara é válido (caixa presente e vazia, `qtd_fisica = 0`).
2. `qtd_fisica = round((peso_g - tara_caixa_g) / peso_unitario_g)`.
3. **Guarda de imprecisão:** se a parte fracionária de `(peso_g - tara_caixa_g) /
   peso_unitario_g` estiver a mais de `ROUNDING_TOLERANCE_UNITS` de um inteiro, marca
   "leitura imprecisa, confira a caixa" em vez de arredondar cegamente.
4. `delta = qtd_fisica - estoque_disponivel`.
   - `delta > 0` → tipo `REPOSICAO` (entrada), `quantidade = +delta`.
   - `delta < 0` → tipo `AJUSTE` (saída), `quantidade = delta` (negativo).
   - `delta = 0` → ignora (nada mudou).
5. Emite via WebSocket um **movimento PENDENTE** (preview). **Nada é gravado ainda.**

### 7.4 Confirmação (efetivação)

Ao clicar **Confirmar**, o backend executa, **numa única transação**:

1. `INSERT` em `movimentacoes` (`produto_id`, `venda_id = NULL`, `tipo`, `quantidade` com
   sinal, `peso_g`, `preco_unitario_snapshot = NULL`).
2. `UPDATE produtos SET estoque_disponivel = qtd_fisica` (o trigger atualiza `atualizado_em`).

> Nota Fase 2: quando houver reservas, o estoque físico equivale a
> `estoque_disponivel + estoque_reservado`; o `UPDATE` passará a considerar o reservado.
> Na Fase 1, como `estoque_reservado = 0`, `estoque_disponivel = qtd_fisica`.

**Cancelar** descarta o pendente sem gravar nada.

## 8. Interface (telas)

Shell em dashboard: menu lateral fixo com **Operação · Produtos · Histórico**.

### 8.1 Operação (tempo real)

Layout em painel: menu à esquerda, operação no centro, feed de movimentos recentes à
direita. No topo: indicador de conexão (● conectado/desconectado) e peso ao vivo. No
centro: produto identificado, badge ENTRADA/SAÍDA com o delta, estoque atual → resultante,
e botões **Confirmar / Cancelar**. Atualização via WebSocket.

### 8.2 Produtos (CRUD)

Tabela à esquerda, formulário à direita. Colunas da tabela: nome, tag, peso unitário, tara,
**peso total** (calculado: `tara + estoque × peso_unitário`), preço, estoque disponível.
Linha em destaque visual (amarelo) quando estoque baixo — apenas visual, sem
notificação/alerta.

Formulário de cadastro/edição:

- **Nome**
- **Tag RFID** + botão **⊙ Capturar** (preenche com a próxima leitura RFID da balança).
- **Peso unitário (g)**
- **Peso total (g)** + botão **⚖ Pesar** — campo de conferência: põe a caixa cheia na
  balança. Painel valida ao vivo `tara + estoque × peso_unitário` contra o peso total medido
  (verde se bate, vermelho se não bate).
- **Tara da caixa (g)** + botão **⚖ Tarar** (põe a caixa vazia na balança e grava o peso).
- **Estoque inicial**
- **Preço unitário (R$)** — cadastrado agora, usado na Fase 2.

### 8.3 Histórico

Tabela da `movimentacoes` (registro imutável). Colunas: data/hora, produto, tipo (badge
colorido: REPOSIÇÃO verde / AJUSTE amarelo), quantidade com sinal (+verde / −vermelho),
peso lido, estoque resultante. Filtros por produto, tipo e período. A Fase 2 adiciona os
tipos de venda neste mesmo histórico.

## 9. Componentes e interfaces (backend)

- **`serial_reader`** — thread; lê linhas, faz parse/classificação, alimenta `inventory_state`
  e dispara processamento de tag. Depende de `pyserial`.
- **`inventory_state`** — peso atual, buffer de estabilidade, status de conexão. Sem I/O.
- **`inventory_service`** — regras de cálculo, reconciliação e confirmação transacional.
  Depende dos repositórios/ORM.
- **`ws_manager`** — registra clientes e faz broadcast de eventos.
- **`api` (REST)** — endpoints de produtos e movimentações.
- **`models`/`repositories`** — SQLAlchemy/SQLModel + acesso ao banco.
- **`migrations`** — Alembic.

### Eventos WebSocket (backend → frontend)

- `conexao` — `{ conectado: bool }`
- `peso` — `{ peso_g, estavel: bool }`
- `movimento_pendente` — `{ produto, tipo, delta, peso_g, qtd_resultante }`
- `tag_desconhecida` — `{ tag_uid }`
- `movimento_confirmado` — `{ ...movimentacao }` (para sincronizar outras telas)

### Endpoints REST (esboço)

- `GET/POST /produtos`, `PUT/DELETE /produtos/{id}`
- `GET /movimentacoes?produto_id=&tipo=&periodo=`
- `POST /movimentacoes` — confirma o movimento pendente (efetiva a transação da §7.4)

## 10. Tratamento de erros e casos de borda

- **Dispositivo desconectado:** sem `PESO` por `DEVICE_TIMEOUT_S` → indicador na UI.
- **Tag desconhecida:** evento dedicado; UI oferece cadastro pré-preenchido com a tag.
- **Balança vazia ao ler tag:** ignora/avisa, não calcula.
- **Leitura imprecisa:** fracionário longe de inteiro → avisa em vez de arredondar.
- **Delta zero:** ignorado (nenhuma movimentação criada).
- **Ruído serial:** linhas fora do protocolo são descartadas silenciosamente.

## 11. Configuração e deployment

Arquivo `.env` (fora do git):

```
SERIAL_PORT=/dev/ttyUSB0
SERIAL_BAUD=115200
DATABASE_URL=postgresql+psycopg://inventario:senha@db:5432/inventario
POSTGRES_USER=inventario
POSTGRES_PASSWORD=senha
POSTGRES_DB=inventario
WEIGHT_STABILITY_SAMPLES=3
WEIGHT_STABILITY_TOLERANCE_G=2.0
ROUNDING_TOLERANCE_UNITS=0.4
DEVICE_TIMEOUT_S=5

# Fase 2 (PIX / Mercado Pago) — inerte na Fase 1
MERCADOPAGO_ACCESS_TOKEN=CHANGE_ME
```

`docker-compose.yml` sobe `db`, `backend` e `frontend`. O `backend` recebe o dispositivo
serial via `devices: ["${SERIAL_PORT}:${SERIAL_PORT}"]` e roda `alembic upgrade head` antes
do servidor. Fluxo de uso: `git clone` → preencher `.env` → `docker compose up`.

O README documenta como descobrir a porta serial (`ls /dev/ttyUSB* /dev/ttyACM*`).

## 12. Critérios de sucesso (Fase 1)

1. Cadastrar, editar e excluir produtos, com captura de tag e tara pela balança e
   conferência por peso total.
2. Exibir peso ao vivo e status de conexão da ESP32.
3. Ao ler uma tag, detectar automaticamente entrada/saída, mostrar o movimento pendente e,
   após **Confirmar**, gravar a movimentação e atualizar o estoque numa transação.
4. Listar o histórico de movimentações com filtros por produto, tipo e período.
5. Subir a aplicação inteira num notebook Linux com `docker compose up`.
