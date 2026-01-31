from __future__ import annotations

import tempfile
from typing import Any

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

THEME: dict[str, Any] = {
    "colors": {
        "palette": [
            "#4C72B0", "#55A868", "#C44E52", "#8172B3", "#CCB974",
            "#64B5CD", "#E5AE38", "#6D904F", "#8B8B8B", "#D65F5F",
            "#B47CC7", "#C4AD66", "#77BEDB", "#92C6FF",
        ],
        "primary": "#4C72B0",
        "secondary": "#55A868",
        "trend_line": "#C44E52",
        "grid": "#E5E5E5",
        "background": "#FAFAFA",
        "text": "#2D3436",
        "muted": "#636E72",
    },
    "font": {
        "family": "Inter, sans-serif",
        "size": 13,
        "title_size": 16,
    },
    "size": {
        "width": 800,
        "height": 500,
        "scale": 2,
    },
    "margin": {"l": 60, "r": 30, "t": 60, "b": 50},
}

PIE_CATEGORY_THRESHOLD = 6

_custom_template = pio.templates["plotly_white"]
_custom_template.layout.font = dict(
    family=THEME["font"]["family"],
    size=THEME["font"]["size"],
    color=THEME["colors"]["text"],
)
_custom_template.layout.title = dict(
    font=dict(size=THEME["font"]["title_size"], color=THEME["colors"]["text"]),
    x=0.5,
    xanchor="center",
)
_custom_template.layout.plot_bgcolor = THEME["colors"]["background"]
_custom_template.layout.xaxis = dict(gridcolor=THEME["colors"]["grid"])
_custom_template.layout.yaxis = dict(gridcolor=THEME["colors"]["grid"])
pio.templates["kazo"] = _custom_template
pio.templates.default = "kazo"


def _fmt_eur(value: float) -> str:
    if value >= 1000:
        return f"\u20ac{value:,.0f}"
    return f"\u20ac{value:.0f}" if value == int(value) else f"\u20ac{value:.2f}"


def _base_layout() -> dict[str, Any]:
    return {
        "margin": THEME["margin"],
        "width": THEME["size"]["width"],
        "height": THEME["size"]["height"],
    }


def _save(fig: go.Figure) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    fig.write_image(tmp.name, scale=THEME["size"]["scale"])
    return tmp.name


async def spending_by_category_chart(data: list[dict[str, Any]]) -> str | None:
    if not data:
        return None

    categories = [row["category"] or "Other" for row in data]
    totals: list[float] = [row["total"] for row in data]
    palette = THEME["colors"]["palette"]

    if len(categories) <= PIE_CATEGORY_THRESHOLD:
        fig = go.Figure(go.Pie(
            labels=categories,
            values=totals,
            marker=dict(colors=palette[: len(categories)]),
            textinfo="label+percent",
            texttemplate="%{label}<br>%{percent:.0%}",
            hovertemplate="%{label}: %{value:,.2f} EUR<extra></extra>",
            hole=0.35,
            sort=False,
        ))
        fig.update_layout(
            **_base_layout(),
            title="Spending by Category",
            showlegend=False,
        )
        fig.add_annotation(
            text=_fmt_eur(sum(totals)),
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=18, color=THEME["colors"]["text"]),
        )
    else:
        fig = go.Figure(go.Bar(
            x=totals,
            y=categories,
            orientation="h",
            marker_color=palette[: len(categories)],
            text=[_fmt_eur(v) for v in totals],
            textposition="outside",
            hovertemplate="%{y}: %{x:,.2f} EUR<extra></extra>",
        ))
        fig.update_layout(
            **_base_layout(),
            title="Spending by Category",
            xaxis_title="EUR",
        )
        fig.update_yaxes(autorange="reversed")

    return _save(fig)


async def monthly_trend_chart(data: list[dict[str, Any]]) -> str | None:
    if not data:
        return None

    months = [row["month"] for row in data]
    totals: list[float] = [row["total"] for row in data]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=months,
        y=totals,
        marker_color=THEME["colors"]["primary"],
        text=[_fmt_eur(v) for v in totals],
        textposition="outside",
        hovertemplate="%{x}: %{y:,.2f} EUR<extra></extra>",
        name="Monthly total",
    ))

    if len(totals) >= 3:
        x_idx = list(range(len(totals)))
        z = np.polyfit(x_idx, totals, 1)
        trend = np.polyval(z, x_idx)
        fig.add_trace(go.Scatter(
            x=months,
            y=trend.tolist(),
            mode="lines",
            line=dict(color=THEME["colors"]["trend_line"], width=2, dash="dash"),
            name="Trend",
            hoverinfo="skip",
        ))

    fig.update_layout(
        **_base_layout(),
        title="Monthly Spending",
        yaxis_title="EUR",
        showlegend=len(totals) >= 3,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return _save(fig)


async def daily_spending_chart(data: list[dict[str, Any]]) -> str | None:
    if not data:
        return None

    days = [row["expense_date"] for row in data]
    totals: list[float] = [row["total"] for row in data]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=days,
        y=totals,
        marker_color=THEME["colors"]["secondary"],
        hovertemplate="%{x}: %{y:,.2f} EUR<extra></extra>",
        name="Daily total",
    ))

    if len(totals) >= 5:
        x_idx = list(range(len(totals)))
        z = np.polyfit(x_idx, totals, 1)
        trend = np.polyval(z, x_idx)
        fig.add_trace(go.Scatter(
            x=days,
            y=trend.tolist(),
            mode="lines",
            line=dict(color=THEME["colors"]["trend_line"], width=2, dash="dash"),
            name="Trend",
            hoverinfo="skip",
        ))

    fig.update_layout(
        **_base_layout(),
        title="Daily Spending",
        yaxis_title="EUR",
        yaxis_tickprefix="\u20ac",
        showlegend=len(totals) >= 5,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return _save(fig)
