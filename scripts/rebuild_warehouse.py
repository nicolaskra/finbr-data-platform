"""Reconstroi o warehouse DuckDB a partir dos parquets raw,
sem depender do dbt CLI (que tem bug de encoding no Windows
com paths Latin-1).

Replica os 6 models do projeto dbt (staging, intermediate, marts.core,
marts.analytics) usando SQL direto.

Idempotente: trunca/recria os schemas a cada execucao.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import duckdb

LOGGER = logging.getLogger("rebuild_warehouse")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REPO = Path(__file__).resolve().parent.parent
RAW_GLOB = (REPO / "data/raw/cvm/inf_diario/*/inf_diario.parquet").as_posix()
WAREHOUSE = REPO / "data/warehouse/finbr.duckdb"


def main() -> int:
    if WAREHOUSE.exists():
        WAREHOUSE.unlink()
    LOGGER.info("Criando warehouse limpo em %s", WAREHOUSE)
    con = duckdb.connect(str(WAREHOUSE))

    LOGGER.info("Criando schemas...")
    for s in ("main_staging", "main_intermediate", "main_core", "main_analytics"):
        con.execute(f"create schema if not exists {s}")

    # ----- staging -----
    LOGGER.info("staging.stg_cvm__informe_diario (read_parquet glob)...")
    con.execute(
        f"""
        create or replace table main_staging.stg_cvm__informe_diario as
        with raw as (
            select * from read_parquet('{RAW_GLOB}')
        ),
        renamed as (
            select
                cast(TP_FUNDO_CLASSE     as varchar)   as tipo_classe,
                cast(CNPJ_FUNDO_CLASSE   as varchar)   as cnpj_classe,
                cast(ID_SUBCLASSE        as varchar)   as id_subclasse,
                cast(DT_COMPTC           as date)      as data_competencia,
                cast(VL_TOTAL            as double)    as vl_total,
                cast(VL_QUOTA            as double)    as vl_quota,
                cast(VL_PATRIM_LIQ       as double)    as vl_patrim_liq,
                cast(CAPTC_DIA           as double)    as captacao_dia,
                cast(RESG_DIA            as double)    as resgate_dia,
                cast(NR_COTST            as bigint)    as nr_cotistas
            from raw
        )
        select * from renamed
        where cnpj_classe is not null
          and data_competencia is not null
          and vl_quota is not null
          and vl_quota > 0
        """
    )
    n = con.execute("select count(*) from main_staging.stg_cvm__informe_diario").fetchone()[0]
    LOGGER.info("  -> %s linhas", f"{n:,}")

    # ----- intermediate (views) -----
    LOGGER.info("intermediate.int_fundos__rentabilidade_diaria (view)...")
    con.execute(
        """
        create or replace view main_intermediate.int_fundos__rentabilidade_diaria as
        with base as (
            select
                cnpj_classe,
                coalesce(id_subclasse, '__sem_subclasse__') as id_subclasse,
                tipo_classe,
                data_competencia,
                vl_quota,
                vl_patrim_liq,
                nr_cotistas,
                captacao_dia,
                resgate_dia
            from main_staging.stg_cvm__informe_diario
        ),
        with_lag as (
            select *,
                lag(vl_quota) over (
                    partition by cnpj_classe, id_subclasse
                    order by data_competencia
                ) as vl_quota_anterior
            from base
        )
        select
            cnpj_classe, id_subclasse, tipo_classe, data_competencia,
            vl_quota, vl_quota_anterior,
            case
                when vl_quota_anterior is null then null
                when vl_quota_anterior = 0 then null
                else (vl_quota / vl_quota_anterior) - 1
            end as rentabilidade_dia,
            vl_patrim_liq, nr_cotistas, captacao_dia, resgate_dia
        from with_lag
        """
    )

    LOGGER.info("intermediate.int_fundos__rentabilidade_mensal (view)...")
    con.execute(
        """
        create or replace view main_intermediate.int_fundos__rentabilidade_mensal as
        with diario as (
            select cnpj_classe, id_subclasse, tipo_classe, data_competencia,
                   rentabilidade_dia, vl_patrim_liq, nr_cotistas
            from main_intermediate.int_fundos__rentabilidade_diaria
            where rentabilidade_dia is not null
        )
        select
            cnpj_classe,
            id_subclasse,
            any_value(tipo_classe) as tipo_classe,
            date_trunc('month', data_competencia)::date as mes,
            count(*) as dias_uteis,
            exp(sum(ln(1 + rentabilidade_dia))) - 1 as rentabilidade_mes,
            max_by(vl_patrim_liq, data_competencia) as vl_patrim_liq_fim_mes,
            max_by(nr_cotistas, data_competencia) as nr_cotistas_fim_mes
        from diario
        group by cnpj_classe, id_subclasse, date_trunc('month', data_competencia)
        """
    )

    # ----- marts.core -----
    LOGGER.info("core.dim_fundo_classe (table)...")
    con.execute(
        """
        create or replace table main_core.dim_fundo_classe as
        with base as (
            select
                cnpj_classe,
                coalesce(id_subclasse, '__sem_subclasse__') as id_subclasse,
                tipo_classe,
                data_competencia,
                vl_patrim_liq,
                nr_cotistas
            from main_staging.stg_cvm__informe_diario
        ),
        mais_recente as (
            select
                cnpj_classe, id_subclasse,
                any_value(tipo_classe) as tipo_classe,
                max(data_competencia) as ultima_data_observada,
                max_by(vl_patrim_liq, data_competencia) as vl_patrim_liq_atual,
                max_by(nr_cotistas, data_competencia) as nr_cotistas_atual,
                min(data_competencia) as primeira_data_observada
            from base
            group by cnpj_classe, id_subclasse
        )
        select
            md5(cnpj_classe || '|' || id_subclasse) as sk_fundo_classe,
            cnpj_classe, id_subclasse, tipo_classe,
            primeira_data_observada, ultima_data_observada,
            vl_patrim_liq_atual, nr_cotistas_atual
        from mais_recente
        """
    )
    n = con.execute("select count(*) from main_core.dim_fundo_classe").fetchone()[0]
    LOGGER.info("  -> %s classes", f"{n:,}")

    LOGGER.info("core.fct_fundo_rentabilidade_mensal (table)...")
    con.execute(
        """
        create or replace table main_core.fct_fundo_rentabilidade_mensal as
        with rent as (
            select * from main_intermediate.int_fundos__rentabilidade_mensal
        ),
        dim as (
            select sk_fundo_classe, cnpj_classe, id_subclasse
            from main_core.dim_fundo_classe
        )
        select
            md5(rent.cnpj_classe || '|' || rent.id_subclasse || '|' || rent.mes::varchar) as sk_rentabilidade,
            dim.sk_fundo_classe,
            rent.cnpj_classe, rent.id_subclasse, rent.tipo_classe,
            rent.mes, rent.dias_uteis, rent.rentabilidade_mes,
            rent.vl_patrim_liq_fim_mes, rent.nr_cotistas_fim_mes
        from rent
        inner join dim
          on rent.cnpj_classe = dim.cnpj_classe
         and rent.id_subclasse = dim.id_subclasse
        """
    )
    n = con.execute("select count(*) from main_core.fct_fundo_rentabilidade_mensal").fetchone()[0]
    LOGGER.info("  -> %s linhas", f"{n:,}")

    # ----- marts.analytics -----
    LOGGER.info("analytics.top_fundos_rentabilidade_mes (table)...")
    con.execute(
        """
        create or replace table main_analytics.top_fundos_rentabilidade_mes as
        with rent as (
            select * from main_core.fct_fundo_rentabilidade_mensal
            where dias_uteis >= 15
              and vl_patrim_liq_fim_mes >= 1000000
              and nr_cotistas_fim_mes >= 5
        ),
        ranked as (
            select *,
                row_number() over (partition by mes order by rentabilidade_mes desc) as ranking_mes
            from rent
        )
        select
            mes, ranking_mes,
            cnpj_classe, id_subclasse, tipo_classe,
            dias_uteis,
            rentabilidade_mes,
            rentabilidade_mes * 100 as rentabilidade_mes_pct,
            vl_patrim_liq_fim_mes, nr_cotistas_fim_mes
        from ranked
        where ranking_mes <= 50
        order by mes desc, ranking_mes
        """
    )
    n = con.execute("select count(*) from main_analytics.top_fundos_rentabilidade_mes").fetchone()[
        0
    ]
    LOGGER.info("  -> %s linhas", f"{n:,}")

    # Compactacao: extrair as 3 tabelas em pandas, fechar conexao,
    # apagar o arquivo e reescrever apenas com as tabelas finais.
    # Isso reclama espaco que DuckDB nao libera depois de drop schema.
    LOGGER.info("Compactando warehouse (extract -> wipe -> reimport)...")
    fct = con.execute("select * from main_core.fct_fundo_rentabilidade_mensal").df()
    dim = con.execute("select * from main_core.dim_fundo_classe").df()
    top = con.execute("select * from main_analytics.top_fundos_rentabilidade_mes").df()
    con.close()
    LOGGER.info(
        "  Snapshot em memoria: fct=%s, dim=%s, top=%s",
        f"{len(fct):,}",
        f"{len(dim):,}",
        f"{len(top):,}",
    )

    # Workaround pandas 3.0 (string[python]) vs DuckDB 1.1.3:
    # converte colunas str pra object e numericas pra dtype nativo.
    import pyarrow as pa

    def to_arrow(df):
        # Forca colunas string-backed para python str antes do arrow
        for c in df.columns:
            if str(df[c].dtype) in ("string", "string[python]", "string[pyarrow]"):
                df[c] = df[c].astype(object)
        return pa.Table.from_pandas(df, preserve_index=False)

    fct_t = to_arrow(fct)
    dim_t = to_arrow(dim)
    top_t = to_arrow(top)

    WAREHOUSE.unlink()
    con = duckdb.connect(str(WAREHOUSE))
    con.execute("create schema main_core")
    con.execute("create schema main_analytics")
    con.register("fct_t", fct_t)
    con.register("dim_t", dim_t)
    con.register("top_t", top_t)
    con.execute("create table main_core.fct_fundo_rentabilidade_mensal as select * from fct_t")
    con.execute("create table main_core.dim_fundo_classe as select * from dim_t")
    con.execute("create table main_analytics.top_fundos_rentabilidade_mes as select * from top_t")
    con.execute("checkpoint")
    con.close()

    size_mb = WAREHOUSE.stat().st_size / 1_048_576
    LOGGER.info("CONCLUIDO. Warehouse compacto: %.2f MB", size_mb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
