import plotly.graph_objects as go
from dash import Patch

from data import (
    stops_unique, stops_routes_map, poi_groups,
    road_lats, road_lons,
    pois_in_buffer, circle_latlon,
    CENTER_LAT, CENTER_LON, INIT_ZOOM,
    neighborhoods_gdf,
)

ROUTE_COLORS = {4: "#EA580C", 5: "#0891B2", 6: "#0369A1"}

# Индексы traces - вычисляются после загрузки данных
_N_NBR = len(neighborhoods_gdf) if neighborhoods_gdf is not None else 0
MAX_SELECTED = 10
IDX_ROADS = _N_NBR
IDX_BUFFER = _N_NBR + 1
IDX_POI_M = {k: _N_NBR + 2 + i for i, k in enumerate(poi_groups)}
IDX_POI_T = {k: _N_NBR + 2 + 5 + i for i, k in enumerate(poi_groups)}
IDX_STOPS = _N_NBR + 12


def make_base_figure() -> go.Figure:
    # Строится один раз при запуске. Содержит статичные слои
    fig = go.Figure()

    # 0. Районы (полигоны) - самый нижний слой
    NBR_COLORS = [
        "rgba(74,144,217,0.13)",   "rgba(81,207,102,0.13)",
        "rgba(250,176,5,0.13)",    "rgba(240,101,149,0.13)",
        "rgba(134,142,150,0.13)",  "rgba(92,184,230,0.13)",
    ]
    NBR_BORDER = [
        "rgba(74,144,217,0.45)",   "rgba(81,207,102,0.45)",
        "rgba(250,176,5,0.45)",    "rgba(240,101,149,0.45)",
        "rgba(134,142,150,0.45)",  "rgba(92,184,230,0.45)",
    ]

    if neighborhoods_gdf is not None:
        name_col = next(
            (c for c in ["district_name", "name", "название"] if c in neighborhoods_gdf.columns),
            neighborhoods_gdf.columns[0]
        )
        for idx, row in neighborhoods_gdf.iterrows():
            geom = row.geometry
            color_i = idx % len(NBR_COLORS)
            polys = ([geom] if geom.geom_type == "Polygon"
                     else list(geom.geoms) if geom.geom_type == "MultiPolygon"
                     else [])
            lats_p, lons_p = [], []
            for poly in polys:
                xs, ys = poly.exterior.xy
                lons_p.extend(list(xs) + [None])
                lats_p.extend(list(ys) + [None])

            fig.add_trace(go.Scattermap(
                lat=lats_p, lon=lons_p,
                mode="lines",
                fill="toself",
                fillcolor=NBR_COLORS[color_i],
                line=dict(color=NBR_BORDER[color_i], width=1.2),
                hovertemplate=f"<b>{row[name_col]}</b><extra></extra>",
                showlegend=False,
                name=str(row[name_col]),
            ))

    # Дороги
    fig.add_trace(go.Scattermap(
        lat=road_lats, lon=road_lons,
        mode="lines",
        line=dict(color="#111111", width=1),
        hoverinfo="skip",
        showlegend=False,
        name="roads",
    ))

    # Буферные слоты (MAX_SELECTED штук)
    for _bi in range(MAX_SELECTED):
        fig.add_trace(go.Scattermap(
            lat=[], lon=[],
            mode="lines", fill="toself",
            fillcolor="rgba(255,200,200,0.20)",
            line=dict(color="rgba(255,100,100,0.70)", width=1.5),
            hoverinfo="skip", showlegend=False, name=f"buffer_{_bi}",
        ))

    # POI маркеры (5 placeholders)
    for gkey in poi_groups:
        g = poi_groups[gkey]
        fig.add_trace(go.Scattermap(
            lat=[], lon=[], mode="markers",
            marker=dict(size=16, color=g["color"], opacity=1.0),
            customdata=[],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "%{customdata[1]}<br>"
                "%{customdata[2]} м от остановки"
                "<extra></extra>"
            ),
            showlegend=False, name=f"poi_m_{gkey}",
        ))

    # POI текст (5 placeholders, не используем)
    for gkey in poi_groups:
        fig.add_trace(go.Scattermap(
            lat=[], lon=[], mode="text", text=[],
            hoverinfo="skip", showlegend=False, name=f"poi_t_{gkey}",
        ))

    # 5. Остановки
    stop_hovers = []
    for _, row in stops_unique.iterrows():
        routes = stops_routes_map.get(row.stop_name, [])
        r_str = "  ".join(
            f'<span style="color:{ROUTE_COLORS.get(r,"#aaa")}">●</span> №{r}'
            for r in routes
        )
        stop_hovers.append(f"<b>{row.stop_name}</b><br>{r_str}")

    fig.add_trace(go.Scattermap(
        lat=stops_unique["lat"].tolist(),
        lon=stops_unique["lon"].tolist(),
        mode="markers",
        marker=dict(size=10, color="#111111", opacity=1, allowoverlap=True),
        text=stop_hovers,
        customdata=stops_unique["stop_name"].tolist(),
        hovertemplate="%{text}<extra></extra>",
        showlegend=False, name="stops",
    ))

    fig.update_layout(
        map=dict(
            style="carto-positron",
            center=dict(lat=CENTER_LAT, lon=CENTER_LON),
            zoom=INIT_ZOOM,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#FFFFFF",
        uirevision="never-reset",
        clickmode="event+select",
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            font=dict(color="#111111", family="IBM Plex Sans, sans-serif", size=13),
            bordercolor="#2563EB",
        ),
    )
    return fig


MAX_SELECTED = 10 # максимум одновременно выбранных остановок

# Количество слотов для буферов в базовой фигуре
# Структура: [N_NBR районов] + [дороги] + [MAX_SELECTED буферов] + [POI*5 маркеры] + [POI*5 текст] + [остановки]
IDX_ROADS = _N_NBR
IDX_BUFFERS = [_N_NBR + 1 + i for i in range(MAX_SELECTED)]          # 10 буферных слотов
_POI_BASE = _N_NBR + 1 + MAX_SELECTED
IDX_POI_M = {k: _POI_BASE + i       for i, k in enumerate(poi_groups)}   # маркеры
IDX_POI_T = {k: _POI_BASE + 5 + i   for i, k in enumerate(poi_groups)}   # текст
IDX_STOPS = _POI_BASE + 10


def _buffer_color(poi_count: int, max_count: int) -> tuple:
    # Возвращает (fillcolor, linecolor) градиент белый-розовый-красный.
    # При 0 POI - едва заметный серо-голубой контур
    if max_count == 0 or poi_count == 0:
        # Нулевые буферы - видимые, но нейтральные
        return "rgba(150,180,210,0.10)", "rgba(150,180,210,0.50)"

    t = min(poi_count / max_count, 1.0)
    # RGB интерполяция: светло-розовый (255,220,230) - розовый (255,150,180) - красный (200,30,60)
    if t < 0.5:
        s = t * 2
        r = 255
        g = int(220 - s * 70)   # 220 -> 150
        b = int(230 - s * 50)   # 230 -> 180
    else:
        s = (t - 0.5) * 2
        r = int(255 - s * 55)   # 255 -> 200
        g = int(150 - s * 120)  # 150 -> 30
        b = int(180 - s * 120)  # 180 -> 60
    fill = f"rgba({r},{g},{b},0.22)"
    line = f"rgba({r},{g},{b},0.80)"
    return fill, line


def make_patch(active_groups: list, selected_stops: list) -> Patch:
    # Обновляет буферы и POI для списка выбранных остановок.
    # selected_stops: список названий остановок (до MAX_SELECTED)

    p = Patch()
    selected_stops = (selected_stops or [])[:MAX_SELECTED]

    # Считаем кол-во POI в каждом буфере для градиента
    poi_counts = []
    stop_rows = []
    for sname in selected_stops:
        rows = stops_unique[stops_unique.stop_name == sname]
        if len(rows) == 0:
            poi_counts.append(0)
            stop_rows.append(None)
            continue
        srow = rows.iloc[0]
        stop_rows.append(srow)
        cnt = sum(
            len(pois_in_buffer(srow.lat, srow.lon, gkey))
            for gkey in (active_groups or [])
        )
        poi_counts.append(cnt)

    max_count = max(poi_counts) if poi_counts else 1

    # Заполняем буферные слоты
    for slot_i in range(MAX_SELECTED):
        idx = IDX_BUFFERS[slot_i]
        if slot_i < len(selected_stops) and stop_rows[slot_i] is not None:
            srow = stop_rows[slot_i]
            blats, blons = circle_latlon(srow.lat, srow.lon)
            fill, line_c = _buffer_color(poi_counts[slot_i], max_count)
            p["data"][idx]["lat"] = blats
            p["data"][idx]["lon"] = blons
            p["data"][idx]["fillcolor"] = fill
            p["data"][idx]["line"]["color"] = line_c
        else:
            # Пустой слот
            p["data"][idx]["lat"] = []
            p["data"][idx]["lon"] = []

    # POI - объединяем точки всех выбранных остановок
    for gkey in poi_groups:
        mi = IDX_POI_M[gkey]
        ti = IDX_POI_T[gkey]
        g = poi_groups[gkey]

        if gkey in (active_groups or []) and selected_stops:
            all_lats, all_lons, all_cd = [], [], []
            for srow in stop_rows:
                if srow is None:
                    continue
                sub = pois_in_buffer(srow.lat, srow.lon, gkey)
                if len(sub):
                    all_lats.extend(sub["lat"].tolist())
                    all_lons.extend(sub["lon"].tolist())
                    all_cd.extend([
                        [r["name"], g["label"], str(int(r["dist_m"]))]
                        for _, r in sub.iterrows()
                    ])
            p["data"][mi]["lat"] = all_lats
            p["data"][mi]["lon"] = all_lons
            p["data"][mi]["customdata"] = all_cd
        else:
            p["data"][mi]["lat"] = []
            p["data"][mi]["lon"] = []
            p["data"][mi]["customdata"] = []

        p["data"][ti]["lat"] = []
        p["data"][ti]["lon"] = []

    return p


# Строим при импорте
BASE_FIGURE = make_base_figure()