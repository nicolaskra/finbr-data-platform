# ADR 003 — Why dbt-core (no Spark SQL, no raw Python)

**Data:** 2026-05-27
**Status:** Planejado (implementar na sessão 2)
**Reverter quando:** modelos exigirem lógica imperativa complexa

## Contexto

Transformação dados raw → analytics. Opções:

| Opção | Lineage | Tests | Docs | Curva |
|---|---|---|---|---|
| **dbt-core** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (auto) | Baixa (SQL) |
| Pandas/PySpark scripts | ❌ manual | ❌ manual | ❌ manual | Média |
| SQLMesh | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | Média |
| dbt Cloud (managed) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Baixa | $$ |

## Decisão

Usar **dbt-core** com adapter `dbt-duckdb`.

## Por quê

1. **Padrão de mercado:** vaga GEX cita "modelos semânticos e camadas analíticas escaláveis" — dbt é a resposta
2. **Lineage grátis:** `dbt docs generate` gera DAG visual
3. **Tests declarativos:** `not_null`, `unique`, `relationships`, `accepted_values` no YAML
4. **Documentação como código:** descrições nos `.yml` viram site estático
5. **Convenção sobre configuração:** staging/intermediate/marts padrão da indústria
6. **Roda local:** dbt-core é OSS, zero custo

## Estrutura planejada (sessão 2)

```
dbt/
├── dbt_project.yml
├── profiles.yml (gitignored, template em profiles.yml.example)
├── models/
│   ├── staging/
│   │   ├── cvm/
│   │   │   ├── stg_cvm__informe_diario.sql
│   │   │   └── _stg_cvm__sources.yml
│   │   └── bcb/
│   ├── intermediate/
│   │   └── int_fundos__performance_mensal.sql
│   └── marts/
│       ├── core/
│       │   ├── fct_fundo_rentabilidade.sql
│       │   └── dim_fundo.sql
│       └── analytics/
│           └── fundos_top10_yyyymm.sql
├── tests/
├── macros/
└── seeds/
```

## Trade-offs aceitos

❌ **SQL-only:** lógica imperativa (ex: ML inference) fica fora — usa Python script + dbt-external-tables
❌ **Não bom pra streaming:** dbt é batch. Real-time vai em projeto separado
❌ **Adapter community:** dbt-duckdb é OSS mantido por Jacob Matson (não oficial dbt Labs). Risco baixo, ativo.

## Quando reverter

- Transformações exigirem loops/recursão complexa (PySpark direto)
- Precisar streaming (Flink/Spark Structured Streaming)

## Documentado em

- `README.md` tabela Stack
- `docs/architecture.md`
