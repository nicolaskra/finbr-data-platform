"""Tests endpoint /fundos/{cnpj}/rentabilidade."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_serie_historica_retorna_3_meses(client: TestClient):
    resp = client.get("/fundos/rentabilidade", params={"cnpj": "00.000.001/0001-01"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["cnpj_classe"] == "00.000.001/0001-01"
    assert body["tipo_classe"] == "CLASSES - FIF"
    assert len(body["serie"]) == 3
    # Rentabilidade do 1o mes (fev) = 1.2%
    assert body["serie"][0]["rentabilidade_mes_pct"] == 1.2


def test_serie_ordenada_por_mes(client: TestClient):
    resp = client.get("/fundos/rentabilidade", params={"cnpj": "00.000.001/0001-01"})
    serie = resp.json()["serie"]
    meses = [item["mes"] for item in serie]
    assert meses == sorted(meses)


def test_cnpj_inexistente_retorna_404(client: TestClient):
    resp = client.get("/fundos/rentabilidade", params={"cnpj": "99.999.999/0001-99"})
    assert resp.status_code == 404
    assert "nao encontrada" in resp.json()["detail"].lower()
