import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
import os as _os
from shapely.geometry import Point as _ShPt
from shapely.geometry import Polygon as _ShPoly

HEADER_H = "52px"

LABEL_STYLE = {
    "fontSize": "9px", "letterSpacing": "3px",
    "color": "#111111", "marginBottom": "8px", "fontWeight": "500",
}

C_BAIKALSK = "#0891B2"   # бирюзовый
C_IRKUTSK = "#FAB005"   # жёлтый

# Центры городов для карт
BAIKALSK_CENTER = {"lat": 51.513, "lon": 104.158, "zoom": 12}
IRKUTSK_CENTER = {"lat": 52.290, "lon": 104.296, "zoom": 9}

# Градиент NDVI для карт
NDVI_COLORSCALE = [
    [0.00, "#d73027"],   # < 0    вода / асфальт
    [0.20, "#fc8d59"],   # 0-0.1  голая почва
    [0.35, "#fee08b"],   # 0.1-0.2
    [0.50, "#d9ef8b"],   # 0.2-0.3
    [0.65, "#91cf60"],   # 0.3-0.5
    [0.82, "#1a9850"],   # 0.5-0.7
    [1.00, "#006837"],   # > 0.7  густая растительность
]


DATA_DIR = "data"
def _p(filename):
    return _os.path.join(DATA_DIR, filename)


def _load_stats(path):
    if not _os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace("ndvi_", "") for c in df.columns]
    # Переименовываем системные колонки
    rename = {"system:index": "idx", ".geo": "geo"}
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    return df[["year","mean","median","stddev","p25","p75","min","max","count"]].copy()

stats_b = _load_stats(_p("ndvi_stats_baikalsk.csv"))
stats_i = _load_stats(_p("ndvi_stats_irkutsk.csv"))

# Если файлов нет - синтетические данные для разработки
if stats_b is None:
    years = list(range(2017, 2026))
    stats_b = pd.DataFrame({
        "year": years,
        "mean": [0.690,0.692,0.590,0.638,0.636,0.636,0.616,0.595,0.627],
        "median": [0.777,0.785,0.652,0.707,0.707,0.707,0.676,0.668,0.691],
        "stddev": [0.223,0.225,0.198,0.226,0.224,0.238,0.237,0.222,0.244],
        "p25": [0.566,0.551,0.465,0.496,0.504,0.473,0.449,0.457,0.465],
        "p75": [0.871,0.879,0.754,0.832,0.824,0.847,0.832,0.777,0.848],
        "min": [-0.497,-0.129,-0.347,-0.417,-0.283,-0.412,-0.300,-0.290,-0.197],
        "max": [0.927,0.926,0.860,0.906,0.901,0.915,0.911,0.884,0.909],
        "count": [20478]*9,
    })

if stats_i is None:
    years = list(range(2017, 2026))
    stats_i = pd.DataFrame({
        "year": years,
        "mean": [0.495,0.455,0.440,0.460,0.482,0.461,0.465,0.473,0.471],
        "median": [0.590,0.535,0.504,0.520,0.566,0.520,0.551,0.566,0.527],
        "stddev": [0.322,0.302,0.277,0.286,0.310,0.294,0.294,0.308,0.299],
        "p25": [0.254,0.238,0.223,0.238,0.254,0.230,0.246,0.254,0.238],
        "p75": [0.777,0.707,0.691,0.723,0.762,0.723,0.723,0.746,0.746],
        "min": [-0.600,-0.725,-0.519,-0.571,-0.665,-0.662,-0.544,-0.774,-0.579],
        "max": [0.925,0.901,0.891,0.890,0.910,0.912,0.902,0.898,0.912],
        "count": [481795]*9,
    })


# Графики
def make_ndvi_trend():
    # Линейный график средних значений NDVI по годам для обоих городов
    fig = go.Figure()

    for df, name, color in [
        (stats_b, "Байкальск", C_BAIKALSK),
        (stats_i, "Иркутск", C_IRKUTSK),
    ]:
        # Доверительная полоса p25-p75
        fig.add_trace(go.Scatter(
            x=df["year"].tolist() + df["year"].tolist()[::-1],
            y=df["p75"].tolist() + df["p25"].tolist()[::-1],
            fill="toself",
            fillcolor=color.replace("#", "rgba(").replace(")", ",0.12)") if False
                else f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.12)",
            line=dict(color="rgba(0,0,0,0)"),
            hoverinfo="skip",
            showlegend=False,
        ))
        # Медиана
        fig.add_trace(go.Scatter(
            x=df["year"], y=df["median"],
            mode="lines",
            line=dict(color=color, width=1.5, dash="dot"),
            opacity=0.6,
            name=f"{name} медиана",
            showlegend=False,
            hovertemplate=f"{name} медиана: %{{y:.3f}}<extra></extra>",
        ))
        # Среднее
        fig.add_trace(go.Scatter(
            x=df["year"], y=df["mean"],
            mode="lines+markers",
            line=dict(color=color, width=2.5),
            marker=dict(size=7, color=color,
                        line=dict(color="#FFFFFF", width=1.5)),
            name=name,
            hovertemplate=f"<b>{name}</b> %{{x}}<br>Среднее: %{{y:.3f}}<extra></extra>",
        ))

    fig.update_layout(
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin=dict(l=8, r=8, t=36, b=8),
        title=dict(
            text="Динамика среднего NDVI (вегетационный период, май-сен)",
            font=dict(size=12, color="#111111", family="IBM Plex Sans"),
            x=0.5, xanchor="center",
        ),
        xaxis=dict(
            tickvals=list(range(2017, 2026)),
            tickfont=dict(color="#111111", size=10),
            showgrid=True, gridcolor="#EEEEEE", zeroline=False,
        ),
        yaxis=dict(
            title=dict(text="NDVI", font=dict(color="#666666", size=11)),
            tickfont=dict(color="#111111", size=10),
            showgrid=True, gridcolor="#EEEEEE", zeroline=False,
            range=[0.3, 0.85],
        ),
        legend=dict(
            font=dict(color="#111111", size=11, family="IBM Plex Sans"),
            bgcolor="rgba(0,0,0,0)",
            x=0.02, y=0.05,
        ),
    )
    return fig


def make_ndvi_boxplot_city(df, city_name, color):
    # Box-plot распределения NDVI по годам для одного города
    fig = go.Figure()

    r, g, b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)

    fig.add_trace(go.Box(
        x=df["year"],
        q1=df["p25"],
        median=df["median"],
        q3=df["p75"],
        lowerfence=df["min"],
        upperfence=df["max"],
        mean=df["mean"],
        name=city_name,
        marker=dict(color=color, size=5),
        line=dict(color=color, width=1.8),
        fillcolor=f"rgba({r},{g},{b},0.18)",
        boxmean=True,
        hovertemplate=(
            f"<b>{city_name}</b> %{{x}}<br>"
            "Медиана: %{median:.3f}<br>"
            "Среднее: %{mean:.3f}<br>"
            "P25–P75: %{q1:.3f}–%{q3:.3f}<br>"
            "Min–Max: %{lowerfence:.3f}–%{upperfence:.3f}"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin=dict(l=40, r=16, t=44, b=36),
        title=dict(
            text=f"Распределение NDVI {city_name}<br>"
                 f"<sup>Вегетационный период (май-сентябрь), Sentinel-2</sup>",
            font=dict(size=12, color="#111111", family="IBM Plex Sans"),
            x=0.5, xanchor="center",
        ),
        xaxis=dict(
            tickvals=df["year"].tolist(),
            tickfont=dict(color="#111111", size=10),
            showgrid=False, zeroline=False,
            title=dict(text="Год", font=dict(color="#111111", size=11)),
        ),
        yaxis=dict(
            title=dict(text="NDVI", font=dict(color="#111111", size=11)),
            tickfont=dict(color="#111111", size=10),
            showgrid=True, gridcolor="#EEEEEE", zeroline=False,
            range=[-0.05, 1.0],
        ),
        showlegend=False,
    )
    return fig


def _load_grid(city):
    path = _p(f"ndvi_grid_{city}.csv")
    if not _os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    return df

_grid_cache = {}

def _get_grid(city):
    if city not in _grid_cache:
        _grid_cache[city] = _load_grid(city)
    return _grid_cache[city]


def make_city_map(city: str, year: int = 2024):
    if city == "baikalsk":
        c = BAIKALSK_CENTER
        boundary_coords = [
            [104.11753,51.52273],[104.12203,51.52205],[104.11872,51.51485],
            [104.11983,51.513],  [104.11769,51.50764],[104.12231,51.50674],
            [104.12214,51.51003],[104.12418,51.51185],[104.12268,51.51305],
            [104.12468,51.51529],[104.13815,51.51074],[104.13743,51.50335],
            [104.14223,51.49863],[104.15322,51.5033], [104.15272,51.50651],
            [104.17221,51.50582],[104.17442,51.5076], [104.1995, 51.50192],
            [104.20214,51.50435],[104.20112,51.51021],[104.18288,51.52342],
            [104.16507,51.52626],[104.14456,51.52678],[104.11804,51.52479],
            [104.11753,51.52273],
        ]
        name = "Байкальск"; color = C_BAIKALSK; df_stats = stats_b
    else:
        c = IRKUTSK_CENTER
        boundary_coords = [
            [104.05892,52.39701],[104.10006,52.37727],[104.08618,52.37015],
            [104.09121,52.36676],[104.11448,52.36563],[104.14894,52.34538],
            [104.15266,52.33991],[104.14168,52.33742],[104.15106,52.3286],
            [104.16184,52.33355],[104.172,52.32145],  [104.18249,52.32902],
            [104.19284,52.31902],[104.2193,52.30948], [104.20146,52.30518],
            [104.19722,52.29616],[104.18742,52.29263],[104.18612,52.28932],
            [104.19946,52.28156],[104.18802,52.27468],[104.19317,52.26746],
            [104.18806,52.2632], [104.19891,52.25932],[104.19591,52.25659],
            [104.19897,52.25453],[104.21014,52.25331],[104.18939,52.24488],
            [104.19444,52.24182],[104.22546,52.24506],[104.2246,52.25425],
            [104.23765,52.24633],[104.25034,52.2478], [104.26129,52.24396],
            [104.26562,52.2324], [104.28,52.21765],   [104.30079,52.21364],
            [104.31822,52.21801],[104.3222,52.2096],  [104.34928,52.20923],
            [104.37755,52.24024],[104.37113,52.24574],[104.38617,52.25244],
            [104.36477,52.25404],[104.36502,52.25921],[104.36055,52.26001],
            [104.36362,52.26298],[104.37954,52.2648], [104.43256,52.25639],
            [104.37292,52.27552],[104.37386,52.28372],[104.39616,52.28694],
            [104.4086,52.29513], [104.43035,52.28805],[104.44412,52.28957],
            [104.44519,52.2954], [104.4367,52.30146], [104.44847,52.31008],
            [104.42042,52.34003],[104.40133,52.35461],[104.37077,52.36721],
            [104.35582,52.37121],[104.33317,52.36758],[104.3212,52.33791],
            [104.3095,52.33404], [104.28894,52.34615],[104.28233,52.35717],
            [104.19286,52.38469],[104.18491,52.38941],[104.18077,52.39928],
            [104.16279,52.40263],[104.14082,52.39989],[104.10822,52.42167],
            [104.08884,52.41135],[104.07815,52.39985],[104.06409,52.40355],
            [104.05892,52.39701],
        ]
        name = "Иркутск"; color = C_IRKUTSK; df_stats = stats_i

    lats_b = [p[1] for p in boundary_coords]
    lons_b = [p[0] for p in boundary_coords]

    row = df_stats[df_stats["year"] == year]
    mean_val = float(row["mean"].iloc[0])   if len(row) else float(df_stats["mean"].mean())
    median_val = float(row["median"].iloc[0]) if len(row) else float(df_stats["median"].mean())

    fig = go.Figure()

    grid = _get_grid(city)
    if grid is not None:
        g_year = grid[grid["year"] == year].copy()
        if len(g_year) == 0:
            g_year = grid[grid["year"] == grid["year"].max()].copy()

        # Обрезаем точки по границе города - убираем красный фон за пределами
        try:
            boundary_poly = _ShPoly([(p[0], p[1]) for p in boundary_coords])
            mask = g_year.apply(
                lambda r: boundary_poly.contains(_ShPt(r["lon"], r["lat"])), axis=1
            )
            g_year = g_year[mask]
        except Exception:
            pass  # если shapely не сработает - показываем без обрезки

        fig.add_trace(go.Scattermap(
            lat=g_year["lat"].tolist(),
            lon=g_year["lon"].tolist(),
            mode="markers",
            marker=dict(
                size=6,
                color=g_year["ndvi"].tolist(),
                colorscale=[
                    [0.00, "#d73027"],
                    [0.25, "#fc8d59"],
                    [0.40, "#fee08b"],
                    [0.55, "#d9ef8b"],
                    [0.70, "#91cf60"],
                    [0.85, "#1a9850"],
                    [1.00, "#006837"],
                ],
                cmin=-0.2, cmax=0.9,
                opacity=0.85,
                colorbar=dict(
                    title=dict(text="NDVI", font=dict(color="#111111", size=11)),
                    tickfont=dict(color="#111111", size=9),
                    bgcolor="#FFFFFF",
                    bordercolor="#E2E8F0",
                    thickness=10, len=0.6, x=1.0,
                ),
            ),
            hovertemplate="NDVI: %{marker.color:.3f}<extra></extra>",
            showlegend=False,
        ))
    else:
        fig.add_trace(go.Scattermap(
            lat=[c["lat"]], lon=[c["lon"]],
            mode="text",
            text=["Загрузи data/ndvi_grid_" + city + ".csv"],
            textfont=dict(size=11, color="#111111"),
            hoverinfo="skip", showlegend=False,
        ))

    # Граница города - тонкая пунктирная
    fig.add_trace(go.Scattermap(
        lat=lats_b, lon=lons_b,
        mode="lines",
        line=dict(color="rgba(80,80,80,0.5)", width=1.2),
        hoverinfo="skip", showlegend=False,
    ))

    fig.update_layout(
        map=dict(
            style="carto-positron",
            center=dict(lat=c["lat"], lon=c["lon"]),
            zoom=c["zoom"],
        ),
        margin=dict(l=0, r=0, t=28, b=0),
        paper_bgcolor="#FFFFFF",
        title=dict(
            text=f"{name} · NDVI {year}  (среднее: {mean_val:.3f}  медиана: {median_val:.3f})",
            font=dict(size=11, color="#111111", family="IBM Plex Sans"),
            x=0.5, xanchor="center", y=0.98,
        ),
        uirevision=city,   # фиксируем вид - не сбрасывается при смене года
        hoverlabel=dict(bgcolor="#FFFFFF", font=dict(color="#111111", size=12)),
    )
    return fig


def make_comparison_bar():
    # Горизонтальный bar - сравнение среднего NDVI за весь период
    metrics = ["Среднее NDVI", "Медиана NDVI", "P75 (верхний квартиль)"]
    vals_b = [stats_b["mean"].mean(), stats_b["median"].mean(), stats_b["p75"].mean()]
    vals_i = [stats_i["mean"].mean(), stats_i["median"].mean(), stats_i["p75"].mean()]

    fig = go.Figure()
    for vals, name, color in [
        (vals_b, "Байкальск", C_BAIKALSK),
        (vals_i, "Иркутск",   C_IRKUTSK),
    ]:
        r, g, b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
        fig.add_trace(go.Bar(
            y=metrics, x=vals, orientation="h", name=name,
            marker=dict(color=f"rgba({r},{g},{b},0.80)", line=dict(color=color, width=1)),
            text=[f"{v:.3f}" for v in vals],
            textposition="outside",
            textfont=dict(color="#111111", size=11),
            hovertemplate=f"<b>{name}</b><br>%{{y}}: %{{x:.3f}}<extra></extra>",
        ))

    fig.update_layout(
        barmode="group",
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin=dict(l=8, r=48, t=36, b=8),
        title=dict(text="Средние значения за 2017–2025",
                   font=dict(size=12, color="#111111", family="IBM Plex Sans"),
                   x=0.5, xanchor="center"),
        xaxis=dict(showgrid=True, gridcolor="#EEEEEE",
                   tickfont=dict(color="#111111", size=10), zeroline=False, range=[0, 0.95]),
        yaxis=dict(tickfont=dict(color="#111111", size=11, family="IBM Plex Sans"), showgrid=False),
        legend=dict(font=dict(color="#111111", size=11), bgcolor="rgba(0,0,0,0)"),
        bargap=0.15, bargroupgap=0.05,
    )
    return fig


def _summary_card(name, df, color):
    mean_all = df["mean"].mean()
    best_year = int(df.loc[df["mean"].idxmax(), "year"])
    trend = df["mean"].iloc[-1] - df["mean"].iloc[0]
    trend_str = f"{'▲' if trend > 0 else '▼'} {abs(trend):.3f}"
    trend_col = "#51CF66" if trend > 0 else "#FF6B6B"
    r, g, b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)

    return html.Div([
        html.Div(name, style={"fontSize": "11px", "fontWeight": "600",
                              "color": color, "marginBottom": "5px"}),
        html.Div([
            html.Div([
                html.Span(f"{mean_all:.3f}",
                          style={"fontSize": "20px", "fontWeight": "600", "color": "#111111"}),
                html.Span(" ср. NDVI",
                          style={"fontSize": "10px", "color": "#111111", "marginLeft": "4px"}),
            ]),
            html.Div([
                html.Span("Лучший год: ", style={"fontSize": "10px", "color": "#111111"}),
                html.Span(str(best_year),
                          style={"fontSize": "11px", "color": "#111111", "fontWeight": "500"}),
            ]),
            html.Div([
                html.Span("Тренд 17 -> 25: ", style={"fontSize": "10px", "color": "#111111"}),
                html.Span(trend_str,
                          style={"fontSize": "11px", "color": trend_col, "fontWeight": "500"}),
            ]),
        ]),
    ], style={
        "backgroundColor": f"rgba({r},{g},{b},0.07)",
        "border": f"1px solid rgba({r},{g},{b},0.25)",
        "borderRadius": "6px", "padding": "10px 12px",
    })


def ndvi_layout():
    years = sorted(stats_b["year"].tolist())

    return html.Div([

        # Боковая панель
        html.Div([
            html.Div("ИНДЕКС ОЗЕЛЕНЕНИЯ NDVI", style={**LABEL_STYLE, "color": "#16A34A"}),
            html.Div(style={"borderTop": "1px solid #E2E8F0", "marginBottom": "14px"}),

            html.Div("ГОД ДЛЯ КАРТЫ", style=LABEL_STYLE),
            dcc.Slider(
                id="ndvi-year-slider",
                min=min(years), max=max(years), step=1,
                value=2024,
                marks={y: {"label": str(y),
                           "style": {"color": "#111111", "fontSize": "10px"}}
                       for y in years},
                tooltip={"placement": "bottom", "always_visible": False},
            ),

            html.Div(style={"borderTop": "1px solid #E2E8F0", "margin": "18px 0 14px"}),

            html.Div("ИТОГИ 2017-2025", style=LABEL_STYLE),
            _summary_card("Байкальск", stats_b, C_BAIKALSK),
            html.Div(style={"height": "10px"}),
            _summary_card("Иркутск",   stats_i, C_IRKUTSK),

            html.Div(style={"borderTop": "1px solid #E2E8F0", "margin": "14px 0"}),

            html.Div("ШКАЛА NDVI", style=LABEL_STYLE),
            *[html.Div([
                html.Div(style={
                    "width": "12px", "height": "12px", "borderRadius": "2px",
                    "backgroundColor": c, "marginRight": "8px", "flexShrink": "0",
                }),
                html.Span(label, style={"color": "#111111", "fontSize": "11px"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"})
            for c, label in [
                ("#006837", "> 0.7    густая растительность"),
                ("#1a9850", "0.5–0.7  лес / парки"),
                ("#91cf60", "0.3–0.5  трава / кустарник"),
                ("#fee08b", "0.1–0.3  редкая растительность"),
                ("#fc8d59", "0–0.1    почва / застройка"),
                ("#d73027", "< 0      вода / асфальт"),
            ]],

        ], style={
            "position": "fixed", "top": HEADER_H, "left": 0,
            "width": "220px", "height": f"calc(100vh - {HEADER_H})",
            "backgroundColor": "#FFFFFF", "padding": "18px 14px",
            "zIndex": 1000, "overflowY": "auto",
            "borderRight": "1px solid #E2E8F0",
            "boxShadow": "2px 0 6px rgba(0,0,0,0.05)",
            "boxSizing": "border-box",
        }),

        # Основной контент - карты вверху (60%), графики внизу (40%)
        html.Div([

            # Верхний ряд: две карты - большие
            html.Div([
                html.Div([
                    dcc.Graph(
                        id="ndvi-map-baikalsk",
                        figure=make_city_map("baikalsk", 2024),
                        style={"height": "100%", "width": "100%"},
                        config={"scrollZoom": True, "displayModeBar": False},
                    )
                ], style={
                    "flex": "1",
                    "borderRight": "1px solid #E2E8F0",
                }),
                html.Div([
                    dcc.Graph(
                        id="ndvi-map-irkutsk",
                        figure=make_city_map("irkutsk", 2024),
                        style={"height": "100%", "width": "100%"},
                        config={"scrollZoom": True, "displayModeBar": False},
                    )
                ], style={"flex": "1"}),
            ], style={
                "display": "flex",
                "height": f"calc((100vh - {HEADER_H}) * 0.58)",
                "borderBottom": "1px solid #E2E8F0",
            }),

            # Нижний ряд: два box-plot - Байкальск и Иркутск
            html.Div([
                html.Div([
                    dcc.Graph(
                        id="ndvi-boxplot-baikalsk",
                        figure=make_ndvi_boxplot_city(stats_b, "Байкальск", C_BAIKALSK),
                        style={"height": "100%"},
                        config={"displayModeBar": False},
                    )
                ], style={"flex": "1", "borderRight": "1px solid #E2E8F0"}),
                html.Div([
                    dcc.Graph(
                        id="ndvi-boxplot-irkutsk",
                        figure=make_ndvi_boxplot_city(stats_i, "Иркутск", C_IRKUTSK),
                        style={"height": "100%"},
                        config={"displayModeBar": False},
                    )
                ], style={"flex": "1"}),
            ], style={
                "display": "flex",
                "height": f"calc((100vh - {HEADER_H}) * 0.42)",
                "backgroundColor": "#FFFFFF",
            }),

        ], style={
            "marginLeft": "220px",
            "height": f"calc(100vh - {HEADER_H})",
            "backgroundColor": "#FFFFFF",
        }),
    ])