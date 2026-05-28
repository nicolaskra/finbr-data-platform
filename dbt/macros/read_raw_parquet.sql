{# Macro para ler parquet glob particionado do data lake.
   Encapsula sintaxe DuckDB e tira boilerplate dos staging models.

   Uso:
       select * from {{ read_raw_parquet('cvm/inf_diario/*/inf_diario.parquet') }}

   var('raw_path') vem de dbt_project.yml (default: /opt/airflow/data/raw)
#}
{% macro read_raw_parquet(relative_glob) %}
    read_parquet('{{ var("raw_path") }}/{{ relative_glob }}')
{% endmacro %}
