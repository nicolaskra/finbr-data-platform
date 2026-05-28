{{
  config(
    materialized='table',
    tags=['mart', 'fact']
  )
}}

-- Fato de rentabilidade mensal por classe de fundo.
-- Grain: 1 linha por (classe de fundo, mes).

with rent as (
    select * from {{ ref('int_fundos__rentabilidade_mensal') }}
),

dim as (
    select sk_fundo_classe, cnpj_classe, id_subclasse
    from {{ ref('dim_fundo_classe') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['rent.cnpj_classe', 'rent.id_subclasse', 'rent.mes']) }} as sk_rentabilidade,
    dim.sk_fundo_classe,
    rent.cnpj_classe,
    rent.id_subclasse,
    rent.tipo_classe,
    rent.mes,
    rent.dias_uteis,
    rent.rentabilidade_mes,
    rent.vl_patrim_liq_fim_mes,
    rent.nr_cotistas_fim_mes
from rent
inner join dim
  on rent.cnpj_classe = dim.cnpj_classe
 and rent.id_subclasse = dim.id_subclasse
