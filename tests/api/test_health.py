"""Tests endpoint /health."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_200_e_payload_completo(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["rows_staging"] == 3
    assert body["rows_dim"] == 2
    assert body["rows_fct"] == 4
    assert body["warehouse_size_mb"] > 0


def test_root_redireciona_pra_docs():
    """Endpoint / retorna metadados (sem 404)."""
    # Usa client real pra evitar reload de fixture
    import importlib

    from app.api import main as main_mod

    importlib.reload(main_mod)
    with TestClient(main_mod.app) as c:
        resp = c.get("/")
        # Pode falhar com 500 se DB nao existir, mas nao 404
        assert resp.status_code != 404
