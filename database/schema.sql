-- Inventário — DDL
-- Fonte da verdade do schema do banco de dados

CREATE TABLE IF NOT EXISTS produtos (
    id          SERIAL PRIMARY KEY,
    nome        TEXT        NOT NULL,
    codigo      TEXT        UNIQUE NOT NULL,
    preco       NUMERIC(10,2) NOT NULL,
    estoque     INTEGER     NOT NULL DEFAULT 0,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vendas (
    id          SERIAL PRIMARY KEY,
    produto_id  INTEGER     NOT NULL REFERENCES produtos(id),
    quantidade  INTEGER     NOT NULL,
    total       NUMERIC(10,2) NOT NULL,
    pago        BOOLEAN     NOT NULL DEFAULT FALSE,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
