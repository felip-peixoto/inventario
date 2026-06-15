from decimal import Decimal
from inventario.domain.inventory import reconcile, ReconcileStatus


def base(**over):
    args = dict(
        produto_id=1,
        peso_g=Decimal("120.0"),
        tara_g=Decimal("40.0"),
        peso_unitario_g=Decimal("3.2"),
        estoque_disponivel=20,
        rounding_tolerance_units=Decimal("0.4"),
        empty_scale_tolerance_g=Decimal("5.0"),
    )
    args.update(over)
    return args


def test_entrada_gera_reposicao():
    # (120 - 40) / 3.2 = 25; estoque 20 -> +5
    r = reconcile(**base())
    assert r.status is ReconcileStatus.OK
    assert r.movement.tipo == "REPOSICAO"
    assert r.movement.quantidade == 5
    assert r.movement.qtd_fisica == 25
    assert r.movement.qtd_resultante == 25


def test_saida_gera_ajuste():
    # (110.4 - 40) / 3.2 = 22; estoque 25 -> -3
    r = reconcile(**base(peso_g=Decimal("110.4"), estoque_disponivel=25))
    assert r.status is ReconcileStatus.OK
    assert r.movement.tipo == "AJUSTE"
    assert r.movement.quantidade == -3
    assert r.movement.qtd_resultante == 22


def test_sem_mudanca_quando_delta_zero():
    r = reconcile(**base(estoque_disponivel=25))  # qtd_fisica 25 == estoque
    assert r.status is ReconcileStatus.NO_CHANGE
    assert r.movement is None


def test_caixa_fora_da_balanca():
    # peso 30 < tara 40 - tolerância 5
    r = reconcile(**base(peso_g=Decimal("30.0")))
    assert r.status is ReconcileStatus.EMPTY
    assert r.movement is None


def test_caixa_presente_e_vazia_e_valida():
    # peso ~ tara -> 0 unidades; estoque 4 -> AJUSTE -4
    r = reconcile(**base(peso_g=Decimal("40.0"), estoque_disponivel=4))
    assert r.status is ReconcileStatus.OK
    assert r.movement.qtd_fisica == 0
    assert r.movement.quantidade == -4


def test_leitura_imprecisa():
    # (121.5 - 40) / 3.2 = 25.468...; longe de inteiro > 0.4
    r = reconcile(**base(peso_g=Decimal("121.5")))
    assert r.status is ReconcileStatus.IMPRECISE
    assert r.movement is None
