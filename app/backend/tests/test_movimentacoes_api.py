def _setup(client):
    p = client.post("/produtos", json={"nome": "Parafuso", "rfid_tag_id": "T1",
        "peso_unitario_g": "3.2", "tara_caixa_g": "40", "preco_unitario": "0.15",
        "estoque_disponivel": 20}).json()
    client.post(f"/produtos/{p['id']}/ajustar-estoque", json={"nova_quantidade": 25})
    client.post(f"/produtos/{p['id']}/ajustar-estoque", json={"nova_quantidade": 22})
    return p


def test_lista_movimentacoes(client):
    _setup(client)
    r = client.get("/movimentacoes")
    assert r.status_code == 200
    dados = r.json()
    assert len(dados) == 2
    assert dados[0]["produto_nome"] == "Parafuso"
    assert {d["tipo"] for d in dados} == {"REPOSICAO", "AJUSTE"}


def test_filtra_por_tipo(client):
    _setup(client)
    r = client.get("/movimentacoes", params={"tipo": "AJUSTE"})
    assert len(r.json()) == 1
    assert r.json()[0]["tipo"] == "AJUSTE"


def test_filtra_por_produto(client):
    p = _setup(client)
    r = client.get("/movimentacoes", params={"produto_id": p["id"]})
    assert len(r.json()) == 2
    r2 = client.get("/movimentacoes", params={"produto_id": 999})
    assert r2.json() == []
