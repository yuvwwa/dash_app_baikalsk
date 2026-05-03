import numpy as np
import plotly.graph_objects as go
from dash import dcc, html
import h3
from h3 import LatLngPoly
from shapely.geometry import Point as _ShPoint

from data import (
    buildings_gdf, BUILDING_GROUPS,
    CENTER_LAT, CENTER_LON, INIT_ZOOM,
    boundary_gdf,
)

# Вспомогательная функция цвета с прозрачностью
def hex_to_rgba(hex_color, alpha=0.75):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# Карта зданий
def make_buildings_map(active_groups=None, hex_mode="density"):
    # Полигоны зданий + гексагональная сетка плотности застройки
    active_groups = active_groups or list(BUILDING_GROUPS.keys())
    fig = go.Figure()

    if buildings_gdf is not None:
        # Гексагональная сетка плотности - рисуем первой, под полигонами
        for trace in make_hex_layer(hex_mode):
            fig.add_trace(trace)

        for gkey, ginfo in BUILDING_GROUPS.items():
            if gkey not in active_groups:
                continue
            subset = buildings_gdf[buildings_gdf["group"] == gkey]
            if len(subset) == 0:
                continue

            lats_all, lons_all = [], []
            c_lats, c_lons, texts = [], [], []

            for _, row in subset.iterrows():
                geom = row.geometry
                polys = (
                    [geom] if geom.geom_type == "Polygon"
                    else list(geom.geoms) if geom.geom_type == "MultiPolygon"
                    else []
                )
                for poly in polys:
                    xs, ys = poly.exterior.xy
                    lons_all.extend(list(xs) + [None])
                    lats_all.extend(list(ys) + [None])

                # Центроид для hover
                c_lats.append(row.lat)
                c_lons.append(row.lon)

                floors = int(row.floors) if row.floors and not np.isnan(row.floors) else "н/д"
                area = f"{row.area_m2:.0f}" if row.area_m2 else "н/д"
                btype = row.building
                street = row.street if hasattr(row, "street") and row.street == row.street else ""
                hnum = row.house_number if hasattr(row, "house_number") and row.house_number == row.house_number else ""
                addr = f"{street}, {hnum}".strip(", ") if (street or hnum) else "адрес неизвестен"
                texts.append(
                    f"<b>{ginfo['label']}</b> ({btype})<br>"
                    f"{addr}<br>"
                    f"Площадь: {area} м^2<br>"
                    f"Этажей: {floors}"
                )

            # Полигоны
            fig.add_trace(go.Scattermap(
                lat=lats_all,
                lon=lons_all,
                mode="lines",
                fill="toself",
                fillcolor=hex_to_rgba(ginfo["color"], 0.6),
                line=dict(color=hex_to_rgba(ginfo["color"], 0.9), width=0.8),
                hoverinfo="skip",
                showlegend=False,
                name=gkey,
            ))
            # Невидимые маркеры в центроидах - только для hover
            fig.add_trace(go.Scattermap(
                lat=c_lats,
                lon=c_lons,
                mode="markers",
                marker=dict(size=8, color="rgba(0,0,0,0)", opacity=0),
                text=texts,
                hovertemplate="%{text}<extra></extra>",
                showlegend=False,
                name=f"{gkey}_hover",
            ))

    # Границы города поверх
    for geom in boundary_gdf.geometry:
        if geom is None:
            continue
        polys = ([geom] if geom.geom_type == "Polygon"
                 else list(geom.geoms) if geom.geom_type == "MultiPolygon"
                 else [])
        for poly in polys:
            xs, ys = poly.exterior.xy
            fig.add_trace(go.Scattermap(
                lat=list(ys) + [ys[0]],
                lon=list(xs) + [xs[0]],
                mode="lines",
                line=dict(color="rgba(74,144,217,0.6)", width=1.5),
                hoverinfo="skip",
                showlegend=False,
            ))

    fig.update_layout(
        map=dict(
            style="carto-positron",
            center=dict(lat=CENTER_LAT, lon=CENTER_LON),
            zoom=INIT_ZOOM,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#FFFFFF",
        uirevision="buildings-map",
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            font=dict(color="#111111", family="IBM Plex Sans, sans-serif", size=13),
            bordercolor="#2563EB",
        ),
    )
    return fig


# График: суммарная площадь по типу здания (горизонтальный bar)
# Гексагональная сетка - плотность / этажность / разнообразие / площадь

HEX_RES_BLD = 9   # ~0.1 км^2 на гекс, достаточно для Байкальска

# Режимы и их параметры
HEX_MODES = {
    "floors": {"label": "Средняя этажность", "unit": "эт.",  "fmt": ".1f"},
    "density": {"label": "Плотность застройки (%)", "unit": "%",    "fmt": ".1f"},
    "diversity": {"label": "Разнообразие типов", "unit": "тип.", "fmt": ".0f"},
    "avg_area": {"label": "Средняя площадь здания (м^2)", "unit": "м^2",   "fmt": ".0f"},
}

# Цветовые шкалы для каждого режима
HEX_COLORSCALES = {
    "floors": [[0, "rgba(200,230,255,0.05)"], [0.5, "rgba(74,144,217,0.4)"], [1, "rgba(10,50,160,0.7)"]],
    "density": [[0, "rgba(200,230,255,0.05)"], [0.5, "rgba(81,207,102,0.4)"], [1, "rgba(20,120,50,0.7)"]],
    "diversity": [[0, "rgba(200,230,255,0.05)"], [0.5, "rgba(250,176,5,0.4)"], [1, "rgba(180,100,0,0.7)"]],
    "avg_area": [[0, "rgba(200,230,255,0.05)"], [0.5, "rgba(240,101,149,0.4)"], [1, "rgba(150,20,80,0.7)"]],
}

def _build_hex_data(mode="floors"):
    # Вычисляет значение метрики для каждого гекса
    if buildings_gdf is None:
        return [], [], []

    from data import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, boundary_shape

    poly = LatLngPoly([(LAT_MIN, LON_MIN), (LAT_MAX, LON_MIN),
                       (LAT_MAX, LON_MAX), (LAT_MIN, LON_MAX)])
    all_cells = list(h3.h3shape_to_cells(poly, res=HEX_RES_BLD))
    hex_cells = [
        c for c in all_cells
        if boundary_shape.contains(_ShPoint(h3.cell_to_latlng(c)[1], h3.cell_to_latlng(c)[0]))
    ]

    bdf = buildings_gdf.copy()

    # Вычисляем площадь каждого гекса (приблизительно)
    HEX_AREA_M2 = 105300.0

    results = []
    for cell_id in hex_cells:
        boundary_pts = h3.cell_to_boundary(cell_id)
        lats_b = [p[0] for p in boundary_pts]
        lons_b = [p[1] for p in boundary_pts]
        la0, la1 = min(lats_b), max(lats_b)
        lo0, lo1 = min(lons_b), max(lons_b)

        sub = bdf[(bdf.lat >= la0) & (bdf.lat <= la1) &
                  (bdf.lon >= lo0) & (bdf.lon <= lo1)]

        if len(sub) == 0:
            results.append(None)
            continue

        if mode == "floors":
            val = sub["floors"].replace(0, np.nan).mean()
        elif mode == "density":
            val = min(sub["area_m2"].sum() / HEX_AREA_M2 * 100, 100)
        elif mode == "diversity":
            val = float(sub["building"].nunique())
        elif mode == "avg_area":
            val = sub["area_m2"].mean()
        else:
            val = None

        results.append(val if val is not None and not np.isnan(val) else None)

    return hex_cells, results, HEX_COLORSCALES.get(mode, HEX_COLORSCALES["floors"])


# Кэш - пересчитываем только при смене режима
_hex_cache = {}

def make_hex_layer(mode="floors"):
    # Возвращает список Scattermap traces для гексагональной сетки
    global _hex_cache
    if mode not in _hex_cache:
        _hex_cache[mode] = _build_hex_data(mode)
    hex_cells, values, colorscale = _hex_cache[mode]

    if not hex_cells:
        return []

    valid_vals = [v for v in values if v is not None]
    if not valid_vals:
        return []

    vmin, vmax = min(valid_vals), max(valid_vals)
    if vmax == vmin:
        vmax = vmin + 1

    N_BUCKETS = 8
    buckets = {b: {"lats": [], "lons": []} for b in range(N_BUCKETS)}
    empty_lats, empty_lons = [], []   # гексы без зданий

    for cell_id, val in zip(hex_cells, values):
        bounds = h3.cell_to_boundary(cell_id)
        lats = [p[0] for p in bounds] + [bounds[0][0], None]
        lons = [p[1] for p in bounds] + [bounds[0][1], None]
        if val is None:
            empty_lats.extend(lats)
            empty_lons.extend(lons)
            continue
        t = (val - vmin) / (vmax - vmin)
        b = min(int(t * N_BUCKETS), N_BUCKETS - 1)
        buckets[b]["lats"].extend(lats)
        buckets[b]["lons"].extend(lons)

    traces = []

    # Пустые гексы - слабый зелёный
    if empty_lats:
        traces.append(go.Scattermap(
            lat=empty_lats,
            lon=empty_lons,
            mode="lines",
            fill="toself",
            fillcolor="rgba(100,200,120,0.12)",
            line=dict(color="rgba(100,200,120,0.25)", width=0.4),
            hoverinfo="skip",
            showlegend=False,
            name="hex_empty",
        ))
    for b in range(N_BUCKETS):
        if not buckets[b]["lats"]:
            continue
        t_mid = (b + 0.5) / N_BUCKETS
        # Интерполируем цвет из colorscale
        def interp_color(t, cs):
            for i in range(len(cs)-1):
                t0, c0 = cs[i]
                t1, c1 = cs[i+1]
                if t0 <= t <= t1:
                    return c1  # упрощённо берём верхний цвет сегмента
            return cs[-1][1]

        color = interp_color(t_mid, colorscale)

        traces.append(go.Scattermap(
            lat=buckets[b]["lats"],
            lon=buckets[b]["lons"],
            mode="lines",
            fill="toself",
            fillcolor=color,
            line=dict(color="rgba(100,160,200,0.15)", width=0.3),
            hoverinfo="skip",
            showlegend=False,
            name=f"hex_{b}",
        ))

    return traces

def make_area_bar():
    if buildings_gdf is None:
        return _empty_fig("Нет данных о зданиях")

    df = (
        buildings_gdf
        .groupby(["group", "group_label", "group_color"])["area_m2"]
        .sum()
        .reset_index()
        .sort_values("area_m2", ascending=True)
    )

    fig = go.Figure(go.Bar(
        x=df["area_m2"],
        y=df["group_label"],
        orientation="h",
        marker=dict(
            color=[hex_to_rgba(c, 0.85) for c in df["group_color"]],
            line=dict(color=[c for c in df["group_color"]], width=1),
        ),
        text=[f"{v/1000:.1f} тыс. м^2" for v in df["area_m2"]],
        textposition="outside",
        textfont=dict(color="#111111", size=11, family="IBM Plex Sans"),
        hovertemplate="<b>%{y}</b><br>%{x:,.0f} м^2<extra></extra>",
    ))

    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=8, r=60, t=36, b=8),
        title=dict(
            text="Суммарная площадь по типу",
            font=dict(size=12, color="#111111", family="IBM Plex Sans"),
            x=0.5, xanchor="center",
        ),
        xaxis=dict(
            showgrid=True, gridcolor="#EEEEEE", gridwidth=0.5,
            tickfont=dict(color="#111111", size=10),
            tickformat=",",
            showline=False, zeroline=False,
        ),
        yaxis=dict(
            tickfont=dict(color="#111111", size=12, family="IBM Plex Sans"),
            showgrid=False,
        ),
        bargap=0.3,
    )
    return fig


# График: donut - жилая / коммерческая / прочее

def make_type_donut():
    if buildings_gdf is None:
        return _empty_fig("Нет данных о зданиях")

    df = (
        buildings_gdf
        .groupby(["group_label", "group_color"])["area_m2"]
        .sum()
        .reset_index()
        .sort_values("area_m2", ascending=False)
    )

    fig = go.Figure(go.Pie(
        labels=df["group_label"],
        values=df["area_m2"],
        hole=0.55,
        marker=dict(
            colors=df["group_color"].tolist(),
            line=dict(color="#FFFFFF", width=2),
        ),
        textinfo="percent",
        textfont=dict(size=11, color="white", family="IBM Plex Sans"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} м^2 (%{percent})<extra></extra>",
        direction="clockwise",
        sort=False,
    ))

    total = df["area_m2"].sum()
    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=12, r=12, t=40, b=8),
        title=dict(
            text="Структура площади",
            font=dict(size=12, color="#111111", family="IBM Plex Sans"),
            x=0.5, xanchor="center", y=0.98,
        ),
        showlegend=False,
        annotations=[dict(
            text=f"{total/1000:.0f}<br><span style='font-size:10px'>тыс. м^2</span>",
            x=0.5, y=0.5,
            font=dict(size=18, color="#111111", family="IBM Plex Sans"),
            showarrow=False,
            align="center",
        )],
    )
    return fig


# График: количество зданий по типу (bar)

def make_count_bar():
    if buildings_gdf is None:
        return _empty_fig("Нет данных о зданиях")

    df = (
        buildings_gdf
        .groupby(["building", "group_color"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=True)
    )

    fig = go.Figure(go.Bar(
        x=df["count"],
        y=df["building"],
        orientation="h",
        marker=dict(
            color=[hex_to_rgba(c, 0.8) for c in df["group_color"]],
            line=dict(color=df["group_color"].tolist(), width=1),
        ),
        text=df["count"],
        textposition="outside",
        textfont=dict(color="#111111", size=11, family="IBM Plex Sans"),
        hovertemplate="<b>%{y}</b>: %{x} зданий<extra></extra>",
    ))

    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=8, r=40, t=36, b=8),
        title=dict(
            text="Количество зданий по типу",
            font=dict(size=12, color="#111111", family="IBM Plex Sans"),
            x=0.5, xanchor="center",
        ),
        xaxis=dict(
            showgrid=True, gridcolor="#EEEEEE", gridwidth=0.5,
            tickfont=dict(color="#111111", size=10),
            showline=False, zeroline=False,
        ),
        yaxis=dict(
            tickfont=dict(color="#111111", size=11, family="IBM Plex Sans"),
            showgrid=False,
        ),
        bargap=0.25,
        height=320,
    )
    return fig


# layout страницы застройки

LABEL_STYLE = {
    "fontSize": "9px", "letterSpacing": "3px",
    "color": "#111111", "marginBottom": "8px", "fontWeight": "500",
}
CHART_PANEL_W = "460px"
SIDEBAR_BLD_W = "220px"
HEADER_H = "52px"


def buildings_layout():
    return html.Div([

        # Боковая панель - фильтр по группам
        html.Div([
            html.Div("ТИПЫ ЗДАНИЙ", style=LABEL_STYLE),
            html.Div(id="bld-filter-container", children=[
                _group_checklist()
            ]),
            html.Div(style={"borderTop": "1px solid #E2E8F0", "margin": "16px 0"}),

            # Легенда гекс-сетки (плотность застройки, всегда включена)
            html.Div("ПЛОТНОСТЬ ЗАСТРОЙКИ", style=LABEL_STYLE),
            html.Div([
                html.Div(style={
                    "height": "8px", "borderRadius": "4px",
                    "background": "linear-gradient(to right, rgba(200,230,255,0.05), rgba(81,207,102,0.4), rgba(20,120,50,0.7))",
                    "marginBottom": "3px",
                }),
                html.Div([
                    html.Span("0%", style={"color": "#111111", "fontSize": "10px"}),
                    html.Span("100%", style={"color": "#111111", "fontSize": "10px"}),
                ], style={"display": "flex", "justifyContent": "space-between"}),
            ], style={"marginBottom": "16px"}),

            html.Div(style={"borderTop": "1px solid #E2E8F0", "margin": "16px 0"}),
            # Статистика
            html.Div("ВСЕГО ЗДАНИЙ", style=LABEL_STYLE),
            html.Div(id="bld-stats", children=_building_stats()),
        ], style={
            "position": "fixed", "top": HEADER_H, "left": 0,
            "width": SIDEBAR_BLD_W,
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
                id="buildings-map",
                figure=make_buildings_map(),
                style={"height": f"calc(100vh - {HEADER_H})", "width": "100%"},
                config={"scrollZoom": True, "displayModeBar": False},
            )
        ], style={
            "marginLeft": SIDEBAR_BLD_W,
            "marginRight": CHART_PANEL_W,
            "height": f"calc(100vh - {HEADER_H})",
        }),

        # Правая панель - графики
        html.Div([
            html.Div(style={"height": "16px"}),

            html.Div("СТРУКТУРА ПЛОЩАДИ", style={**LABEL_STYLE, "paddingLeft": "4px"}),
            dcc.Graph(
                id="bld-donut",
                figure=make_type_donut(),
                style={"height": "260px"},
                config={"displayModeBar": False},
            ),

            html.Div(style={"borderTop": "1px solid #E2E8F0", "margin": "4px 12px"}),

            html.Div("ПЛОЩАДЬ ПО КАТЕГОРИЯМ", style={**LABEL_STYLE, "paddingLeft": "4px", "paddingTop": "12px"}),
            dcc.Graph(
                id="bld-area-bar",
                figure=make_area_bar(),
                style={"height": "220px"},
                config={"displayModeBar": False},
            ),

            html.Div(style={"borderTop": "1px solid #E2E8F0", "margin": "4px 12px"}),

            html.Div("КОЛИЧЕСТВО ПО ТИПУ", style={**LABEL_STYLE, "paddingLeft": "4px", "paddingTop": "12px"}),
            dcc.Graph(
                id="bld-count-bar",
                figure=make_count_bar(),
                style={"height": "320px"},
                config={"displayModeBar": False},
            ),

        ], style={
            "position": "fixed", "top": HEADER_H, "right": 0,
            "width": CHART_PANEL_W,
            "height": f"calc(100vh - {HEADER_H})",
            "backgroundColor": "#FFFFFF",
            "borderLeft": "1px solid #E2E8F0",
            "overflowY": "auto",
            "zIndex": 1000,
        }),

    ])


# Вспомогательные компоненты

def _group_checklist():
    from dash import dcc, html
    return dcc.Checklist(
        id="bld-group-filter",
        options=[{
            "label": html.Span([
                html.Div(style={
                    "width": "10px", "height": "10px", "borderRadius": "2px",
                    "backgroundColor": ginfo["color"],
                    "marginRight": "8px", "flexShrink": "0",
                }),
                html.Span(ginfo["label"],
                          style={"fontSize": "12px", "color": "#111111"}),
            ], style={"display": "flex", "alignItems": "center", "padding": "4px 0"}),
            "value": gkey,
        } for gkey, ginfo in BUILDING_GROUPS.items()],
        value=list(BUILDING_GROUPS.keys()),
        inputStyle={"accentColor": "#2563EB", "marginRight": "8px",
                    "cursor": "pointer", "width": "13px", "height": "13px"},
        labelStyle={"display": "flex", "alignItems": "center", "cursor": "pointer"},
        style={"marginBottom": "16px"},
    )


def _building_stats():
    if buildings_gdf is None:
        return html.Div("Файл не найден", style={"color": "#111111", "fontSize": "12px"})

    total = len(buildings_gdf)
    total_a = buildings_gdf["area_m2"].sum()

    return html.Div([
        html.Div([
            html.Span(str(total),
                      style={"fontSize": "28px", "fontWeight": "600", "color": "#111111"}),
            html.Span(" зд.", style={"color": "#111111", "fontSize": "13px", "marginLeft": "4px"}),
        ], style={"marginBottom": "4px"}),
        html.Div([
            html.Span(f"{total_a/1000:.1f}",
                      style={"fontSize": "22px", "fontWeight": "500", "color": "#444444"}),
            html.Span(" тыс. м^2", style={"color": "#111111", "fontSize": "12px", "marginLeft": "4px"}),
        ]),
    ])


def _empty_fig(msg="Нет данных"):
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin=dict(l=8, r=8, t=8, b=8),
        annotations=[dict(
            text=msg, x=0.5, y=0.5,
            font=dict(color="#111111", size=13), showarrow=False,
        )],
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig