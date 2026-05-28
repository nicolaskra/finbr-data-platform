"""Settings carregadas via env vars (12-factor)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    duckdb_path: str = os.getenv("FINBR_DUCKDB_PATH", "/opt/finbr/data/warehouse/finbr.duckdb")
    api_title: str = "finbr API"
    api_version: str = "0.1.0"
    api_description: str = (
        "REST API para servir o warehouse DuckDB do finbr-data-platform "
        "(rentabilidade de fundos CVM, ranking analitico)."
    )
    cors_origins: tuple[str, ...] = tuple(
        o.strip() for o in os.getenv("FINBR_CORS_ORIGINS", "*").split(",")
    )


settings = Settings()
