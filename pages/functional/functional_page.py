import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
import h3
from h3 import LatLngPoly
from shapely.geometry import Point as ShPoint

from data import (
    poi_groups, neighborhoods_gdf, boundary_shape,
    CENTER_LAT, CENTER_LON, INIT_ZOOM,
    LAT_MIN, LAT_MAX, LON_MIN, LON_MAX,
)


HEX_RES = 9

LABEL_STYLE = {
    "fontSize": "9px", "letterSpacing": "3px",
    "color": "#111111", "marginBottom": "8px", "fontWeight": "500",
}
HEADER_H = "52px"
SIDEBAR_W = "220px"
CHART_W = "460px"

# Веса для популярности
W_RATING = 0.6
W_PHOTOS = 0.2
W_REVIEWS = 0.2

# Режимы карты
MAP_MODES = {
    "quantity": {"label": "Количество POI", "colorscale": [
        [0.0, "rgba(200,230,255,0.05)"],
        [0.5, "rgba(74,144,217,0.40)"],
        [1.0, "rgba(10,50,180,0.70)"],
    ]},
    "diversity": {"label": "Разнообразие POI", "colorscale": [
        [0.0, "rgba(200,230,255,0.05)"],
        [0.5, "rgba(250,176,5,0.40)"],
        [1.0, "rgba(180,100,0,0.70)"],
    ]},
    "popularity": {"label": "Популярность POI", "colorscale": [
        [0.0, "rgba(200,230,255,0.05)"],
        [0.5, "rgba(240,101,149,0.40)"],
        [1.0, "rgba(150,20,80,0.70)"],
    ]},
}


# Подготовка POI с метриками

def _load_rich_poi():
    #Объединяем все POI в один датафрейм с колонками:
    #lat, lon, name, group, rating, photos, reviews, popularity
    
    rows = []
    for gkey, ginfo in poi_groups.items():
        df = ginfo["df"].copy()
        df["group"] = gkey
        df["label"] = ginfo["label"]
        df["color"] = ginfo["color"]

        # rating - берём из GeoJSON если есть, иначе NaN
        if "rating" not in df.columns:
            df["rating"] = np.nan
        else:
            df["rating"] = pd.to_numeric(df["rating"], errors="coerce")

        df["photos"] = df.get("photos",  pd.Series(0, index=df.index))
        df["reviews"] = df.get("reviews", pd.Series(0, index=df.index))

        # Нормализуем каждую метрику в [0,1] по всему датасету группы
        def _norm(col):
            mn, mx = col.min(), col.max()
            if mx == mn:
                return col * 0
            return (col - mn) / (mx - mn)

        r_norm = _norm(df["rating"].fillna(0))
        ph_norm = _norm(df["photos"].fillna(0))
        rew_norm = _norm(df["reviews"].fillna(0))

        df["popularity"] = W_RATING * r_norm + W_PHOTOS * ph_norm + W_REVIEWS * rew_norm

        rows.append(df)

    all_poi = pd.concat(rows, ignore_index=True)
    return all_poi

ALL_POI = _load_rich_poi()


# Гексагональная сетка
def _build_hex_cells():
    poly = LatLngPoly([(LAT_MIN, LON_MIN), (LAT_MAX, LON_MIN),
                       (LAT_MAX, LON_MAX), (LAT_MIN, LON_MAX)])
    all_cells = list(h3.h3shape_to_cells(poly, res=HEX_RES))
    return [
        c for c in all_cells
        if boundary_shape.contains(ShPoint(h3.cell_to_latlng(c)[1], h3.cell_to_latlng(c)[0]))
    ]

HEX_CELLS = _build_hex_cells()


def _compute_hex_values(mode: str) -> dict:
    # Вычисляет значение метрики для каждого гекса
    result = {}
    for cell_id in HEX_CELLS:
        bounds = h3.cell_to_boundary(cell_id)
        la0 = min(p[0] for p in bounds); la1 = max(p[0] for p in bounds)
        lo0 = min(p[1] for p in bounds); lo1 = max(p[1] for p in bounds)

        sub = ALL_POI[
            (ALL_POI.lat >= la0) & (ALL_POI.lat <= la1) &
            (ALL_POI.lon >= lo0) & (ALL_POI.lon <= lo1)
        ]

        if len(sub) == 0:
            result[cell_id] = None
            continue

        if mode == "quantity":
            result[cell_id] = float(len(sub))
        elif mode == "diversity":
            result[cell_id] = float(sub["group"].nunique())
        elif mode == "popularity":
            result[cell_id] = float(sub["popularity"].mean())

    return result

# Кэш
_hex_cache: dict = {}

def _get_hex_values(mode: str) -> dict:
    if mode not in _hex_cache:
        _hex_cache[mode] = _compute_hex_values(mode)
    return _hex_cache[mode]


def _bucket_color(t: float, colorscale: list) -> str:
    for i in range(len(colorscale) - 1):
        t0, c0 = colorscale[i]
        t1, c1 = colorscale[i + 1]
        if t0 <= t <= t1:
            # Линейная интерполяция alpha
            ratio = (t - t0) / (t1 - t0) if t1 > t0 else 0
            # Берём ближайший цвет (упрощение)
            return c1 if ratio > 0.5 else c0
    return colorscale[-1][1]


# Карта
def make_functional_map(mode: str = "quantity", active_groups: list = None) -> go.Figure:
    active_groups = active_groups or list(poi_groups.keys())
    fig = go.Figure()

    values = _get_hex_values(mode)
    colorscale = MAP_MODES[mode]["colorscale"]
    valid_vals = [v for v in values.values() if v is not None]
    vmin = min(valid_vals) if valid_vals else 0
    vmax = max(valid_vals) if valid_vals else 1
    if vmax == vmin: vmax = vmin + 1

    N_BUCKETS = 8
    buckets = {b: {"lats": [], "lons": []} for b in range(N_BUCKETS)}
    empty_lats, empty_lons = [], []

    for cell_id in HEX_CELLS:
        bounds = h3.cell_to_boundary(cell_id)
        lats = [p[0] for p in bounds] + [bounds[0][0], None]
        lons = [p[1] for p in bounds] + [bounds[0][1], None]
        val = values.get(cell_id)
        if val is None:
            empty_lats.extend(lats)
            empty_lons.extend(lons)
        else:
            t = (val - vmin) / (vmax - vmin)
            b = min(int(t * N_BUCKETS), N_BUCKETS - 1)
            buckets[b]["lats"].extend(lats)
            buckets[b]["lons"].extend(lons)

    # Пустые гексы
    if empty_lats:
        fig.add_trace(go.Scattermap(
            lat=empty_lats, lon=empty_lons,
            mode="lines", fill="toself",
            fillcolor="rgba(100,200,120,0.07)",
            line=dict(color="rgba(100,200,120,0.18)", width=0.3),
            hoverinfo="skip", showlegend=False, name="hex_empty",
        ))

    # Заполненные гексы по бакетам
    for b in range(N_BUCKETS):
        if not buckets[b]["lats"]:
            continue
        t_mid = (b + 0.5) / N_BUCKETS
        color = _bucket_color(t_mid, colorscale)
        fig.add_trace(go.Scattermap(
            lat=buckets[b]["lats"], lon=buckets[b]["lons"],
            mode="lines", fill="toself",
            fillcolor=color,
            line=dict(color="rgba(100,160,200,0.15)", width=0.3),
            hoverinfo="skip", showlegend=False, name=f"hex_{b}",
        ))

    # Границы районов
    if neighborhoods_gdf is not None:
        name_col = next(
            (c for c in ["district_name", "name", "название"] if c in neighborhoods_gdf.columns),
            neighborhoods_gdf.columns[0]
        )
        for _, row in neighborhoods_gdf.iterrows():
            geom = row.geometry
            polys = ([geom] if geom.geom_type == "Polygon"
                     else list(geom.geoms) if geom.geom_type == "MultiPolygon" else [])
            lats_p, lons_p = [], []
            for poly in polys:
                xs, ys = poly.exterior.xy
                lons_p.extend(list(xs) + [None])
                lats_p.extend(list(ys) + [None])
            fig.add_trace(go.Scattermap(
                lat=lats_p, lon=lons_p,
                mode="lines",
                line=dict(color="rgba(74,144,217,0.5)", width=1.2),
                hovertemplate=f"<b>{row[name_col]}</b><extra></extra>",
                fill=None, showlegend=False,
            ))

    # POI точки
    for gkey in active_groups:
        g = poi_groups[gkey]
        sub = ALL_POI[ALL_POI["group"] == gkey]
        if len(sub) == 0:
            continue

        hover = []
        for _, r in sub.iterrows():
            rat = f"{r.rating:.1f}" if pd.notna(r.get("rating")) and r.get("rating", 0) > 0 else "-"
            pop = f"{r.popularity:.2f}" if pd.notna(r.get("popularity")) else "-"
            hover.append(
                f"<b>{r['name']}</b><br>"
                f"{g['label']}<br>"
                f"Рейтинг: {rat}<br>"
                f"Популярность: {pop}"
            )

        fig.add_trace(go.Scattermap(
            lat=sub["lat"].tolist(), lon=sub["lon"].tolist(),
            mode="markers",
            marker=dict(size=8, color=g["color"], opacity=1.0),
            text=hover,
            hovertemplate="%{text}<extra></extra>",
            showlegend=False, name=gkey,
        ))

    fig.update_layout(
        map=dict(
            style="carto-positron",
            center=dict(lat=CENTER_LAT, lon=CENTER_LON),
            zoom=INIT_ZOOM,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#FFFFFF",
        uirevision="functional-map",
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            font=dict(color="#111111", family="IBM Plex Sans, sans-serif", size=13),
            bordercolor="#2563EB",
        ),
    )
    return fig

# Графики
def make_poi_by_district_bar():
    # Количество POI по районам (горизонтальный bar)
    if neighborhoods_gdf is None:
        return _empty_fig("Файл районов не найден")

    name_col = next(
        (c for c in ["district_name", "name", "название"] if c in neighborhoods_gdf.columns),
        neighborhoods_gdf.columns[0]
    )

    rows = []
    for _, nbr in neighborhoods_gdf.iterrows():
        for gkey, ginfo in poi_groups.items():
            df = ginfo["df"]
            cnt = sum(
                1 for _, p in df.iterrows()
                if nbr.geometry.contains(ShPoint(p.lon, p.lat))
            )
            rows.append({"district": str(nbr[name_col]), "group": ginfo["label"],
                         "color": ginfo["color"], "count": cnt})

    df_plot = pd.DataFrame(rows)
    districts = df_plot.groupby("district")["count"].sum().sort_values().index.tolist()

    fig = go.Figure()
    for gkey, ginfo in poi_groups.items():
        sub = df_plot[df_plot["group"] == ginfo["label"]]
        sub = sub.set_index("district").reindex(districts).fillna(0)
        fig.add_trace(go.Bar(
            y=districts,
            x=sub["count"],
            name=ginfo["label"],
            orientation="h",
            marker=dict(color=ginfo["color"], opacity=0.85),
            hovertemplate=f"<b>%{{y}}</b><br>{ginfo['label']}: %{{x}}<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin=dict(l=8, r=16, t=36, b=8),
        title=dict(text="POI по районам", font=dict(size=12, color="#111111", family="IBM Plex Sans"), x=0.5, xanchor="center"),
        xaxis=dict(showgrid=True, gridcolor="#EEEEEE", tickfont=dict(color="#111111", size=10), zeroline=False),
        yaxis=dict(tickfont=dict(color="#111111", size=11, family="IBM Plex Sans"), showgrid=False),
        legend=dict(font=dict(color="#111111", size=10), bgcolor="rgba(0,0,0,0)"),
        bargap=0.25,
    )
    return fig


def make_diversity_bar():
    # Разнообразие POI по районам
    if neighborhoods_gdf is None:
        return _empty_fig("Файл районов не найден")

    name_col = next(
        (c for c in ["district_name", "name", "название"] if c in neighborhoods_gdf.columns),
        neighborhoods_gdf.columns[0]
    )

    rows = []
    for _, nbr in neighborhoods_gdf.iterrows():
        types_present = set()
        for gkey in poi_groups:
            df = poi_groups[gkey]["df"]
            if any(nbr.geometry.contains(ShPoint(p.lon, p.lat)) for _, p in df.iterrows()):
                types_present.add(gkey)
        rows.append({"district": str(nbr[name_col]), "diversity": len(types_present)})

    df_plot = pd.DataFrame(rows).sort_values("diversity", ascending=True)
    max_d = max(df_plot["diversity"].max(), 1)
    colors = [f"rgba(250,176,5,{0.25 + 0.65*(v/max_d):.2f})" for v in df_plot["diversity"]]

    fig = go.Figure(go.Bar(
        y=df_plot["district"], x=df_plot["diversity"],
        orientation="h",
        marker=dict(color=colors, line=dict(color="rgba(250,176,5,0.6)", width=0.8)),
        text=df_plot["diversity"],
        textposition="outside",
        textfont=dict(color="#111111", size=11),
        hovertemplate="<b>%{y}</b><br>Типов POI: %{x}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin=dict(l=8, r=32, t=36, b=8),
        title=dict(text="Разнообразие POI по районам", font=dict(size=12, color="#111111", family="IBM Plex Sans"), x=0.5, xanchor="center"),
        xaxis=dict(showgrid=True, gridcolor="#EEEEEE", tickfont=dict(color="#111111", size=10),
                   zeroline=False, dtick=1, range=[0, len(poi_groups) + 0.5]),
        yaxis=dict(tickfont=dict(color="#111111", size=11, family="IBM Plex Sans"), showgrid=False),
        bargap=0.3,
    )
    return fig


def make_top_rated_bar():
    # Топ POI по рейтингу (горизонтальный bar, топ-10)
    sub = ALL_POI[ALL_POI["rating"].notna() & (ALL_POI["rating"] > 0)].copy()

    if len(sub) == 0:
        return _empty_fig("Нет данных о рейтинге")

    sub = sub.nlargest(10, "rating")[["name", "rating", "label", "color"]].reset_index(drop=True)
    sub = sub.sort_values("rating", ascending=True)

    fig = go.Figure(go.Bar(
        y=sub["name"],
        x=sub["rating"],
        orientation="h",
        marker=dict(
            color=sub["color"].tolist(),
            opacity=0.85,
            line=dict(color=sub["color"].tolist(), width=0.8),
        ),
        text=[f"{r:.1f} ★" for r in sub["rating"]],
        textposition="outside",
        textfont=dict(color="#111111", size=11, family="IBM Plex Sans"),
        customdata=sub["label"].tolist(),
        hovertemplate="<b>%{y}</b><br>%{customdata}<br>Рейтинг: %{x:.1f}<extra></extra>",
    ))

    fig.update_layout(
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin=dict(l=8, r=48, t=36, b=8),
        title=dict(
            text="Топ-10 по рейтингу",
            font=dict(size=12, color="#111111", family="IBM Plex Sans"),
            x=0.5, xanchor="center",
        ),
        xaxis=dict(
            showgrid=True, gridcolor="#EEEEEE",
            tickfont=dict(color="#111111", size=10),
            zeroline=False, range=[0, 5.5],
        ),
        yaxis=dict(
            tickfont=dict(color="#111111", size=11, family="IBM Plex Sans"),
            showgrid=False,
        ),
        bargap=0.3,
    )
    return fig


# layout
def functional_layout():
    return html.Div([

        # Боковая панель
        html.Div([
            html.Div("РЕЖИМ КАРТЫ", style=LABEL_STYLE),
            dcc.RadioItems(
                id="func-map-mode",
                options=[
                    {"label": html.Span(MAP_MODES[k]["label"],
                                        style={"fontSize": "12px", "color": "#111111"}),
                     "value": k}
                    for k in MAP_MODES
                ],
                value="quantity",
                inputStyle={"accentColor": "#2563EB", "marginRight": "8px", "cursor": "pointer"},
                labelStyle={"display": "flex", "alignItems": "center",
                            "padding": "4px 0", "cursor": "pointer"},
                style={"marginBottom": "16px"},
            ),

            # Легенда градиента (меняется при смене режима)
            html.Div(id="func-hex-legend", style={"marginBottom": "16px"}),

            html.Div(style={"borderTop": "1px solid #E2E8F0", "margin": "12px 0"}),

            html.Div("СЛОИ ОБЪЕКТОВ", style=LABEL_STYLE),
            dcc.Checklist(
                id="func-poi-filter",
                options=[{
                    "label": html.Span([
                        html.Div(style={
                            "width": "10px", "height": "10px", "borderRadius": "50%",
                            "backgroundColor": poi_groups[k]["color"],
                            "marginRight": "8px", "flexShrink": "0",
                        }),
                        html.Span(poi_groups[k]["label"],
                                  style={"fontSize": "12px", "color": "#333333"}),
                    ], style={"display": "flex", "alignItems": "center", "padding": "3px 0"}),
                    "value": k,
                } for k in poi_groups],
                value=list(poi_groups.keys()),
                inputStyle={"accentColor": "#2563EB", "marginRight": "8px",
                            "cursor": "pointer", "width": "13px", "height": "13px"},
                labelStyle={"display": "flex", "alignItems": "center", "cursor": "pointer"},
                style={"marginBottom": "16px"},
            ),

            html.Div(style={"borderTop": "1px solid #E2E8F0", "margin": "12px 0"}),

            # Суммарная статистика
            html.Div("ВСЕГО POI", style=LABEL_STYLE),
            html.Div([
                html.Span(str(len(ALL_POI)),
                          style={"fontSize": "28px", "fontWeight": "600", "color": "#111111"}),
                html.Span(" объектов",
                          style={"color": "#111111", "fontSize": "12px", "marginLeft": "4px"}),
            ], style={"marginBottom": "8px"}),
            html.Div([
                html.Div([
                    html.Div(style={
                        "width": "8px", "height": "8px", "borderRadius": "50%",
                        "backgroundColor": poi_groups[k]["color"],
                        "marginRight": "6px", "flexShrink": "0",
                    }),
                    html.Span(poi_groups[k]["label"],
                              style={"color": "#111111", "fontSize": "11px", "flex": "1"}),
                    html.Span(str(len(poi_groups[k]["df"])),
                              style={"color": "#111111", "fontSize": "11px"}),
                ], style={"display": "flex", "alignItems": "center",
                          "padding": "3px 0", "borderBottom": "1px solid #F5F7FA"})
                for k in poi_groups
            ]),

        ], style={
            "position": "fixed", "top": HEADER_H, "left": 0,
            "width": SIDEBAR_W,
            "height": f"calc(100vh - {HEADER_H})",
            "backgroundColor": "#FFFFFF",
            "padding": "18px 14px",
            "zIndex": 1000, "overflowY": "auto",
            "borderRight": "1px solid #E2E8F0",
            "boxSizing": "border-box",
        }),

        # Карта
        html.Div([
            dcc.Graph(
                id="functional-map",
                figure=make_functional_map("quantity"),
                style={"height": f"calc(100vh - {HEADER_H})", "width": "100%"},
                config={"scrollZoom": True, "displayModeBar": False},
            )
        ], style={
            "marginLeft": SIDEBAR_W,
            "marginRight": CHART_W,
            "height": f"calc(100vh - {HEADER_H})",
        }),

        # Правая панель - графики
        html.Div([
            html.Div(style={"height": "14px"}),

            html.Div("POI ПО РАЙОНАМ", style={**LABEL_STYLE, "paddingLeft": "4px"}),
            dcc.Graph(
                id="func-district-bar",
                figure=make_poi_by_district_bar(),
                style={"height": "240px"},
                config={"displayModeBar": False},
            ),

            html.Div(style={"borderTop": "1px solid #E2E8F0", "margin": "4px 12px"}),

            html.Div("РАЗНООБРАЗИЕ ПО РАЙОНАМ", style={**LABEL_STYLE, "paddingLeft": "4px", "paddingTop": "12px"}),
            dcc.Graph(
                id="func-diversity-bar",
                figure=make_diversity_bar(),
                style={"height": "220px"},
                config={"displayModeBar": False},
            ),

            html.Div(style={"borderTop": "1px solid #E2E8F0", "margin": "4px 12px"}),

            html.Div("ТОП-10 ПО РЕЙТИНГУ", style={**LABEL_STYLE, "paddingLeft": "4px", "paddingTop": "12px"}),
            dcc.Graph(
                id="func-popularity-scatter",
                figure=make_top_rated_bar(),
                style={"height": "300px"},
                config={"displayModeBar": False},
            ),

        ], style={
            "position": "fixed", "top": HEADER_H, "right": 0,
            "width": CHART_W,
            "height": f"calc(100vh - {HEADER_H})",
            "backgroundColor": "#FFFFFF",
            "borderLeft": "1px solid #E2E8F0",
            "overflowY": "auto",
            "zIndex": 1000,
        }),
    ])


def _empty_fig(msg="Нет данных"):
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin=dict(l=8, r=8, t=8, b=8),
        annotations=[dict(text=msg, x=0.5, y=0.5, showarrow=False,
                          font=dict(color="#111111", size=12))],
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig