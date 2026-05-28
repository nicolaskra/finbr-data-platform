# ADR 002 — Why DuckDB (no Snowflake/BigQuery/Postgres)

**Data:** 2026-05-27
**Status:** Aceito
**Reverter quando:** dataset crescer >100 GB ou precisar multi-user concorrente

## Contexto

Warehouse pra agregar dados CVM + BCB + B3 e servir API/dashboard. Opções:

| Opção | Custo | Performance OLAP | Setup |
|---|---|---|---|
| **DuckDB** | R$ 0 | ⭐⭐⭐⭐⭐ (colunar, vectorized) | 1 arquivo |
| **PostgreSQL** | R$ 0 | ⭐⭐ (OLTP-optimized) | Container |
| **BigQuery free** | R$ 0 (1TB query/mês) | ⭐⭐⭐⭐⭐ | GCP project |
| **Snowflake free** | R$ 0 (30 dias trial) | ⭐⭐⭐⭐⭐ | Conta cloud |
| **ClickHouse** | R$ 0 | ⭐⭐⭐⭐⭐ | Container pesado |

## Decisão

Usar **DuckDB** como warehouse principal local.

## Por quê

1. **Zero infra:** single-file `warehouse.duckdb`, zero containers
2. **Performance OLAP de verdade:** vectorized execution, colunar — bench compara com Snowflake em datasets <100GB
3. **dbt-duckdb maduro:** adapter oficial mantido, suporta incremental/snapshot/seeds
4. **Lê Parquet direto:** `SELECT * FROM 'data/raw/cvm/**/*.parquet'` sem ingestão
5. **SQL standard:** queries portáveis pra BQ/Snowflake depois
6. **Demo `git clone && rodar`:** recrutador testa em 5 min sem criar conta cloud

## Trade-offs aceitos

❌ **Single-writer:** 1 processo escrevendo por vez. OK pra Airflow (1 DAG ativa)
❌ **Não escala pra TB:** limite prático ~100GB single-machine
❌ **Sem ACL/RBAC:** sem multi-tenant. OK pra portfolio
❌ **Recrutador "ah é local, não é prod"** — mitigado documentando trade-off + ADR `004-future-migrate-bigquery` (futuro)

## Quando reverter

- Dataset crescer >100GB (CVM histórico completo = ~50GB hoje)
- Precisar multi-tenant ou >1 escritor concorrente
- Quiser demonstrar BigQuery hands-on (criar branch `feat/bigquery-warehouse`)

## Benchmarks de referência

- [DuckDB vs Snowflake (TPC-H) — Mother Duck blog 2024](https://motherduck.com/blog/duckdb-vs-snowflake/)
- DuckDB 1.x roda TPC-H SF-100 em ~30s no MacBook

## Documentado em

- `README.md` tabela Stack
- `dbt/profiles.yml` (próxima sessão)
