"""Helpers Plotly: layout padrao do dashboard, formatadores de eixo, paletas."""

from __future__ import annotations

import plotly.graph_objects as go

from .constants import COLOR_BG_SOFT, COLOR_NEUTRAL, COLOR_PRIMARY


def aplicar_layout_padrao(fig: go.Figure, *, height: int = 360, ytitle: str = "") -> go.Figure:
    """Layout sobrio: sem grade pesada, margens enxutas, fonte coerente com o tema."""
    fig.update_layout(
        height=height,
        margin={"l": 50, "r": 24, "t": 36, "b": 40},
        plot_bgcolor=COLOR_BG_SOFT,
        paper_bgcolor="white",
        font={"family": "Inter, system-ui, sans-serif", "color": COLOR_PRIMARY, "size": 13},
        title={"font": {"size": 16, "color": COLOR_PRIMARY}, "x": 0, "xanchor": "left"},
        xaxis={
            "showgrid": False,
            "linecolor": COLOR_NEUTRAL,
            "tickfont": {"color": COLOR_NEUTRAL},
        },
        yaxis={
            "title": ytitle,
            "gridcolor": "#E5E7EB",
            "zerolinecolor": COLOR_NEUTRAL,
            "tickfont": {"color": COLOR_NEUTRAL},
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "font": {"color": COLOR_PRIMARY},
        },
        hoverlabel={"bgcolor": "white", "font_color": COLOR_PRIMARY},
    )
    return fig
