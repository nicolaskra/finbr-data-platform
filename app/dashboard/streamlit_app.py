"""Streamlit dashboard — consome a finbr API.

Duas paginas:
- Top Fundos do mes (tabela + grafico de barras)
- Serie historica de uma classe (linha)
"""

from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

API_URL = os.getenv("FINBR_API_URL", "http://localhost:8000")
DEFAULT_MES = os.getenv("FINBR_DEFAULT_MES", "2026-04-01")

st.set_page_config(
    page_title="finbr · Dashboard",
    page_icon="📊",
    layout="wide",
)


# ----------------------------------------------------------------------
# API helpers (cacheadas)
# ----------------------------------------------------------------------


@st.cache_data(ttl=300)
def fetch_health() -> dict:
    r = requests.get(f"{API_URL}/health", timeout=10)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=300)
def fetch_top_fundos(mes: str, limit: int = 10) -> dict:
    r = requests.get(
        f"{API_URL}/analytics/top-fundos",
        params={"mes": mes, "limit": limit},
        timeout=10,
    )
    if r.status_code == 404:
        return {"mes": mes, "total": 0, "fundos": []}
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=300)
def fetch_historico(cnpj: str) -> dict | None:
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
    st.sidebar.success("API OK")
    st.sidebar.metric("Linhas (fct)", f"{h['rows_fct']:,}")
    st.sidebar.metric("Classes (dim)", f"{h['rows_dim']:,}")
    st.sidebar.metric("Warehouse", f"{h['warehouse_size_mb']} MB")
except Exception as exc:
    st.sidebar.error(f"API indisponivel: {exc}")
    st.stop()

st.sidebar.divider()
st.sidebar.caption(f"API: `{API_URL}`")
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
