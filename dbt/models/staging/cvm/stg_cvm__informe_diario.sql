{{
  config(
    materialized='view',
    tags=['staging', 'cvm']
  )
}}

with raw as (
    -- Le parquet glob direto do data lake via DuckDB read_parquet.
    -- Documentacao do schema em _cvm__sources.yml.
    select * from {{ read_raw_parquet('cvm/inf_diario/*/inf_diario.parquet') }}
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
),

filtered as (
    select *
    from renamed
    -- Filtra linhas obviamente invalidas que apareceriam em qualquer profiling
    where cnpj_classe is not null
      and data_competencia is not null
      and vl_quota is not null
      and vl_quota > 0
)

select * from filtered
