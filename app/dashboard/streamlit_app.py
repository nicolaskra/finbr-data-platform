"""Streamlit dashboard — consome a finbr API (modo `api`) ou DuckDB direto (modo `duckdb`).

Duas paginas:
- Top Fundos do mes (tabela + grafico de barras)
- Serie historica de uma classe (linha)

Modos:
- `FINBR_MODE=api` (default): consome FastAPI em `FINBR_API_URL`. Usado no Docker local.
- `FINBR_MODE=duckdb`: le `data/warehouse/finbr.duckdb` direto. Usado no Streamlit Cloud
  (free hosting nao permite subir o container da API).
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

FINBR_MODE = os.getenv("FINBR_MODE", "api").lower()
API_URL = os.getenv("FINBR_API_URL", "http://localhost:8000")
DEFAULT_MES = os.getenv("FINBR_DEFAULT_MES", "2026-04-01")
DUCKDB_PATH = os.getenv("FINBR_DUCKDB_PATH", "data/warehouse/finbr.duckdb")

st.set_page_config(
    page_title="finbr · Dashboard",
    page_icon="📊",
    layout="wide",
)


# ----------------------------------------------------------------------
# DuckDB helpers (modo standalone)
# ----------------------------------------------------------------------


@st.cache_resource
def _get_duckdb_conn():
    """Conexao read-only ao warehouse. Cacheada por sessao."""
    import duckdb  # import local para nao exigir duckdb no modo api

    path = Path(DUCKDB_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"Warehouse nao encontrado em {path.resolve()}. "
            f"No Streamlit Cloud, certifique-se que o arquivo foi commitado no repo."
        )
    return duckdb.connect(str(path), read_only=True)


def _fetch_health_duckdb() -> dict:
    con = _get_duckdb_conn()
    path = Path(DUCKDB_PATH)
    size_mb = round(path.stat().st_size / (1024 * 1024), 2)
    rows_fct = con.execute(
        "select count(*) from main_core.fct_fundo_rentabilidade_mensal"
    ).fetchone()[0]
    rows_dim = con.execute("select count(*) from main_core.dim_fundo_classe").fetchone()[0]
    return {
        "status": "ok",
        "warehouse_path": str(path),
        "warehouse_size_mb": size_mb,
        "rows_dim": rows_dim,
        "rows_fct": rows_fct,
    }


def _fetch_top_fundos_duckdb(mes: str, limit: int) -> dict:
    con = _get_duckdb_conn()
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

    fundos = [
        {
            "mes": str(row["mes"]),
            "ranking_mes": int(row["ranking_mes"]),
            "cnpj_classe": row["cnpj_classe"],
            "tipo_classe": row["tipo_classe"],
            "rentabilidade_mes_pct": float(row["rentabilidade_mes_pct"]),
            "dias_uteis": int(row["dias_uteis"]),
            "vl_patrim_liq_fim_mes": float(row["vl_patrim_liq_fim_mes"]),
            "nr_cotistas_fim_mes": int(row["nr_cotistas_fim_mes"]),
        }
        for _, row in df.iterrows()
    ]
    return {"mes": mes, "total": len(fundos), "fundos": fundos}


def _fetch_historico_duckdb(cnpj: str) -> dict | None:
    con = _get_duckdb_conn()
    df = con.execute(
        """
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
        order by mes
        """,
        [cnpj],
    ).df()

    if df.empty:
        return None

    # Pega 1a subclasse caso haja multiplas (mesma logica da API)
    primeira = df["id_subclasse"].iloc[0]
    df = df[df["id_subclasse"] == primeira]

    serie = [
        {
            "mes": str(row["mes"]),
            "rentabilidade_mes": float(row["rentabilidade_mes"]),
            "rentabilidade_mes_pct": float(row["rentabilidade_mes"]) * 100,
            "dias_uteis": int(row["dias_uteis"]),
            "vl_patrim_liq_fim_mes": (
                float(row["vl_patrim_liq_fim_mes"])
                if row["vl_patrim_liq_fim_mes"] is not None
                else None
            ),
            "nr_cotistas_fim_mes": (
                int(row["nr_cotistas_fim_mes"]) if row["nr_cotistas_fim_mes"] is not None else None
            ),
        }
        for _, row in df.iterrows()
    ]
    return {
        "cnpj_classe": df["cnpj_classe"].iloc[0],
        "id_subclasse": df["id_subclasse"].iloc[0],
        "tipo_classe": df["tipo_classe"].iloc[0],
        "serie": serie,
    }


# ----------------------------------------------------------------------
# API helpers (modo api)
# ----------------------------------------------------------------------


def _fetch_health_api() -> dict:
    import requests

    r = requests.get(f"{API_URL}/health", timeout=10)
    r.raise_for_status()
    return r.json()


def _fetch_top_fundos_api(mes: str, limit: int) -> dict:
    import requests

    r = requests.get(
        f"{API_URL}/analytics/top-fundos",
        params={"mes": mes, "limit": limit},
        timeout=10,
    )
    if r.status_code == 404:
        return {"mes": mes, "total": 0, "fundos": []}
    r.raise_for_status()
    return r.json()


def _fetch_historico_api(cnpj: str) -> dict | None:
    import requests

    r = requests.get(
        f"{API_URL}/fundos/rentabilidade",
        params={"cnpj": cnpj},
        timeout=10,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


# ----------------------------------------------------------------------
# Dispatcher (cacheado)
# ----------------------------------------------------------------------


@st.cache_data(ttl=300)
def fetch_health() -> dict:
    if FINBR_MODE == "duckdb":
        return _fetch_health_duckdb()
    return _fetch_health_api()


@st.cache_data(ttl=300)
def fetch_top_fundos(mes: str, limit: int = 10) -> dict:
    if FINBR_MODE == "duckdb":
        return _fetch_top_fundos_duckdb(mes, limit)
    return _fetch_top_fundos_api(mes, limit)


@st.cache_data(ttl=300)
def fetch_historico(cnpj: str) -> dict | None:
    if FINBR_MODE == "duckdb":
        return _fetch_historico_duckdb(cnpj)
    return _fetch_historico_api(cnpj)


# ----------------------------------------------------------------------
# Sidebar — status + navegacao
# ----------------------------------------------------------------------

st.sidebar.title("📊 finbr")
st.sidebar.caption("CVM · Fundos · Rentabilidade")

pagina = st.sidebar.radio(
    "Navegacao",
    ["🏆 Top fundos", "📈 Serie historica"],
)

st.sidebar.divider()
st.sidebar.subheader("Status warehouse")
try:
    h = fetch_health()
    label = "DuckDB OK" if FINBR_MODE == "duckdb" else "API OK"
    st.sidebar.success(label)
    st.sidebar.metric("Linhas (fct)", f"{h['rows_fct']:,}")
    st.sidebar.metric("Classes (dim)", f"{h['rows_dim']:,}")
    st.sidebar.metric("Warehouse", f"{h['warehouse_size_mb']} MB")
except Exception as exc:
    backend = "DuckDB" if FINBR_MODE == "duckdb" else "API"
    st.sidebar.error(f"{backend} indisponivel: {exc}")
    st.stop()

st.sidebar.divider()
if FINBR_MODE == "duckdb":
    st.sidebar.caption(f"Mode: `duckdb`  ·  `{DUCKDB_PATH}`")
else:
    st.sidebar.caption(f"Mode: `api`  ·  `{API_URL}`")
st.sidebar.caption("[Source · GitHub](https://github.com/nicolaskra/finbr-data-platform)")


# ----------------------------------------------------------------------
# Pagina: Top Fundos
# ----------------------------------------------------------------------

if pagina == "🏆 Top fundos":
    st.title("🏆 Top Fundos por Rentabilidade Mensal")
    st.caption(
        "Filtros aplicados no warehouse: **PL >= R\\$ 1M** e **>= 15 dias uteis** "
        "(reduz outliers de fundos micro / novos)."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        mes_input = st.text_input(
            "Mes (formato YYYY-MM-01)",
            value=DEFAULT_MES,
            help="Primeiro dia do mes desejado",
        )
    with col2:
        limit = st.slider("Top N", min_value=5, max_value=50, value=10, step=5)

    data = fetch_top_fundos(mes_input, limit=limit)

    if not data["fundos"]:
        st.warning(f"Sem dados para o mes {mes_input}.")
    else:
        df = pd.DataFrame(data["fundos"])
        df["rentabilidade_mes_pct"] = df["rentabilidade_mes_pct"].round(2)
        df["vl_patrim_liq_fim_mes_R$"] = df["vl_patrim_liq_fim_mes"].apply(lambda v: f"R$ {v:,.0f}")

        st.subheader(f"Top {len(df)} · {mes_input}")

        # Grafico de barras
        st.bar_chart(
            df.set_index("cnpj_classe")["rentabilidade_mes_pct"],
            height=350,
            use_container_width=True,
            y_label="Rentabilidade do mes (%)",
        )

        # Tabela
        st.dataframe(
            df[
                [
                    "ranking_mes",
                    "cnpj_classe",
                    "tipo_classe",
                    "rentabilidade_mes_pct",
                    "dias_uteis",
                    "vl_patrim_liq_fim_mes_R$",
                    "nr_cotistas_fim_mes",
                ]
            ].rename(
                columns={
                    "ranking_mes": "#",
                    "cnpj_classe": "CNPJ",
                    "tipo_classe": "Tipo",
                    "rentabilidade_mes_pct": "Rentab %",
                    "dias_uteis": "Dias uteis",
                    "vl_patrim_liq_fim_mes_R$": "PL fim mes",
                    "nr_cotistas_fim_mes": "Cotistas",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


# ----------------------------------------------------------------------
# Pagina: Serie historica
# ----------------------------------------------------------------------

else:
    st.title("📈 Serie Historica de Rentabilidade")
    st.caption("Informe um CNPJ de classe de fundo (formato XX.XXX.XXX/XXXX-XX).")

    cnpj_input = st.text_input(
        "CNPJ da classe",
        value="00.017.024/0001-53",
        help="Exemplo: 00.017.024/0001-53",
    )

    if st.button("Buscar", type="primary"):
        data = fetch_historico(cnpj_input)
        if data is None:
            st.error(f"Classe {cnpj_input} nao encontrada.")
        else:
            st.subheader(data.get("tipo_classe") or "Classe de fundo")
            st.caption(f"CNPJ: `{data['cnpj_classe']}`  ·  Subclasse: `{data['id_subclasse']}`")

            df = pd.DataFrame(data["serie"])
            if df.empty:
                st.warning("Serie historica vazia.")
            else:
                df["mes"] = pd.to_datetime(df["mes"])
                df = df.sort_values("mes")

                col1, col2, col3 = st.columns(3)
                col1.metric("Meses observados", len(df))
                col2.metric(
                    "Rentab acumulada %",
                    f"{((1 + df['rentabilidade_mes']).prod() - 1) * 100:.2f}%",
                )
                col3.metric(
                    "Melhor mes %",
                    f"{df['rentabilidade_mes_pct'].max():.2f}%",
                )

                st.line_chart(
                    df.set_index("mes")["rentabilidade_mes_pct"],
                    use_container_width=True,
                    y_label="Rentabilidade mensal (%)",
                )

                with st.expander("Dados brutos"):
                    st.dataframe(df, use_container_width=True, hide_index=True)
