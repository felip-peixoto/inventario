def _produto(client, **over):
    p = {"nome": "Parafuso", "rfid_tag_id": "TAG1", "peso_unitario_g": "3.2",
         "tara_caixa_g": "40", "preco_unitario": "0.15", "estoque_disponivel": 20}
    p.update(over)
    return client.post("/produtos", json=p).json()


def test_ajuste_aumenta_estoque_gera_reposicao(client):
    pid = _produto(client)["id"]
    r = client.post(f"/produtos/{pid}/ajustar-estoque", json={"nova_quantidade": 25})
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["tipo"] == "REPOSICAO"
    assert m["quantidade"] == 5
    assert m["produto_nome"] == "Parafuso"
    assert client.get(f"/produtos/{pid}").json()["estoque_disponivel"] == 25


def test_ajuste_diminui_estoque_gera_ajuste(client):
    pid = _produto(client, rfid_tag_id="TAG2")["id"]
    r = client.post(f"/produtos/{pid}/ajustar-estoque", json={"nova_quantidade": 12})
    assert r.json()["tipo"] == "AJUSTE"
    assert r.json()["quantidade"] == -8


def test_ajuste_sem_mudanca_da_400(client):
    pid = _produto(client, rfid_tag_id="TAG3")["id"]
    r = client.post(f"/produtos/{pid}/ajustar-estoque", json={"nova_quantidade": 20})
    assert r.status_code == 400


def test_ajuste_produto_inexistente_404(client):
    r = client.post("/produtos/999/ajustar-estoque", json={"nova_quantidade": 5})
    assert r.status_code == 404
