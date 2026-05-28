"""Tests endpoint /analytics/top-fundos."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_top_fundos_abr_2026(client: TestClient):
    resp = client.get("/analytics/top-fundos", params={"mes": "2026-04-01"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["fundos"]) == 2
    # Rank 1 deve ter rentab maior
    assert body["fundos"][0]["ranking_mes"] == 1
    assert body["fundos"][0]["rentabilidade_mes_pct"] == 3.0


def test_top_fundos_respeita_limit(client: TestClient):
    resp = client.get(
        "/analytics/top-fundos",
        params={"mes": "2026-04-01", "limit": 1},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_top_fundos_mes_sem_dados_retorna_404(client: TestClient):
    resp = client.get("/analytics/top-fundos", params={"mes": "2020-01-01"})
    assert resp.status_code == 404


def test_top_fundos_limit_invalido_retorna_422(client: TestClient):
    resp = client.get(
        "/analytics/top-fundos",
        params={"mes": "2026-04-01", "limit": 999},
    )
    assert resp.status_code == 422  # Pydantic validation: le=50


def test_top_fundos_mes_invalido_retorna_422(client: TestClient):
    resp = client.get("/analytics/top-fundos", params={"mes": "not-a-date"})
    assert resp.status_code == 422
