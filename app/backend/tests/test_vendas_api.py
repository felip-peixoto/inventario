def _produto(client, nome, tag, preco, estoque):
    return client.post("/produtos", json={
        "nome": nome, "rfid_tag_id": tag, "peso_unitario_g": "1",
        "preco_unitario": preco, "tara_caixa_g": "0", "estoque_disponivel": estoque,
    }).json()


def test_criar_venda_reserva(client):
    a = _produto(client, "Refri", "A", "5.00", 8)
    b = _produto(client, "Salg", "B", "8.00", 5)
    r = client.post("/vendas", json={"itens": [
        {"produto_id": a["id"], "quantidade": 3},
        {"produto_id": b["id"], "quantidade": 2},
    ]})
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["status"] == "PENDENTE"
    assert v["valor_total"] == "31.00"
    assert v["pix_copia_e_cola"] == "COPIA_E_COLA"
    assert v["qr_code_base64"] == "BASE64IMG"
    assert len(v["itens"]) == 2
    item_a = next(i for i in v["itens"] if i["produto_id"] == a["id"])
    assert item_a["quantidade"] == 3
    assert item_a["subtotal"] == "15.00"
    assert client.get(f"/produtos/{a['id']}").json()["estoque_disponivel"] == 5


def test_criar_venda_estoque_insuficiente_409(client):
    a = _produto(client, "Refri", "A", "5.00", 1)
    r = client.post("/vendas", json={"itens": [{"produto_id": a["id"], "quantidade": 3}]})
    assert r.status_code == 409


def test_pagamento_confirma(client):
    a = _produto(client, "Refri", "A", "5.00", 8)
    vid = client.post("/vendas", json={"itens": [{"produto_id": a["id"], "quantidade": 3}]}).json()["id"]
    r = client.post(f"/vendas/{vid}/pagamento")
    assert r.status_code == 200
    assert r.json()["status"] == "CONFIRMADO"
    assert client.get(f"/produtos/{a['id']}").json()["estoque_disponivel"] == 5


def test_cancelar_devolve(client):
    a = _produto(client, "Refri", "A", "5.00", 8)
    vid = client.post("/vendas", json={"itens": [{"produto_id": a["id"], "quantidade": 3}]}).json()["id"]
    r = client.post(f"/vendas/{vid}/cancelar")
    assert r.json()["status"] == "CANCELADO"
    assert client.get(f"/produtos/{a['id']}").json()["estoque_disponivel"] == 8


def test_get_reconcilia_aprovado(client, fake_mp):
    a = _produto(client, "Refri", "A", "5.00", 8)
    vid = client.post("/vendas", json={"itens": [{"produto_id": a["id"], "quantidade": 3}]}).json()["id"]
    fake_mp.status_consulta = "approved"
    r = client.get(f"/vendas/{vid}")
    assert r.json()["status"] == "CONFIRMADO"


def test_get_venda_inexistente_404(client):
    assert client.get("/vendas/999").status_code == 404


def test_criar_venda_falha_pagamento_502_nao_reserva(client, fake_mp):
    a = _produto(client, "Refri", "A", "5.00", 8)
    fake_mp.falhar = True
    r = client.post("/vendas", json={"itens": [{"produto_id": a["id"], "quantidade": 3}]})
    assert r.status_code == 502
    assert client.get(f"/produtos/{a['id']}").json()["estoque_disponivel"] == 8
