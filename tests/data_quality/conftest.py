"""
Fixtures para data quality tests.

Conecta ao warehouse DuckDB REAL (data/warehouse/finbr.duckdb).
Esses tests SO rodam se o warehouse existir — em CI sao SKIPPED.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

WAREHOUSE_PATH = Path(
    os.getenv(
        "FINBR_DUCKDB_PATH",
        "data/warehouse/finbr.duckdb",
    )
).resolve()


@pytest.fixture(scope="session")
def duckdb_con():
    """Conexao read-only ao warehouse real."""
    import duckdb

    if not WAREHOUSE_PATH.exists():
        pytest.skip(
            f"Warehouse nao encontrado em {WAREHOUSE_PATH}. "
            "Esse teste so roda apos rodar o pipeline (Airflow + dbt)."
        )
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    yield con
    con.close()
