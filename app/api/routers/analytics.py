"""Endpoint /analytics/top-fundos — ranking mensal."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from app.api.db import get_connection
from app.api.schemas import TopFundoItem, TopFundosResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/top-fundos",
    response_model=TopFundosResponse,
    summary="Top 50 fundos por rentabilidade no mes",
    responses={404: {"description": "Mes sem dados"}},
)
def top_fundos(
    mes: date = Query(
        ...,
        description="Primeiro dia do mes desejado (ex: 2026-04-01)",
        examples=["2026-04-01"],
    ),
    limit: int = Query(10, ge=1, le=50, description="Quantos resultados retornar"),
) -> TopFundosResponse:
    """Top N classes de fundo por rentabilidade mensal (PL min R$1M, 15+ dias uteis)."""
    with get_connection() as con:
        df = con.execute(
            """
            select
                mes,
                ranking_mes,
                cnpj_classe,
                tipo_classe,
                rentabilidade_mes_pct,
                dias_uteis,
                vl_patrim_liq_fim_mes,
                nr_cotistas_fim_mes
            from main_analytics.top_fundos_rentabilidade_mes
            where mes = ?
            order by ranking_mes
            limit ?
            """,
            [mes, limit],
        ).df()

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sem dados para o mes {mes}",
        )

    fundos = [
        TopFundoItem(
            mes=row["mes"],
            ranking_mes=int(row["ranking_mes"]),
            cnpj_classe=row["cnpj_classe"],
            tipo_classe=row["tipo_classe"],
            rentabilidade_mes_pct=float(row["rentabilidade_mes_pct"]),
            dias_uteis=int(row["dias_uteis"]),
            vl_patrim_liq_fim_mes=float(row["vl_patrim_liq_fim_mes"]),
            nr_cotistas_fim_mes=int(row["nr_cotistas_fim_mes"]),
        )
        for _, row in df.iterrows()
    ]

    return TopFundosResponse(mes=mes, total=len(fundos), fundos=fundos)
