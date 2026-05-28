"""Response schemas Pydantic (validacao automatica + OpenAPI)."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------
# Health
# --------------------------------------------------------------------


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str = Field(..., examples=["ok"])
    warehouse_path: str
    warehouse_size_mb: float
    rows_staging: int
    rows_dim: int
    rows_fct: int


# --------------------------------------------------------------------
# Fundos: rentabilidade historica
# --------------------------------------------------------------------


class RentabilidadeMensal(BaseModel):
    model_config = ConfigDict(frozen=True)

    mes: date
    rentabilidade_mes: float = Field(..., description="Decimal (ex: 0.012 = 1.2%)")
    rentabilidade_mes_pct: float = Field(..., description="Pre-formatado em %")
    dias_uteis: int
    vl_patrim_liq_fim_mes: float | None
    nr_cotistas_fim_mes: int | None


class FundoHistorico(BaseModel):
    model_config = ConfigDict(frozen=True)

    cnpj_classe: str
    id_subclasse: str | None
    tipo_classe: str | None
    serie: list[RentabilidadeMensal]


# --------------------------------------------------------------------
# Analytics: top fundos
# --------------------------------------------------------------------


class TopFundoItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    mes: date
    ranking_mes: int
    cnpj_classe: str
    tipo_classe: str | None
    rentabilidade_mes_pct: float
    dias_uteis: int
    vl_patrim_liq_fim_mes: float
    nr_cotistas_fim_mes: int


class TopFundosResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    mes: date
    total: int
    fundos: list[TopFundoItem]
