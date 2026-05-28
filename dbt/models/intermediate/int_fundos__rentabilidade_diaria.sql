{{
  config(
    materialized='view',
    tags=['intermediate', 'cvm']
  )
}}

-- Calcula rentabilidade diaria da quota por (cnpj_classe, id_subclasse).
-- Usa LAG sobre janela ordenada por data para pegar a cota do dia anterior.
-- Rentabilidade = (vl_quota_hoje / vl_quota_ontem) - 1

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
    from {{ ref('stg_cvm__informe_diario') }}
),

with_lag as (
    select
        *,
        lag(vl_quota) over (
            partition by cnpj_classe, id_subclasse
            order by data_competencia
        ) as vl_quota_anterior
    from base
)

select
    cnpj_classe,
    id_subclasse,
    tipo_classe,
    data_competencia,
    vl_quota,
    vl_quota_anterior,
    case
        when vl_quota_anterior is null then null  -- 1o dia da serie
        when vl_quota_anterior = 0 then null
        else (vl_quota / vl_quota_anterior) - 1
    end as rentabilidade_dia,
    vl_patrim_liq,
    nr_cotistas,
    captacao_dia,
    resgate_dia
from with_lag
