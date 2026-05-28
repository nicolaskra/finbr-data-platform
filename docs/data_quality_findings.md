# Data Quality Findings — Aprendizados do dataset real CVM

> Cada achado aqui foi descoberto por um teste em `tests/data_quality/` rodando
> contra o warehouse populado com dados reais. Documenta-se a anomalia,
> a investigação e a regra final (que pode ser "aceitar como dado real").

---

## #1 — PL negativo em ~0.001% das linhas

**Achado:** 6 linhas (de 506.122) com `vl_patrim_liq < 0` no informe Abr/2026.

**Investigação:**
```
       cnpj_classe data_competencia  vl_patrim_liq    vl_total  nr_cotistas
06.174.847/0001-79       2026-04-28     -111274.37 15409741.56            2  ← alavancado
29.242.473/0001-87       2026-04-16     -111224.83  9839930.63            1  ← alavancado
64.095.255/0001-68       2026-04-02      -38605.26        0.00            2  ← liquidando
64.095.255/0001-68       2026-04-01      -38055.26        0.00            2  ← liquidando
64.095.186/0001-92       2026-04-02      -23568.90        0.00            2  ← liquidando
64.095.186/0001-92       2026-04-01      -23218.90        0.00            3  ← liquidando

Range: -111k <= PL < 0
```

**Classificação:**
- **4 casos** (`vl_total = 0` + PL negativo): fundos em **liquidação** com obrigações
  pendentes. Padrão CVM legítimo.
- **2 casos** (`vl_total >> 0` + PL negativo): fundos **alavancados** com posição
  mark-to-market negativa naquele dia. Também legítimo.

**Decisão:**
- ✅ Aceitar até 0.1% das linhas com PL negativo (atual: 0.001%)
- ❌ Rejeitar PL < -R$ 1.000.000 (provável bug de import / encoding)
- Test atualizado: `test_vl_patrim_liq_negativo_dentro_do_esperado`

**Sinal sênior:** thresholds informados por **conhecimento do dado**, não absolutos.

---

## #2 — Schema CVM mudou em 2024 (Resolução 175)

**Achado:** colunas `TP_FUNDO`/`CNPJ_FUNDO` foram renomeadas para
`TP_FUNDO_CLASSE`/`CNPJ_FUNDO_CLASSE` + nova coluna `ID_SUBCLASSE`.

**Como pegamos:** validação fail-fast na DAG (`raise ValueError('Schema CVM mudou')`)
quebrou no primeiro run real. Não foi um bug nosso — foi mudança regulatória.

**Decisão:** EXPECTED_COLUMNS atualizada, ADR 005 documenta racional.

---

## #3 — Outlier de 1360% no top fundos

**Achado:** fundo `52.286.056/0001-58` aparece como #1 com rentabilidade
1360.22% no mês de Abr/2026.

**Investigação:** PL = R$ 3.8M, apenas 3 cotistas, 15 dias úteis. Provavelmente
fundo novo com NAV inicial muito baixo ou cota com base de cálculo distorcida.

**Decisão:** filtros atuais (PL >= R$ 1M, dias_uteis >= 15) **não cortam** esse
caso porque ele passa nos dois. Para análise pública, considerar adicionar:
- Filtro adicional: `nr_cotistas >= 5` (pulverização mínima)
- Ou: filtro percentil 99 da distribuição mensal

**Status:** documentado, não implementado. Próximo refinamento do `top_fundos`.

---

## Por que esse arquivo existe

Engenheiro Pleno detecta o problema e corrige.
**Sênior detecta, investiga, classifica, decide threshold informado, e documenta.**

Esse arquivo é a evidência da segunda postura.
