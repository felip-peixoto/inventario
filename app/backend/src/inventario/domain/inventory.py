from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


class ReconcileStatus(str, Enum):
    OK = "ok"
    EMPTY = "empty"          # caixa não está (totalmente) na balança
    IMPRECISE = "imprecise"  # leitura longe de um inteiro
    NO_CHANGE = "no_change"  # delta zero


@dataclass(frozen=True)
class PendingMovement:
    produto_id: int
    tipo: str           # 'REPOSICAO' | 'AJUSTE'
    quantidade: int     # com sinal: + entrada, - saída
    peso_g: Decimal
    qtd_fisica: int
    qtd_resultante: int


@dataclass(frozen=True)
class ReconcileResult:
    status: ReconcileStatus
    movement: PendingMovement | None = None


def reconcile(
    *,
    produto_id: int,
    peso_g: Decimal,
    tara_g: Decimal,
    peso_unitario_g: Decimal,
    estoque_disponivel: int,
    rounding_tolerance_units: Decimal,
    empty_scale_tolerance_g: Decimal,
) -> ReconcileResult:
    peso_g = Decimal(str(peso_g))
    tara_g = Decimal(str(tara_g))
    peso_unitario_g = Decimal(str(peso_unitario_g))

    # caixa não está (totalmente) na balança
    if peso_g < tara_g - Decimal(str(empty_scale_tolerance_g)):
        return ReconcileResult(ReconcileStatus.EMPTY)

    liquido = peso_g - tara_g
    if liquido < 0:
        liquido = Decimal(0)

    unidades = liquido / peso_unitario_g
    qtd_fisica = int(unidades.to_integral_value(rounding=ROUND_HALF_UP))

    if abs(unidades - qtd_fisica) > Decimal(str(rounding_tolerance_units)):
        return ReconcileResult(ReconcileStatus.IMPRECISE)

    delta = qtd_fisica - estoque_disponivel
    if delta == 0:
        return ReconcileResult(ReconcileStatus.NO_CHANGE)

    tipo = "REPOSICAO" if delta > 0 else "AJUSTE"
    movement = PendingMovement(
        produto_id=produto_id,
        tipo=tipo,
        quantidade=delta,
        peso_g=peso_g,
        qtd_fisica=qtd_fisica,
        qtd_resultante=qtd_fisica,
    )
    return ReconcileResult(ReconcileStatus.OK, movement)
