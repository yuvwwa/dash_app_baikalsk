import dash
from dash import html, Input, Output, State, ctx
from pages.transport.map_figure import ROUTE_COLORS
from layout import transport_layout, buildings_layout


def register_callbacks(app: dash.Dash):

    # Обновление шапки при смене вкладки
    @app.callback(
        Output("app-header", "children"),
        Input("active-tab",  "data"),
    )
    def update_header(tab):
        from layout import make_header
        return make_header(active_tab=tab)

    # Переключение вкладок
    @app.callback(
        Output("active-tab", "data"),
        Input({"type": "tab-btn", "index": dash.ALL}, "n_clicks"),
        State("active-tab", "data"),
        prevent_initial_call=True,
    )
    def switch_tab(_, current):
        triggered = ctx.triggered_id
        if triggered and isinstance(triggered, dict):
            return triggered["index"]
        return current

    # Рендер страницы
    @app.callback(
        Output("page-content", "children"),
        Input("active-tab", "data"),
    )
    def render_page(tab):
        from pages.functional.functional_page import functional_layout
        from pages.ndvi.ndvi_page             import ndvi_layout
        if tab == "transport":
            return transport_layout()
        elif tab == "functional":
            return functional_layout()
        elif tab == "ndvi":
            return ndvi_layout()
        return buildings_layout()

    # Добавление остановки через дропдаун
    @app.callback(
        Output("selected-stop", "data"),
        Input("stop-dropdown",  "value"),
        Input("reset-btn",      "n_clicks"),
        Input({"type": "remove-stop", "index": dash.ALL}, "n_clicks"),
        State("selected-stop",  "data"),
        prevent_initial_call=True,
    )
    def update_selected_stops(dropdown_val, _reset, remove_clicks, current):
        current = current or []
        trigger = ctx.triggered_id

        if trigger == "reset-btn":
            return []

        if isinstance(trigger, dict) and trigger.get("type") == "remove-stop":
            stop_to_remove = trigger["index"]
            return [s for s in current if s != stop_to_remove]

        if dropdown_val and dropdown_val not in current:
            from pages.transport.map_figure import MAX_SELECTED
            if len(current) < MAX_SELECTED:
                return current + [dropdown_val]

        return current

    # Теги выбранных остановок
    @app.callback(
        Output("selected-stops-tags", "children"),
        Input("selected-stop", "data"),
    )
    def render_stop_tags(selected_stops):
        selected_stops = selected_stops or []
        if not selected_stops:
            return html.Div("Остановки не выбраны",
                            style={"color": "#4D4C4C", "fontSize": "12px",
                                   "textAlign": "center", "padding": "4px 0"})
        return html.Div([
            html.Div([
                html.Span(s, style={
                    "fontSize": "12px", "color": "#000000",
                    "flex": "1", "overflow": "hidden",
                    "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                }),
                html.Button("✕",
                    id={"type": "remove-stop", "index": s},
                    n_clicks=0,
                    style={
                        "background": "transparent", "border": "none",
                        "color": "#000000", "cursor": "pointer",
                        "fontSize": "11px", "padding": "0 0 0 6px",
                        "lineHeight": "1", "flexShrink": "0",
                    }
                ),
            ], style={
                "display": "flex", "alignItems": "center",
                "backgroundColor": "#F8FAFC",
                "border": "1px solid #E2E8F0",
                "borderRadius": "4px",
                "padding": "4px 8px",
                "marginBottom": "4px",
            })
            for s in selected_stops
        ])

    # Обновление карты (мульти-буфер)
    @app.callback(
        Output("map",    "figure"),
        Input("selected-stop", "data"),
        Input("poi-filter",    "value"),
    )
    def refresh_map(selected_stops, active_groups):
        from pages.transport.map_figure import make_patch
        return make_patch(active_groups or [], selected_stops or [])

    # Боковая панель остановки
    @app.callback(
        Output("stop-info-panel", "children"),
        Input("selected-stop",    "data"),
        Input("poi-filter",       "value"),
    )
    def refresh_panel(selected_stops, active_groups):
        from data import stops_unique, stops_routes_map, pois_in_buffer, poi_groups
        selected_stops = selected_stops or []
        active_groups = active_groups  or []

        if not selected_stops:
            return html.Div("Выберите остановку выше", style={
                "color": "#525050", "fontSize": "12px",
                "textAlign": "center", "padding": "8px 0",
            })

        sname = selected_stops[-1]
        rows = stops_unique[stops_unique.stop_name == sname]
        if len(rows) == 0:
            return html.Div()

        srow = rows.iloc[0]
        routes = stops_routes_map.get(sname, [])

        poi_rows = []
        for gkey in active_groups:
            g = poi_groups[gkey]
            sub = pois_in_buffer(srow.lat, srow.lon, gkey)
            n = len(sub)
            if n == 0:
                continue
            poi_rows.append(html.Div([
                html.Div(style={
                    "width": "10px", "height": "10px", "borderRadius": "50%",
                    "backgroundColor": g["color"],
                    "marginRight": "8px", "flexShrink": "0",
                }),
                html.Span(g["label"],
                          style={"color": "#252525", "fontSize": "12px", "flex": "1"}),
                html.Span(str(n),
                          style={"color": g["color"], "fontWeight": "600", "fontSize": "13px"}),
            ], style={"display": "flex", "alignItems": "center",
                      "padding": "5px 0", "borderBottom": "1px solid #F1F5F9"}))

        return html.Div([
            html.Div("ПОСЛЕДНЯЯ ОСТАНОВКА", style={
                "fontSize": "9px", "letterSpacing": "3px",
                "color": "#444343", "marginBottom": "4px",
            }),
            html.Div(sname, style={
                "fontSize": "15px", "fontWeight": "600",
                "color": "#111111", "marginBottom": "10px",
            }),
            html.Div("МАРШРУТЫ", style={
                "fontSize": "9px", "letterSpacing": "3px",
                "color": "#444343", "marginBottom": "7px",
            }),
            html.Div([
                html.Div([
                    html.Div(style={
                        "width": "10px", "height": "10px", "borderRadius": "50%",
                        "backgroundColor": ROUTE_COLORS.get(r, "#888"),
                        "marginRight": "8px", "flexShrink": "0",
                    }),
                    html.Span(f"Маршрут {r}",
                              style={"color": "#1B1B1B", "fontSize": "13px"}),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"})
                for r in routes
            ], style={"marginBottom": "12px"}),
            html.Div("ОБЪЕКТЫ В РАДИУСЕ 500 М", style={
                "fontSize": "9px", "letterSpacing": "3px",
                "color": "#444343", "marginBottom": "7px",
            }),
            html.Div(
                poi_rows if poi_rows
                else html.Div("Нет объектов в радиусе",
                              style={"color": "#4B4949", "fontSize": "12px"})
            ),
        ])

    # Круговая диаграмма
    @app.callback(
        Output("pie-chart",  "figure"),
        Output("pie-legend", "children"),
        Input("selected-stop", "data"),
        Input("poi-filter",    "value"),
    )
    def refresh_pie(selected_stops, active_groups):
        from pages.transport.charts import make_pie
        from data import stops_unique, pois_in_buffer, poi_groups
        active_groups = active_groups  or list(poi_groups.keys())
        selected_stops = selected_stops or []

        selected_stop = selected_stops[-1] if selected_stops else None

        if selected_stop:
            row = stops_unique[stops_unique.stop_name == selected_stop].iloc[0]
            counts = {k: len(pois_in_buffer(row.lat, row.lon, k)) for k in poi_groups}
        else:
            counts = {k: len(poi_groups[k]["df"]) for k in poi_groups}

        legend = [
            html.Div([
                html.Div(style={
                    "width": "10px", "height": "10px", "borderRadius": "2px",
                    "backgroundColor": poi_groups[k]["color"],
                    "marginRight": "8px", "flexShrink": "0",
                    "opacity": "1" if k in active_groups else "0.3",
                }),
                html.Span(poi_groups[k]["label"], style={
                    "color": "#242323" if k in active_groups else "#CBD5E1",
                    "fontSize": "12px", "flex": "1",
                }),
                html.Span(str(counts[k]),
                          style={"color": "#444343", "fontSize": "11px"}),
            ], style={"display": "flex", "alignItems": "center",
                      "padding": "5px 0", "borderBottom": "1px solid #F5F7FA"})
            for k in poi_groups
        ]
        return make_pie(selected_stop, active_groups), legend

    # Фильтр зданий
    @app.callback(
        Output("buildings-map", "figure"),
        Output("bld-donut",     "figure"),
        Output("bld-area-bar",  "figure"),
        Output("bld-count-bar", "figure"),
        Input("bld-group-filter", "value"),
    )
    def refresh_buildings(active_groups):
        from pages.buildings.buildings_page import (
            make_buildings_map, make_type_donut,
            make_area_bar, make_count_bar,
        )
        ag = active_groups or []
        return (
            make_buildings_map(ag),
            make_type_donut(),
            make_area_bar(),
            make_count_bar(),
        )

    # Функциональное наполнение
    @app.callback(
        Output("functional-map",  "figure"),
        Output("func-hex-legend", "children"),
        Input("func-map-mode",    "value"),
        Input("func-poi-filter",  "value"),
    )
    def refresh_functional_map(mode, active_groups):
        from pages.functional.functional_page import make_functional_map, MAP_MODES
        from dash import html

        ag = active_groups or []
        fig = make_functional_map(mode, ag)

        cs = MAP_MODES[mode]["colorscale"]
        legend = html.Div([
            html.Div(style={
                "height": "8px", "borderRadius": "4px",
                "background": f"linear-gradient(to right, {cs[0][1]}, {cs[1][1]}, {cs[2][1]})",
                "marginBottom": "3px",
            }),
            html.Div([
                html.Span("мало",  style={"color": "#444343", "fontSize": "10px"}),
                html.Span("много", style={"color": "#444343", "fontSize": "10px"}),
            ], style={"display": "flex", "justifyContent": "space-between"}),
        ])
        return fig, legend

    # NDVI
    @app.callback(
        Output("ndvi-map-baikalsk", "figure"),
        Output("ndvi-map-irkutsk",  "figure"),
        Input("ndvi-year-slider",   "value"),
    )
    def refresh_ndvi_maps(year):
        from pages.ndvi.ndvi_page import make_city_map
        return make_city_map("baikalsk", year), make_city_map("irkutsk", year)