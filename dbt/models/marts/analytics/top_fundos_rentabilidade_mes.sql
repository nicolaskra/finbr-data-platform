{{
  config(
    materialized='table',
    tags=['mart', 'analytics']
  )
}}

-- Ranking analitico: top 50 classes de fundo por rentabilidade mensal,
-- filtrando classes com PL minimo (R$ 1 milhao) e numero minimo
-- de dias uteis (15) para evitar fundos novos ou ilíquidos.

with rent as (
    select * from {{ ref('fct_fundo_rentabilidade_mensal') }}
    where dias_uteis >= 15
      and vl_patrim_liq_fim_mes >= 1000000  -- R$ 1M minimo
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
