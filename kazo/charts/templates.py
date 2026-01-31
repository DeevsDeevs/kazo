from __future__ import annotations

import tempfile
from typing import Any

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

from kazo.currency import currency_symbol

THEME: dict[str, Any] = {
    "colors": {
        "palette": [
            "#4C72B0",
            "#55A868",
            "#C44E52",
            "#8172B3",
            "#CCB974",
            "#64B5CD",
            "#E5AE38",
            "#6D904F",
            "#8B8B8B",
            "#D65F5F",
            "#B47CC7",
            "#C4AD66",
            "#77BEDB",
            "#92C6FF",
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


def _fmt_amount(value: float, cur: str) -> str:
    sym = currency_symbol(cur)
    prefix_symbols = {"\u20ac", "$", "\u00a3", "\u00a5", "\u20b9", "\u20a9", "\u20ba", "\u20aa", "\u20b1"}
    if sym in prefix_symbols:
        if value >= 1000:
            return f"{sym}{value:,.0f}"
        return f"{sym}{value:.0f}" if value == int(value) else f"{sym}{value:.2f}"
    if value >= 1000:
        return f"{value:,.0f} {sym}"
    return f"{value:.0f} {sym}" if value == int(value) else f"{value:.2f} {sym}"


def _base_layout() -> dict[str, Any]:
    return {
        "margin": THEME["margin"],
        "width": THEME["size"]["width"],
        "height": THEME["size"]["height"],
    }


def _save(fig: go.Figure) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)  # noqa: SIM115
    tmp.close()
    fig.write_image(tmp.name, scale=THEME["size"]["scale"])
    return tmp.name


async def spending_by_category_chart(data: list[dict[str, Any]], cur: str = "EUR") -> str | None:
    if not data:
        return None

    categories = [row["category"] or "Other" for row in data]
    totals: list[float] = [row["total"] for row in data]
    palette = THEME["colors"]["palette"]

    if len(categories) <= PIE_CATEGORY_THRESHOLD:
        fig = go.Figure(
            go.Pie(
                labels=categories,
                values=totals,
                marker=dict(colors=palette[: len(categories)]),
                textinfo="label+percent",
                texttemplate="%{label}<br>%{percent:.0%}",
                hovertemplate="%{label}: %{value:,.2f} " + cur + "<extra></extra>",
                hole=0.35,
                sort=False,
            )
        )
        fig.update_layout(
            **_base_layout(),
            title="Spending by Category",
            showlegend=False,
        )
        fig.add_annotation(
            text=_fmt_amount(sum(totals), cur),
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=18, color=THEME["colors"]["text"]),
        )
    else:
        fig = go.Figure(
            go.Bar(
                x=totals,
                y=categories,
                orientation="h",
                marker_color=palette[: len(categories)],
                text=[_fmt_amount(v, cur) for v in totals],
                textposition="outside",
                hovertemplate="%{y}: %{x:,.2f} " + cur + "<extra></extra>",
            )
        )
        fig.update_layout(
            **_base_layout(),
            title="Spending by Category",
            xaxis_title=cur,
        )
        fig.update_yaxes(autorange="reversed")

    return _save(fig)


async def monthly_trend_chart(data: list[dict[str, Any]], cur: str = "EUR") -> str | None:
    if not data:
        return None

    months = [row["month"] for row in data]
    totals: list[float] = [row["total"] for row in data]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=months,
            y=totals,
            marker_color=THEME["colors"]["primary"],
            text=[_fmt_amount(v, cur) for v in totals],
            textposition="outside",
            hovertemplate="%{x}: %{y:,.2f} " + cur + "<extra></extra>",
            name="Monthly total",
        )
    )

    if len(totals) >= 3:
        x_idx = list(range(len(totals)))
        z = np.polyfit(x_idx, totals, 1)
        trend = np.polyval(z, x_idx)
        fig.add_trace(
            go.Scatter(
                x=months,
                y=trend.tolist(),
                mode="lines",
                line=dict(color=THEME["colors"]["trend_line"], width=2, dash="dash"),
                name="Trend",
                hoverinfo="skip",
            )
        )

    fig.update_layout(
        **_base_layout(),
        title="Monthly Spending",
        yaxis_title=cur,
        showlegend=len(totals) >= 3,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return _save(fig)


async def daily_spending_chart(data: list[dict[str, Any]], cur: str = "EUR", budget: float | None = None) -> str | None:
    if not data:
        return None

    sym = currency_symbol(cur)
    days = [row["expense_date"] for row in data]
    totals: list[float] = [row["total"] for row in data]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=days,
            y=totals,
            marker_color=THEME["colors"]["secondary"],
            hovertemplate="%{x}: %{y:,.2f} " + cur + "<extra></extra>",
            name="Daily total",
        )
    )

    # Cumulative spending overlay
    cumulative = []
    running = 0.0
    for t in totals:
        running += t
        cumulative.append(running)
    fig.add_trace(
        go.Scatter(
            x=days,
            y=cumulative,
            mode="lines+markers",
            line=dict(color=THEME["colors"]["primary"], width=2),
            marker=dict(size=4),
            name="Cumulative",
            yaxis="y2",
            hovertemplate="%{x}: %{y:,.2f} " + cur + "<extra></extra>",
        )
    )

    if len(totals) >= 5:
        x_idx = list(range(len(totals)))
        z = np.polyfit(x_idx, totals, 1)
        trend = np.polyval(z, x_idx)
        fig.add_trace(
            go.Scatter(
                x=days,
                y=trend.tolist(),
                mode="lines",
                line=dict(color=THEME["colors"]["trend_line"], width=2, dash="dash"),
                name="Trend",
                hoverinfo="skip",
            )
        )

    layout_kwargs: dict[str, Any] = {
        **_base_layout(),
        "title": "Daily Spending",
        "yaxis_title": cur,
        "yaxis_tickprefix": sym if len(sym) <= 1 else "",
        "yaxis2": dict(
            title="Cumulative",
            overlaying="y",
            side="right",
            showgrid=False,
            tickprefix=sym if len(sym) <= 1 else "",
        ),
        "showlegend": True,
        "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    }

    if budget is not None and budget > 0:
        fig.add_hline(
            y=budget,
            line_dash="dot",
            line_color=THEME["colors"]["trend_line"],
            annotation_text=f"Budget: {_fmt_amount(budget, cur)}",
            annotation_position="top left",
            yref="y2",
        )

    fig.update_layout(**layout_kwargs)

    return _save(fig)
