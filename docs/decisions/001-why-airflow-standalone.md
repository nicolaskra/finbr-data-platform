# ADR 001 — Why Airflow Standalone (no Postgres/Celery)

**Data:** 2026-05-27
**Status:** Aceito (sessão 1)
**Reverter quando:** projeto precisar paralelismo ou alta disponibilidade

## Contexto

Airflow tem 3 modos de deploy comuns:

| Modo | Metadata | Executor | Quando |
|---|---|---|---|
| **Standalone** | SQLite | SequentialExecutor | Dev local, learning, demo |
| **LocalExecutor** | Postgres | LocalExecutor | Single-node prod pequeno |
| **CeleryExecutor** | Postgres + Redis | CeleryExecutor | Multi-node, scale-out |

## Decisão

Usar **Standalone** (SQLite + SequentialExecutor) na sessão 1.

## Por quê

1. **Portfolio local:** repositório roda com `docker compose up` em qualquer máquina
2. **Custo zero:** sem Postgres container, sem Redis container
3. **Setup em <1 min:** SQLite é embedded, zero configuração
4. **Suficiente pro escopo:** 3 DAGs, 1 job por vez, dados em GB

## Trade-offs aceitos

❌ **Sem paralelismo:** SequentialExecutor roda 1 task por vez
❌ **Sem alta disponibilidade:** SQLite single-file, lock contention possível
❌ **Não escala:** se DAGs crescerem pra >50, migrar pra Postgres + LocalExecutor

## Quando reverter

- Pipeline crescer pra >10 DAGs ativas
- Necessidade de rodar >1 task em paralelo (ex: ingestar CVM + BCB + B3 simultâneo)
- Demonstrar HA pra recrutador (criar branch `feat/celery-prod` separada)

## Documentado em

- `docker-compose.yml` (comentário no topo)
- `README.md` seção Stack
