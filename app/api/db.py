"""Conexao DuckDB read-only — segura para multi-reader."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb

from app.api.settings import settings


def _validate_path() -> Path:
    path = Path(settings.duckdb_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Warehouse DuckDB nao encontrado em {path}. "
            f"Rode o pipeline (Airflow: ingest + dbt) antes da API."
        )
    return path


@contextmanager
def get_connection() -> Iterator[duckdb.DuckDBPyConnection]:
    """
    Conexao read-only ao warehouse.
    DuckDB suporta multiplos readers concorrentes em modo read_only.
    """
    path = _validate_path()
    con = duckdb.connect(str(path), read_only=True)
    try:
        yield con
    finally:
        con.close()
