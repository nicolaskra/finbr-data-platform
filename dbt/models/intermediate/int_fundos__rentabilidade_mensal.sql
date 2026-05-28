{{
  config(
    materialized='view',
    tags=['intermediate', 'cvm']
  )
}}

-- Rentabilidade mensal = produto composto (1+r_diaria) - 1
-- DuckDB nao tem PRODUCT, entao usamos EXP(SUM(LN(...))).

with diario as (
    select
        cnpj_classe,
        id_subclasse,
        tipo_classe,
        data_competencia,
        rentabilidade_dia,
        vl_patrim_liq,
        nr_cotistas
    from {{ ref('int_fundos__rentabilidade_diaria') }}
    where rentabilidade_dia is not null
),

mensal as (
    select
        cnpj_classe,
        id_subclasse,
        any_value(tipo_classe) as tipo_classe,
        date_trunc('month', data_competencia)::date as mes,
        count(*) as dias_uteis,

        -- Produto composto: EXP(SUM(LN(1+r))) - 1
        exp(sum(ln(1 + rentabilidade_dia))) - 1 as rentabilidade_mes,

        -- Patrimonio: ultimo dia do mes
        max_by(vl_patrim_liq, data_competencia) as vl_patrim_liq_fim_mes,
        max_by(nr_cotistas, data_competencia) as nr_cotistas_fim_mes
    from diario
    group by cnpj_classe, id_subclasse, date_trunc('month', data_competencia)
)

select * from mensal
