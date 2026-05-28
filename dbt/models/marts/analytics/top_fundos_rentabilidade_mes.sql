{{
  config(
    materialized='table',
    tags=['mart', 'analytics']
  )
}}

-- Ranking analitico: top 50 classes de fundo por rentabilidade mensal,
-- filtrando classes com PL minimo (R$ 1 milhao), numero minimo de dias
-- uteis (15) e pulverizacao minima (>= 5 cotistas) para evitar fundos
-- novos, ilíquidos ou com NAV inicial distorcido por baixa pulverizacao
-- (vide finding #3 em docs/data_quality_findings.md).

with rent as (
    select * from {{ ref('fct_fundo_rentabilidade_mensal') }}
    where dias_uteis >= 15
      and vl_patrim_liq_fim_mes >= 1000000  -- R$ 1M minimo
      and nr_cotistas_fim_mes >= 5          -- pulverizacao minima (finding #3)
),

ranked as (
    select
        *,
        row_number() over (
            partition by mes
            order by rentabilidade_mes desc
        ) as ranking_mes
    from rent
)

select
    mes,
    ranking_mes,
    cnpj_classe,
    id_subclasse,
    tipo_classe,
    dias_uteis,
    rentabilidade_mes,
    rentabilidade_mes * 100 as rentabilidade_mes_pct,
    vl_patrim_liq_fim_mes,
    nr_cotistas_fim_mes
from ranked
where ranking_mes <= 50
order by mes desc, ranking_mes
