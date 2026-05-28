# Arquitetura — finbr-data-platform

## Visão de alto nível

```mermaid
flowchart LR
    subgraph "Sources (public APIs)"
        CVM[CVM<br/>Fundos<br/>CSV ZIP mensal]
        BCB[BCB SGS<br/>Selic / IPCA<br/>JSON diario]
        B3[B3<br/>Cotacoes<br/>CSV diario]
    end

    subgraph "Orchestration — Airflow Standalone (Docker)"
        DAG1[ingest_cvm_informe_diario<br/>mensal, dia 5]
        DAG2[ingest_bcb_sgs<br/>diario - sessao 2]
        DAG3[ingest_b3_cotacoes<br/>diario - sessao 2]
    end

    subgraph "Data Lake — Parquet particionado"
        RAW1[("data/raw/cvm/<br/>inf_diario/YYYY-MM/")]
        RAW2[("data/raw/bcb/<br/>sgs/YYYY-MM/")]
        RAW3[("data/raw/b3/<br/>cotacoes/YYYY-MM/")]
    end

    subgraph "Transformation — dbt (sessao 2)"
        STG[staging models<br/>tipagem + clean]
        INT[intermediate<br/>joins + biz logic]
        MART[marts<br/>fato + dimensoes]
    end

    subgraph "Warehouse"
        DUCKDB[(DuckDB single-file<br/>warehouse.duckdb)]
    end

    subgraph "Serving (sessao 3)"
        API[FastAPI<br/>REST + OpenAPI]
        UI[Streamlit<br/>Dashboard]
    end

    subgraph "Quality (sessao 4)"
        UNIT[pytest<br/>DAG + transform tests]
        EVAL[DeepEval<br/>LLM answer quality]
    end

    CVM --> DAG1 --> RAW1
    BCB --> DAG2 --> RAW2
    B3 --> DAG3 --> RAW3

    RAW1 & RAW2 & RAW3 --> STG --> INT --> MART --> DUCKDB

    DUCKDB --> API
    DUCKDB --> UI

    UNIT -.cobre.-> DAG1 & DAG2 & DAG3 & STG
    EVAL -.audita.-> API
```

---

## Decisões arquiteturais (ADRs)

- [001 — Why Airflow Standalone (no Postgres/Celery)](./decisions/001-why-airflow-standalone.md)
- [002 — Why DuckDB (no Snowflake/BigQuery)](./decisions/002-why-duckdb.md)
- [003 — Why dbt-core (no Fivetran/Stitch)](./decisions/003-why-dbt-core.md)

---

## Particionamento de dados raw

Padrão: `data/raw/{source}/{dataset}/{YYYY-MM}/{file}.parquet`

Exemplo: `data/raw/cvm/inf_diario/2026-04/inf_diario.parquet`

**Por que YYYY-MM em vez de YYYY/MM/DD?**
- CVM publica dado mensal (não diário)
- BCB SGS pode ser agregado mensal mesmo sendo diário
- Simplifica navegação e dbt sources
- Compatível com Hive-style partitioning (DuckDB lê com `partition_by`)

---

## Idempotência

Toda DAG aqui é **idempotente**: re-rodar pra mesma partição substitui o output (não duplica).

- Download CVM é determinístico (mesma URL → mesmo conteúdo)
- `salvar_particionado` faz `rename` (substitui)
- dbt models são `table` ou `incremental` com `unique_key` (sessão 2)

---

## Failure handling

Cada task tem:
- `retries=3` com `retry_exponential_backoff=True`
- `retry_delay=5min` inicial
- Validação de schema explícita (raise se schema CVM mudar — fail-fast)
- Logs estruturados em `airflow/logs/`

DLQ não implementado nesta sessão (Standalone executor não suporta). Em produção: Celery + Redis + DLQ via failure callback.
