from decimal import Decimal
from inventario.models import Produto, Movimentacao, Venda


def test_produto_tem_defaults_de_estoque():
    p = Produto(
        nome="Parafuso M6",
        rfid_tag_id="A1B2C3D4",
        peso_unitario_g=Decimal("3.2"),
        preco_unitario=Decimal("0.15"),
    )
    assert p.estoque_disponivel == 0
    assert p.estoque_reservado == 0
    assert p.tara_caixa_g == Decimal("0")


def test_tabelas_registradas_no_metadata():
    nomes = set(Produto.metadata.tables.keys())
    assert {"produtos", "vendas", "movimentacoes"} <= nomes
