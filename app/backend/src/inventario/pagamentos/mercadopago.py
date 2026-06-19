from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol

import mercadopago


class PagamentoError(Exception):
    """Falha ao falar com o provedor de pagamento (token inválido, indisponível, etc.)."""


@dataclass(frozen=True)
class PagamentoPix:
    id: str
    status: str
    qr_code: str          # copia-e-cola
    qr_code_base64: str
    expira_em: datetime


class ClientePagamento(Protocol):
    def criar_pagamento_pix(self, valor: Decimal, descricao: str) -> PagamentoPix: ...
    def consultar_pagamento(self, pagamento_id: str) -> str: ...


class MercadoPago:
    """Cliente real. Não é testado por unidade (boundary); validado com token manual."""

    def __init__(self, access_token: str, expiracao_minutos: int):
        self._sdk = mercadopago.SDK(access_token)
        self._expiracao_minutos = expiracao_minutos

    def criar_pagamento_pix(self, valor: Decimal, descricao: str) -> PagamentoPix:
        expira_em = datetime.now(timezone.utc) + timedelta(minutes=self._expiracao_minutos)
        resp = self._sdk.payment().create(
            {
                "transaction_amount": float(valor),
                "description": descricao,
                "payment_method_id": "pix",
                "payer": {"email": "comprador@example.com"},
            }
        )
        dados = resp.get("response") or {}
        tx = (dados.get("point_of_interaction") or {}).get("transaction_data")
        if tx is None:
            raise PagamentoError(dados.get("message") or "falha ao gerar o Pix no Mercado Pago")
        return PagamentoPix(
            id=str(dados["id"]),
            status=dados["status"],
            qr_code=tx["qr_code"],
            qr_code_base64=tx["qr_code_base64"],
            expira_em=expira_em,
        )

    def consultar_pagamento(self, pagamento_id: str) -> str:
        resp = self._sdk.payment().get(pagamento_id)
        return (resp.get("response") or {}).get("status", "pending")
