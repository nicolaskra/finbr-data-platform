# Constraints do projeto — INEGOCIÁVEIS

> Esse documento lista limites de design auto-impostos.
> Nenhum PR deve violar essas regras sem alterar este arquivo antes.

---

## 🟢 1. Stack 100% gratuita

**Tudo no projeto roda sem nenhum serviço pago.**

| Camada | Tool | Por quê é grátis |
|---|---|---|
| Orquestração | Apache Airflow (OSS) | Open source, roda local em Docker |
| Transformação | dbt-core + dbt-duckdb | OSS |
| Warehouse | DuckDB | Single-file embedded, grátis |
| API | FastAPI + Uvicorn | OSS |
| Dashboard | Streamlit | OSS, free hosting opcional |
| Distribuído | PySpark local | OSS (Java 17 OSS) |
| CI | GitHub Actions | 2.000 min/mês free |
| Testes | pytest + dbt tests | OSS |

### O que NÃO entra no projeto

- ❌ APIs LLM pagas (OpenAI, Anthropic Claude API, Cohere)
- ❌ Warehouses pagos além do free tier (Snowflake, BigQuery além de 10 GB/mês)
- ❌ Observability pago (Datadog, New Relic, Sentry pago)
- ❌ Vector DBs hospedados (Pinecone, Weaviate Cloud)
- ❌ Schedulers managed (Astronomer Cloud, Prefect Cloud paid)

### Alternativas free que adotamos quando precisar

| Categoria | Alternativa free |
|---|---|
| LLM | Ollama local (Llama 3, Mistral, Qwen, Gemma) |
| Embeddings | sentence-transformers (HuggingFace, local) |
| Vector DB | ChromaDB / DuckDB VSS / Faiss (local) |
| Observability | Grafana + Prometheus (Docker local) |
| Evals LLM | DeepEval com Ollama OU evals determinísticos pytest |

---

## 🟢 2. Dados públicos apenas

Toda fonte usada no projeto é **dado público brasileiro**:

- CVM (dados.cvm.gov.br) — Lei de Acesso à Informação 12.527/2011
- BCB SGS (Sistema Gerenciador de Séries Temporais) — público
- B3 (Histórico de cotações) — público

Nenhum dado de cliente real ou PII entra no repo.

---

## 🟢 3. Reprodutível em qualquer máquina

`git clone && docker compose up -d` deve subir tudo sem credenciais externas.

Exceções aceitáveis:
- BigQuery sandbox (futuro): requer login Google grátis
- Claude Code (desenvolvimento): subscription do mantenedor, não vai pro produto

---

## 🟢 4. Decisões registradas (ADRs)

Toda escolha de stack não-óbvia tem ADR em `docs/decisions/`.
Reverter uma escolha requer ADR novo explicando o porquê.

---

## Por que isso importa

Esse repo é **projeto de portfolio público** — qualquer recrutador deve poder
clonar e validar end-to-end sem custo. Restringir a stack a free-tier força
escolhas arquiteturais que escalam (DuckDB ao invés de Snowflake, Ollama ao
invés de OpenAI). Sinaliza maturidade técnica acima da média de mercado.
