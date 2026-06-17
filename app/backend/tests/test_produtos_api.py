def _payload(**over):
    p = {
        "nome": "Parafuso M6",
        "rfid_tag_id": "A1B2C3D4",
        "peso_unitario_g": "3.2",
        "tara_caixa_g": "40",
        "preco_unitario": "0.15",
        "estoque_disponivel": 25,
    }
    p.update(over)
    return p


def test_criar_e_listar(client):
    r = client.post("/produtos", json=_payload())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] > 0
    assert body["peso_total_g"] == "120.000"

    r = client.get("/produtos")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_tag_duplicada_da_conflito(client):
    assert client.post("/produtos", json=_payload()).status_code == 201
    r = client.post("/produtos", json=_payload(nome="Outro"))
    assert r.status_code == 409


def test_get_update_delete(client):
    pid = client.post("/produtos", json=_payload()).json()["id"]

    r = client.get(f"/produtos/{pid}")
    assert r.status_code == 200

    r = client.put(f"/produtos/{pid}", json={"nome": "Parafuso M8"})
    assert r.status_code == 200
    assert r.json()["nome"] == "Parafuso M8"

    assert client.delete(f"/produtos/{pid}").status_code == 204
    assert client.get(f"/produtos/{pid}").status_code == 404


def test_get_inexistente_404(client):
    assert client.get("/produtos/999").status_code == 404
