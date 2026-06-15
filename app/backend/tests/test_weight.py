from decimal import Decimal
from inventario.domain.weight import WeightBuffer


def make_buffer():
    return WeightBuffer(samples=3, tolerance_g=Decimal("2.0"))


def test_nao_estavel_antes_de_encher_o_buffer():
    b = make_buffer()
    b.add(Decimal("100.0"))
    b.add(Decimal("100.0"))
    assert b.is_stable() is False
    assert b.stable_value() is None


def test_estavel_quando_dentro_da_tolerancia():
    b = make_buffer()
    for v in ("100.0", "101.0", "100.5"):
        b.add(Decimal(v))
    assert b.is_stable() is True
    assert b.stable_value() == Decimal("100.5")  # média das 3 leituras


def test_nao_estavel_quando_uma_leitura_salta():
    b = make_buffer()
    for v in ("100.0", "100.5", "130.0"):
        b.add(Decimal(v))
    assert b.is_stable() is False
    assert b.stable_value() is None


def test_so_considera_as_ultimas_n_leituras():
    b = make_buffer()
    for v in ("130.0", "100.0", "100.5", "101.0"):
        b.add(Decimal(v))
    assert b.is_stable() is True  # a leitura 130.0 já saiu da janela de 3
