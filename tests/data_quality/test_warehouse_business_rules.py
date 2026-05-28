"""
Data quality tests — regras de negocio sobre o warehouse REAL.

Diferente de tests/dags/ (unitario com mocks) e tests/api/ (TestClient
com fixture), estes tests rodam contra o DuckDB real produzido pelo
pipeline. Sao SKIPPED se o warehouse nao existir.

Cobrem:
- Volumes minimos esperados
- Ranges plausiveis (vl_quota > 0, dias_uteis razoavel)
- Integridade referencial (fct -> dim sem orfaos)
- Idempotencia (re-rodar nao duplica)
- Distribuicao de outliers (max 1% de fundos com rentab > 100%)
"""

from __future__ import annotations

# ----------------------------------------------------------------------
# Volumes
# ----------------------------------------------------------------------


class TestVolumes:
    def test_staging_tem_dados(self, duckdb_con):
        n = duckdb_con.execute(
            "select count(*) from main_staging.stg_cvm__informe_diario"
        ).fetchone()[0]
        assert n > 100_000, f"Staging com apenas {n} linhas (esperado >100k)"

    def test_dim_tem_fundos(self, duckdb_con):
        n = duckdb_con.execute("select count(*) from main_core.dim_fundo_classe").fetchone()[0]
        assert n > 1_000, f"Dim com apenas {n} fundos (esperado >1k)"

    def test_fct_proporcional_a_dim(self, duckdb_con):
        """fct deve ter pelo menos 50% do tamanho do dim (cada fundo >= 1 mes)."""
        dim_n = duckdb_con.execute("select count(*) from main_core.dim_fundo_classe").fetchone()[0]
        fct_n = duckdb_con.execute(
            "select count(*) from main_core.fct_fundo_rentabilidade_mensal"
        ).fetchone()[0]
        ratio = fct_n / dim_n
        assert 0.5 <= ratio <= 12.0, (
            f"Proporcao fct/dim = {ratio:.2f} fora do range esperado [0.5, 12.0]"
        )


# ----------------------------------------------------------------------
# Ranges de valores
# ----------------------------------------------------------------------


class TestRanges:
    def test_vl_quota_sempre_positivo(self, duckdb_con):
        n_invalid = duckdb_con.execute(
            "select count(*) from main_staging.stg_cvm__informe_diario where vl_quota <= 0"
        ).fetchone()[0]
        assert n_invalid == 0, f"{n_invalid} linhas com vl_quota <= 0"

    def test_vl_patrim_liq_negativo_dentro_do_esperado(self, duckdb_con):
        """
        PL negativo existe na realidade (fundos em liquidacao, alavancados).
        Achado documentado em docs/data_quality_findings.md (item #1).
        Regra: max 0.1% das linhas com PL < 0, e nenhum < -R$ 1 milhao.
        """
        total = duckdb_con.execute(
            "select count(*) from main_staging.stg_cvm__informe_diario"
        ).fetchone()[0]
        negativos = duckdb_con.execute(
            "select count(*) from main_staging.stg_cvm__informe_diario where vl_patrim_liq < 0"
        ).fetchone()[0]
        pct = negativos / total
        assert pct < 0.001, f"{pct * 100:.3f}% das linhas com PL negativo (limite 0.1%)"

        # PL muito negativo (< -R$ 1M) e suspeito de bug, nao realidade
        muito_negativo = duckdb_con.execute(
            "select count(*) from main_staging.stg_cvm__informe_diario "
            "where vl_patrim_liq < -1_000_000"
        ).fetchone()[0]
        assert muito_negativo == 0, (
            f"{muito_negativo} fundos com PL < -R$ 1M (provavel bug de import)"
        )

    def test_nr_cotistas_nao_negativo(self, duckdb_con):
        n_invalid = duckdb_con.execute(
            "select count(*) from main_staging.stg_cvm__informe_diario where nr_cotistas < 0"
        ).fetchone()[0]
        assert n_invalid == 0

    def test_dias_uteis_razoaveis(self, duckdb_con):
        """Nenhum mes deve ter > 25 dias uteis (impossivel)."""
        max_dias = duckdb_con.execute(
            "select max(dias_uteis) from main_core.fct_fundo_rentabilidade_mensal"
        ).fetchone()[0]
        assert max_dias <= 25, f"Mes com {max_dias} dias uteis (impossivel)"


# ----------------------------------------------------------------------
# Integridade referencial
# ----------------------------------------------------------------------


class TestIntegridade:
    def test_fct_nao_tem_orfaos(self, duckdb_con):
        """Todo fct.sk_fundo_classe deve existir em dim."""
        orfaos = duckdb_con.execute(
            """
            select count(*)
            from main_core.fct_fundo_rentabilidade_mensal f
            left join main_core.dim_fundo_classe d
              on f.sk_fundo_classe = d.sk_fundo_classe
            where d.sk_fundo_classe is null
            """
        ).fetchone()[0]
        assert orfaos == 0, f"{orfaos} fatos sem dim correspondente"

    def test_dim_sem_duplicatas(self, duckdb_con):
        total = duckdb_con.execute("select count(*) from main_core.dim_fundo_classe").fetchone()[0]
        unicos = duckdb_con.execute(
            "select count(distinct sk_fundo_classe) from main_core.dim_fundo_classe"
        ).fetchone()[0]
        assert total == unicos, f"Dim com {total - unicos} duplicatas"

    def test_top_fundos_so_de_meses_existentes(self, duckdb_con):
        """top_fundos so deve listar fundos que estao no fct."""
        invalido = duckdb_con.execute(
            """
            select count(*) from main_analytics.top_fundos_rentabilidade_mes t
            where not exists (
                select 1 from main_core.fct_fundo_rentabilidade_mensal f
                where f.cnpj_classe = t.cnpj_classe and f.mes = t.mes
            )
            """
        ).fetchone()[0]
        assert invalido == 0


# ----------------------------------------------------------------------
# Distribuicao / outliers
# ----------------------------------------------------------------------


class TestDistribuicao:
    def test_max_1pct_fundos_com_rentab_acima_100pct(self, duckdb_con):
        """
        Fundos com rentab > 100% no mes existem (provados na sessao 1)
        mas devem ser <= 1% do total. Se mais, schema mudou ou bug no calculo.
        """
        total = duckdb_con.execute(
            "select count(*) from main_core.fct_fundo_rentabilidade_mensal"
        ).fetchone()[0]
        outliers = duckdb_con.execute(
            "select count(*) from main_core.fct_fundo_rentabilidade_mensal "
            "where rentabilidade_mes > 1.0"  # > 100%
        ).fetchone()[0]
        pct = outliers / total
        assert pct <= 0.01, (
            f"{pct * 100:.2f}% dos fundos com rentab > 100% (limite: 1%). "
            f"Verificar bug no calculo composto."
        )

    def test_top_fundos_tem_max_50_por_mes(self, duckdb_con):
        max_por_mes = duckdb_con.execute(
            """
            select max(c) from (
                select mes, count(*) as c
                from main_analytics.top_fundos_rentabilidade_mes
                group by mes
            )
            """
        ).fetchone()[0]
        assert max_por_mes <= 50, f"Mes com {max_por_mes} top fundos (deveria ser 50)"

    def test_top_fundos_pl_filtro_aplicado(self, duckdb_con):
        """Filtro de PL >= R$ 1M deve estar aplicado no analytics."""
        n_violacao = duckdb_con.execute(
            "select count(*) from main_analytics.top_fundos_rentabilidade_mes "
            "where vl_patrim_liq_fim_mes < 1_000_000"
        ).fetchone()[0]
        assert n_violacao == 0, (
            f"{n_violacao} fundos no top com PL < R$ 1M (filtro de qualidade quebrou)"
        )


# ----------------------------------------------------------------------
# Smoke test: query exemplo deve funcionar
# ----------------------------------------------------------------------


def test_query_top10_executa(duckdb_con):
    """Smoke test: query principal do dashboard nao quebra."""
    df = duckdb_con.execute(
        """
        select mes, ranking_mes, cnpj_classe, rentabilidade_mes_pct
        from main_analytics.top_fundos_rentabilidade_mes
        order by mes desc, ranking_mes
        limit 10
        """
    ).df()
    assert len(df) >= 1
    assert "rentabilidade_mes_pct" in df.columns
