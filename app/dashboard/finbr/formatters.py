"""Formatters BR (R$, %, locale pt-BR) — usados em todos os widgets/charts."""

from __future__ import annotations


def fmt_pct(v: float | None, casas: int = 2) -> str:
    """Formata percentual com virgula decimal BR. Ex: 11.5 -> '11,50%'."""
    if v is None:
        return "—"
    return f"{v:.{casas}f}%".replace(".", ",")


def fmt_pct_signed(v: float | None, casas: int = 2) -> str:
    """Como fmt_pct mas com sinal explicito (+/-). Util para deltas vs benchmark."""
    if v is None:
        return "—"
    sinal = "+" if v >= 0 else ""
    return f"{sinal}{v:.{casas}f}pp".replace(".", ",")


def fmt_rs(v: float | None, casas: int = 0) -> str:
    """Formata moeda BR. Acima de 1B usa B, 1M usa M, 1k usa K."""
    if v is None:
        return "—"
    abs_v = abs(v)
    if abs_v >= 1_000_000_000:
        return f"R$ {v / 1_000_000_000:.{casas + 2}f}B".replace(".", ",")
    if abs_v >= 1_000_000:
        return f"R$ {v / 1_000_000:.{casas + 1}f}M".replace(".", ",")
    if abs_v >= 1_000:
        return f"R$ {v / 1_000:.{casas}f}K".replace(".", ",")
    return f"R$ {v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_int(v: int | float | None) -> str:
    """Inteiro com separador BR. Ex: 25674 -> '25.674'."""
    if v is None:
        return "—"
    return f"{int(v):,}".replace(",", ".")
