"""Fixtures compartilhadas dos tests da API.

Estrategia: cria um DuckDB temporario com schema espelhando o warehouse real
(staging + core + analytics), popula com dados sinteticos minimos,
e injeta via env var FINBR_DUCKDB_PATH antes do app subir.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def warehouse_duckdb(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Cria warehouse DuckDB sintetico minimo (1 fundo, 3 meses)."""
    db_path = tmp_path_factory.mktemp("warehouse") / "finbr.duckdb"
    con = duckdb.connect(str(db_path))

    # Schemas
    con.execute("create schema if not exists main_staging")
    con.execute("create schema if not exists main_core")
    con.execute("create schema if not exists main_analytics")

    # Staging (subset minimo de colunas — health endpoint so faz count)
    con.execute(
        """
        create table main_staging.stg_cvm__informe_diario as
        select * from (values
            ('CLASSES - FIF', '00.000.001/0001-01', NULL, DATE '2026-04-01', 100.0),
            ('CLASSES - FIF', '00.000.001/0001-01', NULL, DATE '2026-04-02', 101.0),
            ('CLASSES - FIF', '00.000.001/0001-01', NULL, DATE '2026-04-03', 102.0)
        ) as t(tipo_classe, cnpj_classe, id_subclasse, data_competencia, vl_quota)
        """
    )

    # Dim
    con.execute(
        """
        create table main_core.dim_fundo_classe as
        select * from (values
            ('sk_001', '00.000.001/0001-01', '__sem_subclasse__',
             'CLASSES - FIF', DATE '2026-01-01', DATE '2026-04-30',
             1000000.0, 10),
            ('sk_002', '00.000.002/0001-02', '__sem_subclasse__',
             'CLASSES - FIF', DATE '2026-01-01', DATE '2026-04-30',
             2000000.0, 20)
        ) as d(sk_fundo_classe, cnpj_classe, id_subclasse, tipo_classe,
               primeira_data_observada, ultima_data_observada,
               vl_patrim_liq_atual, nr_cotistas_atual)
        """
    )

    # Fct — 3 meses para 2 fundos
    con.execute(
        """
        create table main_core.fct_fundo_rentabilidade_mensal as
        select * from (values
            ('rk_001_202602', 'sk_001', '00.000.001/0001-01', '__sem_subclasse__',
             'CLASSES - FIF', DATE '2026-02-01', 20, 0.012, 1010000.0, 10),
            ('rk_001_202603', 'sk_001', '00.000.001/0001-01', '__sem_subclasse__',
             'CLASSES - FIF', DATE '2026-03-01', 20, 0.015, 1025000.0, 10),
            ('rk_001_202604', 'sk_001', '00.000.001/0001-01', '__sem_subclasse__',
             'CLASSES - FIF', DATE '2026-04-01', 20, 0.020, 1045000.0, 10),
            ('rk_002_202604', 'sk_002', '00.000.002/0001-02', '__sem_subclasse__',
             'CLASSES - FIF', DATE '2026-04-01', 20, 0.030, 2060000.0, 20)
        ) as f(sk_rentabilidade, sk_fundo_classe, cnpj_classe, id_subclasse,
               tipo_classe, mes, dias_uteis, rentabilidade_mes,
               vl_patrim_liq_fim_mes, nr_cotistas_fim_mes)
        """
    )

    # Analytics — top fundos abr/2026
    con.execute(
        """
        create table main_analytics.top_fundos_rentabilidade_mes as
        select * from (values
            (DATE '2026-04-01', 1, '00.000.002/0001-02', '__sem_subclasse__',
             'CLASSES - FIF', 20, 0.030, 3.0, 2060000.0, 20),
            (DATE '2026-04-01', 2, '00.000.001/0001-01', '__sem_subclasse__',
             'CLASSES - FIF', 20, 0.020, 2.0, 1045000.0, 10)
        ) as a(mes, ranking_mes, cnpj_classe, id_subclasse, tipo_classe,
               dias_uteis, rentabilidade_mes, rentabilidade_mes_pct,
               vl_patrim_liq_fim_mes, nr_cotistas_fim_mes)
        """
    )

    con.close()
    return db_path


@pytest.fixture
def client(warehouse_duckdb: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient com env var apontando pro warehouse sintetico."""
    monkeypatch.setenv("FINBR_DUCKDB_PATH", str(warehouse_duckdb))

    # Reimport settings + app pra recarregar env var
    import importlib

    from app.api import settings as settings_mod

    importlib.reload(settings_mod)
    from app.api import main as main_mod

    importlib.reload(main_mod)

    return TestClient(main_mod.app)
