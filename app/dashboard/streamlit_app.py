"""Dashboard finbr — CVM / fundos / rentabilidade vs CDI.

3 paginas:
- Overview: snapshot do mes (KPIs + distribuicao + breakdown)
- Top fundos: ranking com filtros e delta vs CDI inline
- Serie historica: evolucao de um fundo vs CDI acumulado

Modos:
- FINBR_MODE=duckdb (default no Streamlit Cloud): le `data/warehouse/finbr.duckdb` direto
- FINBR_MODE=api (Docker local): consome FastAPI em FINBR_API_URL
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.dashboard.finbr import queries
from app.dashboard.finbr.constants import (
    COLOR_BENCHMARK,
    COLOR_NEGATIVE,
    COLOR_NEUTRAL,
    COLOR_POSITIVE,
    COLOR_PRIMARY,
    cdi_do_mes,
)
from app.dashboard.finbr.formatters import fmt_int, fmt_pct, fmt_pct_signed, fmt_rs
from app.dashboard.finbr.theme import aplicar_layout_padrao

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DUCKDB_PATH = os.getenv("FINBR_DUCKDB_PATH", "data/warehouse/finbr.duckdb")

st.set_page_config(
    page_title="finbr · Mercado de Fundos BR",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_conn():
    path = Path(DUCKDB_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Warehouse nao encontrado em {path.resolve()}.")
    return duckdb.connect(str(path), read_only=True)


@st.cache_data(ttl=300)
def health_cached():
    p = Path(DUCKDB_PATH)
    return queries.health(get_conn(), str(p), round(p.stat().st_size / 1_048_576, 2))


@st.cache_data(ttl=300)
def meses_cached() -> list[str]:
    return queries.listar_meses(get_conn())


@st.cache_data(ttl=300)
def overview_cached(mes: str, cdi_pct: float):
    return queries.overview_kpis(get_conn(), mes, cdi_pct)


@st.cache_data(ttl=300)
def distribuicao_cached(mes: str):
    return queries.distribuicao_rentab(get_conn(), mes)


@st.cache_data(ttl=300)
def top_fundos_cached(mes: str, limit: int):
    return queries.top_fundos(get_conn(), mes, limit)


@st.cache_data(ttl=300)
def serie_cached(cnpj: str):
    return queries.serie_historica(get_conn(), cnpj)


@st.cache_data(ttl=300)
def cnpjs_cached(mes: str, prefixo: str | None = None):
    return queries.pesquisar_cnpjs(get_conn(), mes, prefixo, limit=200)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("📊 finbr")
st.sidebar.caption("Mercado de Fundos BR · dados CVM")

pagina = st.sidebar.radio(
    "Navegação",
    ["Overview do mês", "Top fundos", "Série histórica"],
    label_visibility="collapsed",
)

st.sidebar.divider()
try:
    h = health_cached()
    st.sidebar.success("Warehouse OK")
    c1, c2 = st.sidebar.columns(2)
    c1.metric("Meses", fmt_int(h["meses_count"]))
    c2.metric("Tamanho", f"{h['warehouse_size_mb']} MB")
    c1.metric("Classes", fmt_int(h["rows_dim"]))
    c2.metric("Linhas fct", fmt_int(h["rows_fct"]))
except Exception as exc:
    st.sidebar.error(f"Warehouse indisponivel: {exc}")
    st.stop()

st.sidebar.divider()
st.sidebar.caption(
    "Benchmark: **CDI ≈ Selic/12** hardcoded por mês (substituído por ingest BCB SGS na v0.2)."
)
st.sidebar.caption("[Source · GitHub](https://github.com/nicolaskra/finbr-data-platform)")

meses_disp = meses_cached()
if not meses_disp:
    st.error("Warehouse vazio — rode o pipeline (`scripts/backfill_cvm.py`).")
    st.stop()


# ---------------------------------------------------------------------------
# PAGINA 1 — Overview do mes
# ---------------------------------------------------------------------------


def render_overview() -> None:
    st.title("Overview do mês")
    st.caption(
        "Snapshot agregado do mercado de fundos brasileiros no mês selecionado. "
        "Filtros aplicados: PL > 0, dias úteis ≥ 15."
    )

    mes_sel = st.selectbox("Mês de referência", meses_disp, index=0)
    cdi_pct = cdi_do_mes(mes_sel)

    kpis = overview_cached(mes_sel, cdi_pct)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fundos observados", fmt_int(kpis["total_fundos"]))
    c2.metric("PL total", fmt_rs(kpis["pl_total"]))
    delta_acima = kpis["pct_acima_cdi"] - 50.0
    c3.metric(
        "% acima do CDI",
        fmt_pct(kpis["pct_acima_cdi"], 1),
        delta=f"{delta_acima:+.1f}pp vs 50%".replace(".", ","),
        delta_color="normal",
        help=f"CDI de referência: {fmt_pct(cdi_pct)} no mês.",
    )
    c4.metric(
        "Mediana rentab.",
        fmt_pct(kpis["mediana_rentab_pct"]),
        delta=f"{kpis['mediana_rentab_pct'] - cdi_pct:+.2f}pp vs CDI".replace(".", ","),
        delta_color="normal",
    )

    st.divider()

    # ---- Histograma de distribuicao ----
    st.subheader("Distribuição de rentabilidade mensal")
    st.caption(
        "Eixo X em pontos percentuais (pp). Linha laranja vertical = CDI do mês. "
        "Distribuição truncada em ±10pp para foco no centro (extremos vão para Top fundos)."
    )

    df_dist = distribuicao_cached(mes_sel)
    if df_dist.empty:
        st.warning("Sem dados para o mês.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=df_dist["rentab_pct"],
            nbinsx=60,
            marker={"color": COLOR_PRIMARY, "line": {"width": 0}},
            opacity=0.85,
            name="Fundos",
            hovertemplate="Bucket: %{x:.2f}pp<br>Fundos: %{y}<extra></extra>",
        )
    )
    fig.add_vline(
        x=cdi_pct,
        line={"color": COLOR_BENCHMARK, "dash": "dash", "width": 2},
        annotation_text=f"CDI {fmt_pct(cdi_pct)}",
        annotation_position="top right",
        annotation_font_color=COLOR_BENCHMARK,
    )
    fig.add_vline(
        x=float(df_dist["rentab_pct"].median()),
        line={"color": COLOR_NEUTRAL, "dash": "dot", "width": 1},
        annotation_text=f"Mediana {fmt_pct(float(df_dist['rentab_pct'].median()))}",
        annotation_position="top left",
        annotation_font_color=COLOR_NEUTRAL,
    )
    aplicar_layout_padrao(fig, height=380, ytitle="Quantidade de fundos")
    fig.update_xaxes(title="Rentabilidade do mês (pp)", ticksuffix="pp")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ---- Bucket de PL ----
    st.subheader("Tamanho do mercado por bucket de PL")
    st.caption("Distribuição dos fundos por faixa de patrimônio líquido (R$).")

    df_buckets = (
        get_conn()
        .execute(
            """
        with base as (
            select vl_patrim_liq_fim_mes as pl, rentabilidade_mes*100 as rentab_pct
            from main_core.fct_fundo_rentabilidade_mensal
            where mes = ?
              and vl_patrim_liq_fim_mes > 0
              and dias_uteis >= 15
        ),
        bucketed as (
            select
                case
                    when pl < 1e6     then '< R$ 1M'
                    when pl < 1e7     then 'R$ 1M – 10M'
                    when pl < 1e8     then 'R$ 10M – 100M'
                    when pl < 1e9     then 'R$ 100M – 1B'
                    else                 '> R$ 1B'
                end as bucket_pl,
                pl,
                rentab_pct
            from base
        )
        select
            bucket_pl,
            count(*)         as qtd,
            sum(pl)          as pl_total,
            median(rentab_pct) as mediana_rentab,
            avg(case when rentab_pct >= ? then 1.0 else 0.0 end)*100 as pct_acima_cdi
        from bucketed
        group by bucket_pl
        order by case bucket_pl
            when '< R$ 1M' then 1
            when 'R$ 1M – 10M' then 2
            when 'R$ 10M – 100M' then 3
            when 'R$ 100M – 1B' then 4
            else 5
        end
        """,
            [mes_sel, cdi_pct],
        )
        .df()
    )

    df_buckets["pl_total_fmt"] = df_buckets["pl_total"].apply(fmt_rs)
    df_buckets["qtd_fmt"] = df_buckets["qtd"].apply(fmt_int)
    df_buckets["mediana_fmt"] = df_buckets["mediana_rentab"].apply(fmt_pct)
    df_buckets["pct_acima_fmt"] = df_buckets["pct_acima_cdi"].apply(lambda v: fmt_pct(v, 1))

    st.dataframe(
        df_buckets[["bucket_pl", "qtd_fmt", "pl_total_fmt", "mediana_fmt", "pct_acima_fmt"]].rename(
            columns={
                "bucket_pl": "Faixa de PL",
                "qtd_fmt": "Qtd. fundos",
                "pl_total_fmt": "PL total",
                "mediana_fmt": "Mediana rentab.",
                "pct_acima_fmt": "% > CDI",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# PAGINA 2 — Top Fundos
# ---------------------------------------------------------------------------


def render_top_fundos() -> None:
    st.title("Top fundos por rentabilidade")
    st.caption(
        "Ranking do mart `top_fundos_rentabilidade_mes`. Filtros aplicados no warehouse: "
        "**PL ≥ R$ 1M**, **dias úteis ≥ 15**, **cotistas ≥ 5** (pulverização mínima)."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        mes_sel = st.selectbox("Mês", meses_disp, index=0, key="top_mes")
    with col2:
        limit = st.slider("Top N", min_value=5, max_value=50, value=20, step=5)

    cdi_pct = cdi_do_mes(mes_sel)
    df = top_fundos_cached(mes_sel, limit)

    if df.empty:
        st.warning(f"Sem ranking disponível para {mes_sel}.")
        return

    df = df.copy()
    df["delta_cdi"] = df["rentab_pct"] - cdi_pct

    st.metric(
        "CDI de referência",
        fmt_pct(cdi_pct),
        help="Benchmark mensal usado para colorir o delta de cada fundo.",
    )

    # Tabela rica com bar inline + delta colorido
    rentab_max = float(max(df["rentab_pct"].max(), cdi_pct * 1.5))

    st.dataframe(
        df.rename(
            columns={
                "ranking": "#",
                "cnpj": "CNPJ",
                "tipo": "Tipo",
                "rentab_pct": "Rentab. mês",
                "delta_cdi": "Δ vs CDI",
                "dias_uteis": "Dias úteis",
                "pl": "PL fim mês",
                "cotistas": "Cotistas",
            }
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn(width="small"),
            "CNPJ": st.column_config.TextColumn(width="medium"),
            "Tipo": st.column_config.TextColumn(width="medium"),
            "Rentab. mês": st.column_config.ProgressColumn(
                format="%.2f%%",
                min_value=0,
                max_value=rentab_max,
                width="medium",
            ),
            "Δ vs CDI": st.column_config.NumberColumn(
                format="%+.2f pp",
                width="small",
            ),
            "Dias úteis": st.column_config.NumberColumn(width="small"),
            "PL fim mês": st.column_config.NumberColumn(
                format="R$ %.0f",
                width="medium",
            ),
            "Cotistas": st.column_config.NumberColumn(format="%d", width="small"),
        },
    )

    st.caption(
        f"Δ vs CDI = rentab. do fundo no mês − CDI do mês ({fmt_pct(cdi_pct)}). "
        f"Valores positivos significam outperformance."
    )


# ---------------------------------------------------------------------------
# PAGINA 3 — Serie historica
# ---------------------------------------------------------------------------


def render_historico() -> None:
    st.title("Série histórica · fundo vs CDI")
    st.caption(
        "Selecione um CNPJ de classe para ver a evolução mensal vs o CDI acumulado. "
        "A área sombreada mostra outperformance (verde) ou underperformance (vermelho)."
    )

    # Selectbox alimentado por CNPJs do mes mais recente (controle de cardinalidade)
    mes_mais_recente = meses_disp[0]
    candidatos = cnpjs_cached(mes_mais_recente)

    cnpj_default = "00.017.024/0001-53" if "00.017.024/0001-53" in candidatos else candidatos[0]
    cnpj = st.selectbox(
        "CNPJ da classe",
        candidatos,
        index=candidatos.index(cnpj_default) if cnpj_default in candidatos else 0,
        help=f"Lista limitada aos {len(candidatos)} primeiros CNPJs ativos em {mes_mais_recente}.",
    )

    df = serie_cached(cnpj)
    if df.empty:
        st.warning("Sem série histórica para esse CNPJ.")
        return

    df = df.copy()
    df["mes"] = pd.to_datetime(df["mes"])
    df = df.sort_values("mes").reset_index(drop=True)
    df["cdi_pct"] = df["mes"].apply(lambda d: cdi_do_mes(d.strftime("%Y-%m-01")))
    df["fundo_acum"] = (1 + df["rentab_pct"] / 100).cumprod() - 1
    df["cdi_acum"] = (1 + df["cdi_pct"] / 100).cumprod() - 1
    df["delta_acum_pp"] = (df["fundo_acum"] - df["cdi_acum"]) * 100

    tipo = str(df["tipo_classe"].iloc[0]) if df["tipo_classe"].notna().any() else "Classe de fundo"
    subclasse = str(df["id_subclasse"].iloc[0]) if df["id_subclasse"].notna().any() else "—"

    st.subheader(tipo)
    st.caption(f"CNPJ `{cnpj}` · Subclasse `{subclasse}` · {len(df)} meses observados.")

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    rentab_acum_pct = float(df["fundo_acum"].iloc[-1] * 100)
    cdi_acum_pct = float(df["cdi_acum"].iloc[-1] * 100)
    melhor = float(df["rentab_pct"].max())
    pior = float(df["rentab_pct"].min())
    vol = float(df["rentab_pct"].std(ddof=0)) if len(df) > 1 else 0.0

    c1.metric(
        "Rentab. acumulada",
        fmt_pct(rentab_acum_pct),
        delta=f"{rentab_acum_pct - cdi_acum_pct:+.2f}pp vs CDI".replace(".", ","),
    )
    c2.metric("Melhor mês", fmt_pct(melhor))
    c3.metric("Pior mês", fmt_pct(pior))
    c4.metric("Volatilidade (σ)", fmt_pct(vol), help="Desvio-padrão da rentab. mensal.")

    # Linha fundo vs CDI (acumulado)
    fig = go.Figure()

    bate_cdi = df["fundo_acum"].iloc[-1] >= df["cdi_acum"].iloc[-1]
    cor_fundo = COLOR_POSITIVE if bate_cdi else COLOR_NEGATIVE

    fig.add_trace(
        go.Scatter(
            x=df["mes"],
            y=df["fundo_acum"] * 100,
            mode="lines+markers",
            name="Fundo (acumulado)",
            line={"color": cor_fundo, "width": 2.5},
            marker={"size": 6},
            hovertemplate="<b>%{x|%b/%Y}</b><br>Acum.: %{y:.2f}pp<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["mes"],
            y=df["cdi_acum"] * 100,
            mode="lines",
            name="CDI (acumulado)",
            line={"color": COLOR_BENCHMARK, "dash": "dash", "width": 2},
            hovertemplate="<b>%{x|%b/%Y}</b><br>CDI acum.: %{y:.2f}pp<extra></extra>",
        )
    )
    aplicar_layout_padrao(fig, height=400, ytitle="Rentab. acumulada (pp)")
    fig.update_xaxes(title="")
    fig.update_yaxes(ticksuffix="pp")
    st.plotly_chart(fig, use_container_width=True)

    # Barras rentab por mes + linha CDI
    st.subheader("Rentabilidade mensal (cada barra = 1 mês)")
    cores_barras = np.where(df["rentab_pct"] >= df["cdi_pct"], COLOR_POSITIVE, COLOR_NEGATIVE)

    fig2 = go.Figure()
    fig2.add_trace(
        go.Bar(
            x=df["mes"],
            y=df["rentab_pct"],
            marker={"color": cores_barras.tolist()},
            name="Fundo",
            hovertemplate="<b>%{x|%b/%Y}</b><br>Rentab.: %{y:.2f}pp<extra></extra>",
        )
    )
    fig2.add_trace(
        go.Scatter(
            x=df["mes"],
            y=df["cdi_pct"],
            mode="lines+markers",
            name="CDI",
            line={"color": COLOR_BENCHMARK, "dash": "dash", "width": 2},
            marker={"size": 5},
            hovertemplate="<b>%{x|%b/%Y}</b><br>CDI: %{y:.2f}pp<extra></extra>",
        )
    )
    aplicar_layout_padrao(fig2, height=340, ytitle="Rentab. do mês (pp)")
    fig2.update_xaxes(title="")
    fig2.update_yaxes(ticksuffix="pp")
    st.plotly_chart(fig2, use_container_width=True)

    with st.expander("Tabela mês a mês"):
        out = df[["mes", "rentab_pct", "cdi_pct", "delta_acum_pp", "pl", "cotistas"]].copy()
        out.columns = ["Mês", "Rentab. fundo", "CDI", "Δ acum. (pp)", "PL", "Cotistas"]
        out["Mês"] = out["Mês"].dt.strftime("%Y-%m")
        st.dataframe(
            out,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Rentab. fundo": st.column_config.NumberColumn(format="%+.2f pp"),
                "CDI": st.column_config.NumberColumn(format="%+.2f pp"),
                "Δ acum. (pp)": st.column_config.NumberColumn(format="%+.2f"),
                "PL": st.column_config.NumberColumn(format="R$ %.0f"),
                "Cotistas": st.column_config.NumberColumn(format="%d"),
            },
        )

    # Sinal sintetico textual (storytelling)
    if bate_cdi:
        delta_pp = (df["fundo_acum"].iloc[-1] - df["cdi_acum"].iloc[-1]) * 100
        st.success(
            f"✅ Esse fundo **bate o CDI** no acumulado dos {len(df)} meses: "
            f"{fmt_pct_signed(delta_pp)} acima do benchmark."
        )
    else:
        delta_pp = (df["fundo_acum"].iloc[-1] - df["cdi_acum"].iloc[-1]) * 100
        st.warning(
            f"⚠️ Esse fundo **não bate o CDI** no acumulado dos {len(df)} meses: "
            f"{fmt_pct_signed(delta_pp)} abaixo do benchmark."
        )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if pagina == "Overview do mês":
    render_overview()
elif pagina == "Top fundos":
    render_top_fundos()
else:
    render_historico()
