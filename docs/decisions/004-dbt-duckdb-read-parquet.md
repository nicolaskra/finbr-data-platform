# ADR 004 — Read parquet via macro custom (no source.external)

**Data:** 2026-05-27
**Status:** Aceito (sessão 2)
**Reverter quando:** dbt-duckdb melhorar suporte nativo a `source.external_location`

## Contexto

Para ler Parquet glob do data lake (`data/raw/cvm/inf_diario/YYYY-MM/inf_diario.parquet`)
dentro do dbt, duas abordagens:

| Abordagem | Vantagens | Desvantagens |
|---|---|---|
| `{{ source(...) }}` + `external.location` | Lineage no docs, padrão dbt | Sintaxe dbt-duckdb instável; quebrou no 1.9 |
| Macro custom `read_raw_parquet()` | Funciona 100%, controle total | Sem lineage automático no `dbt docs` |

## Decisão

Usar macro `{{ read_raw_parquet(...) }}` (em `macros/read_raw_parquet.sql`).
Mantém o source YAML apenas como documentação.

## Por quê

1. **Funciona estável** em dbt-duckdb 1.9.0
2. **Variabilizável:** `vars: raw_path` no `dbt_project.yml` permite trocar caminho
   sem editar models
3. **Migração futura tranquila:** quando trocar pra Snowflake/BigQuery, basta
   reescrever a macro pra `from {{ ref('seed_externa') }}` ou source nativo

## Trade-offs aceitos

❌ Lineage no `dbt docs` não mostra "raw_parquet → staging" como aresta automática
✅ Documentação manual no `_cvm__sources.yml` cobre isso

## Quando reverter

- dbt-duckdb estabilizar `external.location` (acompanhar release notes)
- Migrar pra warehouse remoto (Snowflake/BigQuery) onde sources nativos funcionam perfeito
