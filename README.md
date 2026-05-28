<div align="center">

# finbr-data-platform

**End-to-end data platform · 100% free-tier · dados públicos brasileiros**

Airflow · dbt · DuckDB · FastAPI · Streamlit · PySpark · pytest data quality

[![CI](https://github.com/nicolaskra/finbr-data-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/nicolaskra/finbr-data-platform/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Airflow 2.10](https://img.shields.io/badge/airflow-2.10-017CEE.svg?logo=apacheairflow&logoColor=white)](https://airflow.apache.org/)
[![dbt-duckdb 1.9](https://img.shields.io/badge/dbt-duckdb_1.9-FF694B.svg?logo=dbt&logoColor=white)](https://github.com/duckdb/dbt-duckdb)
[![DuckDB 1.1](https://img.shields.io/badge/DuckDB-1.1-FFF000.svg?logo=duckdb&logoColor=black)](https://duckdb.org/)
[![FastAPI 0.115](https://img.shields.io/badge/FastAPI-0.115-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit 1.40](https://img.shields.io/badge/Streamlit-1.40-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![No paid services](https://img.shields.io/badge/stack-100%25_free-success.svg)](./CONSTRAINTS.md)

</div>

---

## 🎯 Por que esse projeto existe

A maioria dos portfolios Data Engineering replica tutoriais: NYC Taxi, MNIST, GitHub events.
Esse projeto faz o oposto: usa **dados reais públicos do mercado financeiro brasileiro**
(CVM, BCB, B3) e implementa **end-to-end completo** demonstrando:

- **System integration:** ingestão → orquestração → warehouse → transformação → API → frontend
- **Sinais sênior:** trade-offs documentados (5 ADRs), failure handling, idempotência,
  data quality tests informados pelo dado real
- **Hobby-driven:** dado público BR + matemática financeira (rentabilidade composta)
- **Constraint inegociável:** **100% gratuito** (ver [`CONSTRAINTS.md`](./CONSTRAINTS.md))

> *"Senior portfolio mostra POR QUE existe, não só COMO funciona."* — The Data Forge

---

## 🏗️ Arquitetura

```mermaid
flowchart LR
    subgraph "Sources (publicos BR)"
        CVM[CVM<br/>Fundos]
        BCB[BCB<br/>SGS]
        B3[B3<br/>Cotacoes]
    end

    subgraph "Airflow (Docker)"
        D1[ingest_cvm<br/>pandas]
        D2[ingest_cvm<br/>pyspark]
        D3[dbt_transform]
    end

    subgraph "DuckDB warehouse"
        STG[(staging)]
        INT[(intermediate)]
        CORE[(core: dim + fct)]
        ANA[(analytics)]
    end

    subgraph "Serving"
        API[FastAPI<br/>:8000]
        UI[Streamlit<br/>:8501]
    end

    CVM --> D1 & D2 --> STG
    BCB & B3 -.futuro.-> D1
    D3 --> INT --> CORE --> ANA
    STG --> INT
    CORE & ANA --> API --> UI
```

---

## 📊 Stack

| Camada | Tool | Por quê (vs alternativa popular) |
|---|---|---|
| Orquestração | **Apache Airflow** | Padrão de mercado, DAGs versionados, retry nativo |
| Ingestão | **pandas + pyarrow** | Dataset 14 MB → Spark seria overhead (ver [ADR 005](./docs/decisions/005-pandas-vs-pyspark.md)) |
| Ingestão distribuída | **PySpark** (versão didática) | Demonstra fluência; manual trigger apenas |
| Warehouse | **DuckDB** | Performance Snowflake-like, single-file, free ([ADR 002](./docs/decisions/002-why-duckdb.md)) |
| Transformação | **dbt-duckdb** | Lineage + tests + docs autogerados ([ADR 003](./docs/decisions/003-why-dbt-core.md)) |
| API | **FastAPI + Pydantic** | Async, type-safe, OpenAPI grátis |
| Dashboard | **Streamlit** | Deploy free, prototipagem rápida |
| Container | **Docker Compose** | `git clone && docker compose up` |
| CI | **GitHub Actions** | Free 2000 min/mês |
| Quality | **pytest + dbt tests** | 3 camadas: unit (DAG/API) + business rules + dbt |

**Ver decisões em** [`docs/decisions/`](./docs/decisions/) (5 ADRs)

---

## 🚀 Rodar local (5 min)

```bash
git clone https://github.com/nicolaskra/finbr-data-platform.git
cd finbr-data-platform

# Sobe Airflow + API + Dashboard (3 containers)
docker compose up -d

# Aguarda ~3 min na primeira vez (download imagens + build)
# Acompanhe: docker compose ps
```

### Endpoints

| Serviço | URL | Login |
|---|---|---|
| Airflow | http://localhost:8080 | `admin` / senha em `airflow/standalone_admin_password.txt` |
| API docs | http://localhost:8000/docs | — |
| Dashboard | http://localhost:8501 | — |

### Primeiro pipeline run

```bash
# Despausar e disparar a DAG de ingest
docker exec finbr-airflow airflow dags unpause ingest_cvm_informe_diario
docker exec finbr-airflow airflow dags trigger ingest_cvm_informe_diario

# Aguardar concluir, depois rodar dbt
docker exec finbr-airflow airflow dags unpause dbt_transform
docker exec finbr-airflow airflow dags trigger dbt_transform

# Verificar warehouse
curl http://localhost:8000/health
```

---

## 📊 Dados produzidos (último run real, Abr/2026)

| Camada | Tabela | Linhas |
|---|---|---|
| Staging | `stg_cvm__informe_diario` | 506.122 |
| Core | `dim_fundo_classe` | 25.674 |
| Core | `fct_fundo_rentabilidade_mensal` | 25.598 |
| Analytics | `top_fundos_rentabilidade_mes` | 50 |

**Pipeline completo (pandas):** ~4s  ·  **PySpark equivalente:** ~10s (cold JVM)

---

## ✅ Testes (34/34 em 3.4s)

| Categoria | Qtd | Cobertura |
|---|---|---|
| `tests/dags/` | 10 | Estrutura DAG + lógica das tasks (pytest + DagBag) |
| `tests/api/` | 10 | TestClient + DuckDB sintético em fixture |
| `tests/data_quality/` | 14 | Asserções de regra de negócio sobre warehouse real |
| `dbt build` | 22 | not_null, unique, relationships, custom |

**Rodar tudo:**
```bash
pytest tests/ -v
docker exec finbr-airflow bash -c "cd /opt/airflow/dbt && dbt build --profiles-dir ."
```

---

## 🔍 Achados reais documentados

Toda anomalia descoberta nos data quality tests vira aprendizado documentado:

- **CVM Resolução 175/2024:** schema mudou (`TP_FUNDO` → `TP_FUNDO_CLASSE`); fail-fast pegou
- **PL negativo:** 0.001% das linhas (fundos em liquidação / alavancados) — threshold informado pelo dado
- **Outlier 1360%:** classe pequena com NAV distorcido — filtros atuais não cortam

**Ver** [`docs/data_quality_findings.md`](./docs/data_quality_findings.md)

---

## 🗂️ Estrutura

```
finbr-data-platform/
├── airflow/
│   ├── dags/
│   │   ├── ingest_cvm_informe_diario.py        # pandas (default)
│   │   ├── ingest_cvm_informe_diario_spark.py  # PySpark (didático)
│   │   └── dbt_transform.py                    # orquestra dbt
│   ├── Dockerfile                              # + Java 17 + dbt + pyspark
│   └── requirements.txt
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── macros/read_raw_parquet.sql
│   └── models/
│       ├── staging/cvm/
│       ├── intermediate/
│       └── marts/{core,analytics}/
├── app/
│   ├── api/                                    # FastAPI
│   │   ├── routers/{health,fundos,analytics}.py
│   │   ├── schemas.py
│   │   └── Dockerfile
│   └── dashboard/                              # Streamlit
│       ├── streamlit_app.py
│       └── Dockerfile
├── tests/
│   ├── dags/                                   # 10 tests
│   ├── api/                                    # 10 tests
│   └── data_quality/                           # 14 tests
├── docs/
│   ├── architecture.md
│   ├── data_quality_findings.md
│   └── decisions/                              # 5 ADRs
├── .github/workflows/ci.yml                    # GitHub Actions
├── .pre-commit-config.yaml                     # ruff + sqlfluff
├── CONSTRAINTS.md                              # regras inegociáveis
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## 📚 Sources

- **CVM:** [Dados Abertos — Informes Diários FI](https://dados.cvm.gov.br/dataset/fi-doc-inf_diario)
- **BCB:** [SGS — Sistema Gerenciador de Séries Temporais](https://www3.bcb.gov.br/sgspub/) *(roadmap)*
- **B3:** [Histórico de cotações](https://www.b3.com.br/) *(roadmap)*

---

## 🛣️ Roadmap

- [x] **S1** — Airflow + DAG ingest CVM (pandas) + tests + ADRs
- [x] **S2** — dbt warehouse DuckDB (6 models, 16 tests, 2 exposures)
- [x] **S3** — FastAPI (3 endpoints) + Streamlit dashboard + paridade PySpark
- [x] **S4** — Data quality tests + CI + pre-commit + público
- [ ] **S5** — Ingest BCB SGS (Selic, IPCA) + BCB no warehouse + dashboard timeline
- [ ] **S6** — Ingest B3 cotações históricas (versão PySpark vira default)
- [ ] **S7** — Evals com Ollama local (Llama 3.1) — opcional

---

## 📄 License

MIT — ver [LICENSE](./LICENSE)

---

<div align="center">

Construído por [Nícolas Klein](https://github.com/nicolaskra) · [LinkedIn](https://www.linkedin.com/in/nicolaskleincg/) · [smartbusiness.ia.br](https://smartbusiness.ia.br/)

</div>
