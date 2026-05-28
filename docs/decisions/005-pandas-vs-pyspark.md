# ADR 005 — Pandas (default) + PySpark (paralela didatica) para ingest CVM

**Data:** 2026-05-27
**Status:** Aceito (sessão 3)
**Reverter quando:** dataset CVM passar de 1 GB ou novo dataset > 10 GB

## Contexto

O Informe Diário CVM tem ~14 MB/mês (Parquet snappy) e ~500k linhas.
Duas versões de DAG foram implementadas:

| DAG | Engine | Schedule | Tempo total |
|---|---|---|---|
| `ingest_cvm_informe_diario` | pandas + pyarrow | mensal automatico | ~3-4s |
| `ingest_cvm_informe_diario_spark` | PySpark local | manual (didatico) | ~30-60s (cold start JVM) |

## Decisão

- **pandas e a versao oficial** (default schedule, usado em produção)
- **PySpark e versao didatica** (manual trigger apenas, documentada como aprendizado)

## Por quê

### Pandas wins em <1 GB
1. **Cold start zero** — Python carrega em ~100ms vs Spark ~30s+ (JVM + executors)
2. **pyarrow rapido** — leitura/escrita Parquet otimizada em C++
3. **Memoria suficiente** — 14 MB cabe trivialmente em RAM (Airflow worker tem 2 GB+)
4. **Codigo mais simples** — sem boilerplate de SparkSession

### Por que MANTER a versao Spark
1. **Demonstra fluencia** — saber Spark e diferencial de mercado
2. **Base para datasets futuros** — historico B3 diario, dados USP/FAPESP, etc.
3. **Documenta a decisao** — recrutador ve que voce ESCOLHEU, nao "nao soube"
4. **Custo de manter zero** — DAG fica `schedule=None`, so roda quando alguem aciona

## Trade-offs aceitos

❌ **Dois caminhos de codigo** — duplica logica de validacao de schema
✅ **Visibilidade da decisao** — codigo + ADR + tags `pyspark, didatico`

## Quando reverter (usar Spark default)

- CVM publicar dataset com >1 GB/mes (improvavel)
- Adicionar fonte que naturalmente passa de 10 GB (ex: ticks B3 intraday)
- Time crescer e precisar paralelismo distribuido em cluster managed (EMR/Databricks)

## Como rodar a versao Spark

```bash
# Manualmente via Airflow CLI:
docker exec finbr-airflow airflow dags trigger ingest_cvm_informe_diario_spark
```

Requer `pyspark` instalado no container (esta no `airflow/requirements.txt`).

## Refs

- [DuckDB blog: "Faster than Pandas"](https://duckdb.org/2024/03/27/duckdb-2x-faster-than-spark-and-1000x-faster-than-pandas.html) — confirma que pra single-node OLAP DuckDB e a melhor escolha; Spark so vale acima de TB
- ["Big Data is Dead" — Jordan Tigani 2023](https://motherduck.com/blog/big-data-is-dead/)
