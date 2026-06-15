"""schema inicial (DDL v2)

Revision ID: 0001
Revises:
Create Date: 2026-06-14
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
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

        CREATE TABLE movimentacoes (
            id                      SERIAL          PRIMARY KEY,
            produto_id              INT             NOT NULL REFERENCES produtos(id),
            venda_id                INT             REFERENCES vendas(id),
            tipo                    VARCHAR(20)     NOT NULL
                                        CHECK (tipo IN ('RESERVA','CONFIRMACAO','REVERSAO','REPOSICAO','AJUSTE')),
            quantidade              INT             NOT NULL,
            peso_g                  NUMERIC(10,3),
            preco_unitario_snapshot NUMERIC(10,2),
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
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_produtos_ts ON produtos;
        DROP FUNCTION IF EXISTS fn_atualizar_timestamp();
        DROP TABLE IF EXISTS movimentacoes;
        DROP TABLE IF EXISTS vendas;
        DROP TABLE IF EXISTS produtos;
        """
    )
