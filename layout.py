from dash import dcc, html
from data import poi_groups
from pages.transport.charts import make_pie, make_stops_by_neighborhood
from pages.transport.map_figure import BASE_FIGURE, ROUTE_COLORS

# Константы размеров
HEADER_H = "52px"
SIDEBAR_W = "260px"
CHART_W = "500px"

# Переиспользуемые стили
LABEL_STYLE = {
    "fontSize": "9px", "letterSpacing": "3px",
    "color": "#111111", "marginBottom": "8px", "fontWeight": "500",
}
DIVIDER = html.Div(style={"borderTop": "1px solid #E2E8F0", "marginBottom": "14px"})


def tab_btn(label, tab_id, active=False):
    return html.Button(label, id={"type": "tab-btn", "index": tab_id}, n_clicks=0, style={
        "background": "#EFF6FF" if active else "transparent",
        "border": "none",
        "borderBottom": "2px solid #2563EB" if active else "2px solid transparent",
        "color": "#111111" if active else "#94A3B8",
        "padding": "0 20px",
        "height": HEADER_H,
        "cursor": "pointer",
        "fontSize": "13px",
        "fontWeight": "500" if active else "400",
        "letterSpacing": "0.5px",
        "fontFamily": "'IBM Plex Sans', sans-serif",
        "transition": "all 0.15s",
    })


def make_header(active_tab="transport"):
    return html.Div([
        html.Div([
            html.Span("БАЙКАЛЬСК", style={
                "fontSize": "11px", "letterSpacing": "4px",
                "color": "#000000", "fontWeight": "800", "marginRight": "24px",
            }),
            tab_btn("Транспортная доступность", "transport", active=(active_tab == "transport")),
            tab_btn("Анализ застройки", "buildings", active=(active_tab == "buildings")),
            tab_btn("Функциональное наполнение", "functional", active=(active_tab == "functional")),
            tab_btn("Индекс озеленения NDVI", "ndvi", active=(active_tab == "ndvi")),
        ], style={"display": "flex", "alignItems": "center", "height": HEADER_H}),
    ], style={
        "position": "fixed", "top": 0, "left": 0, "right": 0,
        "height": HEADER_H,
        "backgroundColor": "#FFFFFF",
        "borderBottom": "1px solid #E2E8F0",
        "padding": "0 24px",
        "zIndex": 2000,
        "display": "flex", "alignItems": "center",
        "boxShadow": "0 1px 6px rgba(0,0,0,0.06)",
    })


def transport_layout():
    from data import stops_unique as _su
    stop_options = [{"label": s, "value": s} for s in sorted(_su["stop_name"].tolist())]

    return html.Div([

        # Боковая панель
        html.Div([
            html.Div("ОСТАНОВКИ", style=LABEL_STYLE),
            dcc.Dropdown(
                id="stop-dropdown",
                options=stop_options,
                placeholder="Добавить остановку",
                clearable=False,
                searchable=True,
                style={
                    "backgroundColor": "#FFFFFF",
                    "border": "1px solid #E2E8F0",
                    "borderRadius": "6px",
                    "fontSize": "12px",
                    "marginBottom": "10px",
                    "color": "#252525",
                },
            ),
            html.Div(id="selected-stops-tags", style={"marginBottom": "14px"}),

            DIVIDER,

            html.Div("СЛОИ ОБЪЕКТОВ", style=LABEL_STYLE),
            dcc.Checklist(
                id="poi-filter",
                options=[{
                    "label": html.Span([
                        html.Div(style={
                            "width": "10px", "height": "10px", "borderRadius": "50%",
                            "backgroundColor": poi_groups[k]["color"],
                            "marginRight": "8px", "flexShrink": "0",
                        }),
                        html.Span(poi_groups[k]["label"],
                                  style={"fontSize": "12px", "color": "#111111"}),
                    ], style={"display": "flex", "alignItems": "center", "padding": "4px 0"}),
                    "value": k,
                } for k in poi_groups],
                value=list(poi_groups.keys()),
                inputStyle={"accentColor": "#2563EB", "marginRight": "10px",
                            "cursor": "pointer", "width": "13px", "height": "13px"},
                labelStyle={"display": "flex", "alignItems": "center", "cursor": "pointer"},
                style={"marginBottom": "16px"},
            ),

            DIVIDER,

            html.Div("МАРШРУТЫ", style=LABEL_STYLE),
            html.Div([
                html.Div([
                    html.Div(style={
                        "width": "22px", "height": "3px", "borderRadius": "2px",
                        "backgroundColor": ROUTE_COLORS[r], "marginRight": "10px",
                    }),
                    html.Span(f"Маршрут {r}", style={"color": "#111111", "fontSize": "13px"}),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "6px"})
                for r in sorted(ROUTE_COLORS)
            ], style={"marginBottom": "16px"}),

            DIVIDER,
            html.Div(id="stop-info-panel"),

            html.Button("Сбросить всё", id="reset-btn", n_clicks=0, style={
                "background": "transparent",
                "border": "1px solid #E2E8F0",
                "color": "#2563EB", "borderRadius": "6px",
                "padding": "8px 0", "cursor": "pointer",
                "fontSize": "12px", "letterSpacing": "1px",
                "width": "100%", "marginTop": "10px",
                "fontFamily": "'IBM Plex Sans', sans-serif",
            }),

        ], style={
            "position": "fixed", "top": HEADER_H, "left": 0,
            "width": SIDEBAR_W,
            "height": f"calc(100vh - {HEADER_H})",
            "backgroundColor": "#FFFFFF",
            "padding": "18px 16px",
            "zIndex": 1000, "overflowY": "auto",
            "borderRight": "1px solid #E2E8F0",
            "boxShadow": "2px 0 8px rgba(0,0,0,0.06)",
            "boxSizing": "border-box",
        }),

        # Карта
        html.Div([
            dcc.Graph(
                id="map",
                figure=BASE_FIGURE,
                style={"height": f"calc(100vh - {HEADER_H})", "width": "100%"},
                config={"scrollZoom": True, "displayModeBar": False},
            )
        ], style={
            "marginLeft": SIDEBAR_W,
            "marginRight": CHART_W,
            "height": f"calc(100vh - {HEADER_H})",
        }),

        # Панель с диаграммой
        html.Div([
            html.Div("СТРУКТУРА POI", style={
                **LABEL_STYLE,
                "marginBottom": "12px", "paddingTop": "18px", "paddingLeft": "4px",
            }),
            dcc.Graph(
                id="pie-chart",
                figure=make_pie(None, list(poi_groups.keys())),
                style={"height": "340px"},
                config={"displayModeBar": False},
            ),
            html.Div(id="pie-legend", children=[
                html.Div([
                    html.Div(style={
                        "width": "10px", "height": "10px", "borderRadius": "2px",
                        "backgroundColor": g["color"], "marginRight": "8px", "flexShrink": "0",
                    }),
                    html.Span(g["label"],
                              style={"color": "#111111", "fontSize": "12px", "flex": "1"}),
                    html.Span(str(len(g["df"])),
                              style={"color": "#111111", "fontSize": "11px"}),
                ], style={"display": "flex", "alignItems": "center",
                          "padding": "5px 0", "borderBottom": "1px solid #F5F7FA"})
                for g in poi_groups.values()
            ], style={"padding": "0 12px 12px"}),

            html.Div(style={"borderTop": "1px solid #E2E8F0", "margin": "4px 12px"}),

            html.Div("ОСТАНОВКИ ПО РАЙОНАМ", style={
                **LABEL_STYLE,
                "paddingTop": "14px", "paddingLeft": "4px",
            }),
            dcc.Graph(
                id="stops-neighborhood-bar",
                figure=make_stops_by_neighborhood(),
                style={"height": "260px"},
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


def buildings_layout():
    from pages.buildings.buildings_page import buildings_layout as _bld_layout
    return _bld_layout()