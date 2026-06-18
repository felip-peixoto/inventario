def _produto(client, **over):
    p = {"nome": "Parafuso", "rfid_tag_id": "T1", "peso_unitario_g": "3.2",
         "tara_caixa_g": "40", "preco_unitario": "0.15", "estoque_disponivel": 20}
    p.update(over)
    return client.post("/produtos", json=p).json()


def test_preview_entrada(client):
    pid = _produto(client)["id"]
    r = client.post("/operacao/preview", json={"produto_id": pid, "peso_g": "120"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "ok"
    assert b["tipo"] == "REPOSICAO"
    assert b["quantidade"] == 5
    assert b["qtd_fisica"] == 25
    assert b["qtd_resultante"] == 25
    assert b["estoque_atual"] == 20


def test_preview_caixa_fora(client):
    pid = _produto(client)["id"]
    r = client.post("/operacao/preview", json={"produto_id": pid, "peso_g": "30"})
    assert r.json()["status"] == "empty"
    assert r.json()["tipo"] is None


def test_preview_imprecisa(client):
    pid = _produto(client)["id"]
    r = client.post("/operacao/preview", json={"produto_id": pid, "peso_g": "121.5"})
    assert r.json()["status"] == "imprecise"


def test_confirmar_grava_com_peso(client):
    # (110.4 - 40) / 3.2 = 22 unidades ; estoque 20 -> +2 -> REPOSICAO
    pid = _produto(client)["id"]
    r = client.post("/operacao/confirmar", json={"produto_id": pid, "peso_g": "110.4"})
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["tipo"] == "REPOSICAO"
    assert m["quantidade"] == 2
    assert m["peso_g"] == "110.400"
    assert client.get(f"/produtos/{pid}").json()["estoque_disponivel"] == 22
    movs = client.get("/movimentacoes").json()
    assert movs[0]["peso_g"] == "110.400"


def test_confirmar_sem_mudanca_400(client):
    # estoque 20 ; peso para 20 unidades = 40 + 20*3.2 = 104 -> sem mudança
    pid = _produto(client)["id"]
    r = client.post("/operacao/confirmar", json={"produto_id": pid, "peso_g": "104"})
    assert r.status_code == 400


def test_confirmar_produto_inexistente_404(client):
    r = client.post("/operacao/confirmar", json={"produto_id": 999, "peso_g": "120"})
    assert r.status_code == 404
