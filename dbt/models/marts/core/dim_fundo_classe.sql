{{
  config(
    materialized='table',
    tags=['mart', 'dim']
  )
}}

-- Dimensao de classes de fundo (1 linha por chave natural).
-- Atributos derivados do snapshot mais recente disponivel.

with base as (
    select
        cnpj_classe,
        coalesce(id_subclasse, '__sem_subclasse__') as id_subclasse,
        tipo_classe,
        data_competencia,
        vl_patrim_liq,
        nr_cotistas
    from {{ ref('stg_cvm__informe_diario') }}
),

mais_recente as (
    select
        cnpj_classe,
        id_subclasse,
        any_value(tipo_classe) as tipo_classe,
        max(data_competencia) as ultima_data_observada,
        max_by(vl_patrim_liq, data_competencia) as vl_patrim_liq_atual,
        max_by(nr_cotistas, data_competencia) as nr_cotistas_atual,
        min(data_competencia) as primeira_data_observada
    from base
    group by cnpj_classe, id_subclasse
)

select
    -- Surrogate key (estavel por cnpj+subclasse)
    {{ dbt_utils.generate_surrogate_key(['cnpj_classe', 'id_subclasse']) }} as sk_fundo_classe,
    cnpj_classe,
    id_subclasse,
    tipo_classe,
    primeira_data_observada,
    ultima_data_observada,
    vl_patrim_liq_atual,
    nr_cotistas_atual
from mais_recente
