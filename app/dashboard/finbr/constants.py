"""Constantes do dashboard: benchmark CDI hardcoded por mes + paleta semantica.

CDI mensal = retorno aproximado do certificado de deposito interbancario.
Valores baseados em Selic meta a.a. / 12 (BCB, Mai/2026):
- Selic 14.50% a.a. → ~1.13% ao mes
- Selic 14.75% a.a. → ~1.15% ao mes

Esses valores serao SUBSTITUIDOS pela tabela `fct_benchmark_mensal` quando
S5 (ingest BCB SGS) estiver no warehouse. Por enquanto, hardcode com nota.
"""

from __future__ import annotations

# Benchmark CDI mensal por mes-referencia (primeiro dia do mes).
# Fonte: Banco Central do Brasil — Sistema Selic Meta (Histórico).
# https://www.bcb.gov.br/controleinflacao/historicotaxasjuros
CDI_MENSAL_PCT: dict[str, float] = {
    "2024-12-01": 1.06,
    "2025-01-01": 1.01,
    "2025-02-01": 0.99,
    "2025-03-01": 1.04,
    "2025-04-01": 1.03,
    "2025-05-01": 1.13,
    "2025-06-01": 1.18,
    "2025-07-01": 1.18,
    "2025-08-01": 1.18,
    "2025-09-01": 1.13,
    "2025-10-01": 1.18,
    "2025-11-01": 1.13,
    "2025-12-01": 1.13,
    "2026-01-01": 1.13,
    "2026-02-01": 1.03,
    "2026-03-01": 1.13,
    "2026-04-01": 1.13,
}
CDI_DEFAULT_PCT = 1.10  # fallback se mes nao mapeado

# Paleta semantica. Usar apenas estas cores no dashboard.
COLOR_PRIMARY = "#0F2A4A"  # navy escuro (mesma do theme.toml)
COLOR_NEUTRAL = "#6B7280"  # cinza chumbo
COLOR_BG_SOFT = "#F4F6F8"  # cinza muito claro
COLOR_POSITIVE = "#1B7F4D"  # verde (acima do benchmark)
COLOR_NEGATIVE = "#C0392B"  # vermelho (abaixo do benchmark)
COLOR_BENCHMARK = "#D69E00"  # ambar/gold (linha de referencia CDI)
COLOR_ACCENT = "#3B7DD8"  # azul medio (destaque)


def cdi_do_mes(mes_iso: str) -> float:
    """Retorna CDI mensal em % para o primeiro dia do mes (YYYY-MM-DD)."""
    return CDI_MENSAL_PCT.get(mes_iso, CDI_DEFAULT_PCT)
