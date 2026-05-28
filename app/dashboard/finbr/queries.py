"""Queries DuckDB usadas pelas paginas do dashboard.

Toda funcao recebe `con` (conexao DuckDB) ja aberta read-only. Retornam pandas
DataFrames com colunas no padrao Python (snake_case) e tipos nativos — quem
formata para apresentacao e a camada de UI (paginas/widgets).

Schemas reais do warehouse:
- main_core.fct_fundo_rentabilidade_mensal
- main_core.dim_fundo_classe
- main_analytics.top_fundos_rentabilidade_mes
"""

from __future__ import annotations

import pandas as pd


def listar_meses(con) -> list[str]:
    """Retorna meses distintos do fct (string YYYY-MM-DD), ordenados desc."""
    df = con.execute(
        "select distinct mes from main_core.fct_fundo_rentabilidade_mensal order by mes desc"
    ).df()
    return [str(m) for m in df["mes"]]


def overview_kpis(con, mes: str, cdi_mes_pct: float) -> dict:
    """KPIs agregados do mes:
    - total_fundos: numero de classes com obs no mes
    - pl_total: soma do PL fim mes (R$)
    - pct_acima_cdi: % de fundos com rentab >= cdi do mes
    - mediana_rentab_pct: mediana da rentab do mes (%)
    """
    row = con.execute(
        """
        with base as (
            select
                rentabilidade_mes * 100 as rentab_pct,
                vl_patrim_liq_fim_mes
            from main_core.fct_fundo_rentabilidade_mensal
            where mes = ?
              and vl_patrim_liq_fim_mes > 0
              and dias_uteis >= 15
        )
        select
            count(*)                                                  as total_fundos,
            sum(vl_patrim_liq_fim_mes)                                as pl_total,
            median(rentab_pct)                                        as mediana_rentab_pct,
            avg(case when rentab_pct >= ? then 1.0 else 0.0 end)*100  as pct_acima_cdi
        from base
        """,
        [mes, cdi_mes_pct],
    ).fetchone()

    return {
        "total_fundos": int(row[0] or 0),
        "pl_total": float(row[1] or 0.0),
        "mediana_rentab_pct": float(row[2] or 0.0),
        "pct_acima_cdi": float(row[3] or 0.0),
    }


def distribuicao_rentab(
    con, mes: str, *, p_min: float = -10.0, p_max: float = 10.0
) -> pd.DataFrame:
    """Distribuicao da rentabilidade mensal dos fundos no mes, em %.
    Filtra fundos com PL > 0 e dias_uteis >= 15. Trunca em +-10pp pra remover
    outliers do histograma (mantemos a info no KPI 'extremos' separadamente).
    """
    return con.execute(
        """
        select rentabilidade_mes * 100 as rentab_pct
        from main_core.fct_fundo_rentabilidade_mensal
        where mes = ?
          and vl_patrim_liq_fim_mes > 0
          and dias_uteis >= 15
          and rentabilidade_mes * 100 between ? and ?
        """,
        [mes, p_min, p_max],
    ).df()


def top_fundos(con, mes: str, limit: int = 20) -> pd.DataFrame:
    """Top N por rentabilidade no mes (ja com filtros do mart aplicados)."""
    return con.execute(
        """
        select
            ranking_mes        as ranking,
            cnpj_classe        as cnpj,
            tipo_classe        as tipo,
            rentabilidade_mes_pct as rentab_pct,
            dias_uteis,
            vl_patrim_liq_fim_mes as pl,
            nr_cotistas_fim_mes   as cotistas
        from main_analytics.top_fundos_rentabilidade_mes
        where mes = ?
        order by ranking_mes
        limit ?
        """,
        [mes, limit],
    ).df()


def serie_historica(con, cnpj: str) -> pd.DataFrame:
    """Serie temporal de um fundo: mes, rentab_pct, pl, cotistas, dias_uteis."""
    df = con.execute(
        """
        select
            mes,
            rentabilidade_mes * 100 as rentab_pct,
            vl_patrim_liq_fim_mes as pl,
            nr_cotistas_fim_mes as cotistas,
            dias_uteis,
            id_subclasse,
            tipo_classe
        from main_core.fct_fundo_rentabilidade_mensal
        where cnpj_classe = ?
        order by mes
        """,
        [cnpj],
    ).df()
    if df.empty:
        return df
    # se ha multiplas subclasses pro mesmo cnpj, fica com a primeira
    primeira = df["id_subclasse"].iloc[0]
    return df[df["id_subclasse"] == primeira].reset_index(drop=True)


def pesquisar_cnpjs(con, mes: str, prefixo: str | None = None, limit: int = 50) -> list[str]:
    """Lista CNPJs com observacao no mes — util para selectbox de busca."""
    sql = "select distinct cnpj_classe from main_core.fct_fundo_rentabilidade_mensal where mes = ?"
    params: list = [mes]
    if prefixo:
        sql += " and cnpj_classe like ?"
        params.append(f"{prefixo}%")
    sql += " order by cnpj_classe limit ?"
    params.append(limit)
    df = con.execute(sql, params).df()
    return [str(c) for c in df["cnpj_classe"]]


def health(con, warehouse_path: str, warehouse_size_mb: float) -> dict:
    """Status do warehouse — exibido na sidebar."""
    rows_fct = con.execute(
        "select count(*) from main_core.fct_fundo_rentabilidade_mensal"
    ).fetchone()[0]
    rows_dim = con.execute("select count(*) from main_core.dim_fundo_classe").fetchone()[0]
    meses = listar_meses(con)
    return {
        "rows_fct": int(rows_fct),
        "rows_dim": int(rows_dim),
        "warehouse_path": warehouse_path,
        "warehouse_size_mb": warehouse_size_mb,
        "meses_count": len(meses),
        "mes_mais_recente": meses[0] if meses else None,
    }
