from decimal import Decimal
from inventario.schemas import ProdutoRead


def test_peso_total_calculado():
    p = ProdutoRead(
        id=1,
        nome="Parafuso M6",
        rfid_tag_id="A1B2C3D4",
        peso_unitario_g=Decimal("3.2"),
        tara_caixa_g=Decimal("40"),
        preco_unitario=Decimal("0.15"),
        estoque_disponivel=25,
        estoque_reservado=0,
    )
    # 40 + 25 * 3.2 = 120.0
    assert p.peso_total_g == Decimal("120.0")
