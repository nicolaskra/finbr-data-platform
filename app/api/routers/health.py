"""Endpoint /health — smoke test do warehouse."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.api.db import get_connection
from app.api.schemas import HealthResponse
from app.api.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Smoke test")
def health() -> HealthResponse:
    """Valida que o warehouse esta acessivel e popula counts basicos."""
    path = Path(settings.duckdb_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Warehouse nao encontrado em {path}",
        )

    size_mb = round(path.stat().st_size / (1024 * 1024), 2)

    with get_connection() as con:
        rows_staging = con.execute(
            "select count(*) from main_staging.stg_cvm__informe_diario"
        ).fetchone()[0]
        rows_dim = con.execute(
            "select count(*) from main_core.dim_fundo_classe"
        ).fetchone()[0]
        rows_fct = con.execute(
            "select count(*) from main_core.fct_fundo_rentabilidade_mensal"
        ).fetchone()[0]

    return HealthResponse(
        status="ok",
        warehouse_path=str(path),
        warehouse_size_mb=size_mb,
        rows_staging=rows_staging,
        rows_dim=rows_dim,
        rows_fct=rows_fct,
    )
