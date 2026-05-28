"""Endpoint /fundos/rentabilidade — serie historica de classe."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.db import get_connection
from app.api.schemas import FundoHistorico, RentabilidadeMensal

router = APIRouter(prefix="/fundos", tags=["fundos"])


@router.get(
    "/rentabilidade",
    response_model=FundoHistorico,
    summary="Serie historica de rentabilidade mensal por classe (CNPJ via query)",
    responses={404: {"description": "Classe nao encontrada"}},
)
def rentabilidade_historica(
    cnpj: str = Query(
        ...,
        description="CNPJ da classe (formato XX.XXX.XXX/XXXX-XX). Em query string para evitar conflito com o '/' do CNPJ no path.",
        examples=["00.017.024/0001-53"],
    ),
    id_subclasse: str | None = Query(
        None,
        description="Subclasse opcional. Se omitido, retorna a 1a subclasse encontrada.",
    ),
) -> FundoHistorico:
    """
    Serie temporal de rentabilidade mensal de uma classe de fundo CVM.

    Calcula via produto composto de rentabilidades diarias.
    """
    with get_connection() as con:
        query = """
            select
                cnpj_classe,
                id_subclasse,
                tipo_classe,
                mes,
                rentabilidade_mes,
                dias_uteis,
                vl_patrim_liq_fim_mes,
                nr_cotistas_fim_mes
            from main_core.fct_fundo_rentabilidade_mensal
            where cnpj_classe = ?
              and (? is null or id_subclasse = ?)
            order by mes
        """
        df = con.execute(
            query,
            [cnpj, id_subclasse, id_subclasse],
        ).df()

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Classe {cnpj} nao encontrada no warehouse",
        )

    # Pega 1a subclasse caso omitida e haja multiplas
    if id_subclasse is None:
        primeira = df["id_subclasse"].iloc[0]
        df = df[df["id_subclasse"] == primeira]

    serie = [
        RentabilidadeMensal(
            mes=row["mes"],
            rentabilidade_mes=float(row["rentabilidade_mes"]),
            rentabilidade_mes_pct=float(row["rentabilidade_mes"]) * 100,
            dias_uteis=int(row["dias_uteis"]),
            vl_patrim_liq_fim_mes=(
                float(row["vl_patrim_liq_fim_mes"])
                if row["vl_patrim_liq_fim_mes"] is not None
                else None
            ),
            nr_cotistas_fim_mes=(
                int(row["nr_cotistas_fim_mes"]) if row["nr_cotistas_fim_mes"] is not None else None
            ),
        )
        for _, row in df.iterrows()
    ]

    return FundoHistorico(
        cnpj_classe=df["cnpj_classe"].iloc[0],
        id_subclasse=df["id_subclasse"].iloc[0],
        tipo_classe=df["tipo_classe"].iloc[0],
        serie=serie,
    )
