import pandas as pd
import plotly.graph_objects as go
from data import poi_groups, stops_unique, pois_in_buffer, neighborhoods_gdf
from shapely.geometry import Point

PIE_COLORS = [g["color"] for g in poi_groups.values()]
PIE_LABELS = [g["label"]  for g in poi_groups.values()]


def make_pie(selected_stop, active_groups: list) -> go.Figure:
    """
    Круговая диаграмма POI.
    selected_stop=None - общее число по городу
    selected_stop=<name> - только в буферной зоне 500 м
    """
    active_groups = active_groups or list(poi_groups.keys())

    if selected_stop:
        row = stops_unique[stops_unique.stop_name == selected_stop].iloc[0]
        values = [
            len(pois_in_buffer(row.lat, row.lon, k)) if k in active_groups else 0
            for k in poi_groups
        ]
        title = f"{selected_stop}<br><sup>в радиусе 500 м</sup>"
    else:
        values = [
            len(poi_groups[k]["df"]) if k in active_groups else 0
            for k in poi_groups
        ]
        title = "Все POI<br><sup>по городу</sup>"

    fig = go.Figure(go.Pie(
        labels=PIE_LABELS,
        values=values,
        hole=0.52,
        marker=dict(colors=PIE_COLORS, line=dict(color="#FFFFFF", width=2)),
        textinfo="percent",
        textfont=dict(size=11, color="white", family="IBM Plex Sans"),
        hovertemplate="<b>%{label}</b><br>%{value} объектов (%{percent})<extra></extra>",
        direction="clockwise",
        sort=True,
    ))
    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=12, r=12, t=48, b=12),
        title=dict(
            text=title,
            font=dict(size=12, color="#111111", family="IBM Plex Sans"),
            x=0.5, xanchor="center", y=0.97,
        ),
        showlegend=False,
        annotations=[dict(
            text=str(sum(values)),
            x=0.5, y=0.5,
            font=dict(size=22, color="#111111", family="IBM Plex Sans"),
            showarrow=False,
        )],
    )
    return fig


def make_stops_by_neighborhood():
    # Столбчатая диаграмма - количество остановок по районам
    if neighborhoods_gdf is None or len(neighborhoods_gdf) == 0:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
            margin=dict(l=8, r=8, t=36, b=8),
            title=dict(text="Остановки по районам",
                       font=dict(size=12, color="#111111", family="IBM Plex Sans"),
                       x=0.5, xanchor="center"),
            annotations=[dict(
                text="Файл baikalsk_neighborhoods.geojson не найден",
                x=0.5, y=0.5, showarrow=False,
                font=dict(color="#2C2C2C", size=12),
            )],
            xaxis=dict(visible=False), yaxis=dict(visible=False),
        )
        return fig

    # Считаем остановки в каждом районе
    nbr = neighborhoods_gdf.copy().to_crs(epsg=4326)
    name_col = next((c for c in ["district_name", "name", "название"] if c in nbr.columns), nbr.columns[0])

    counts = []
    for _, row in nbr.iterrows():
        n = sum(
            1 for _, s in stops_unique.iterrows()
            if row.geometry.contains(Point(s.lon, s.lat))
        )
        counts.append({"district": str(row[name_col]), "count": n})

    df = pd.DataFrame(counts).sort_values("count", ascending=True)

    # Цвет баров - градиент от тусклого до насыщенного
    max_c = max(df["count"].max(), 1)
    bar_colors = [
        f"rgba(74,144,217,{0.25 + 0.65 * (v / max_c):.2f})"
        for v in df["count"]
    ]

    fig = go.Figure(go.Bar(
        x=df["count"],
        y=df["district"],
        orientation="h",
        marker=dict(
            color=bar_colors,
            line=dict(color="rgba(74,144,217,0.6)", width=0.8),
        ),
        text=df["count"],
        textposition="outside",
        textfont=dict(color="#111111", size=11, family="IBM Plex Sans"),
        hovertemplate="<b>%{y}</b><br>%{x} остановок<extra></extra>",
    ))

    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=8, r=32, t=36, b=8),
        title=dict(
            text="Остановки по районам",
            font=dict(size=12, color="#111111", family="IBM Plex Sans"),
            x=0.5, xanchor="center",
        ),
        xaxis=dict(
            showgrid=True, gridcolor="#EEEEEE", gridwidth=0.5,
            tickfont=dict(color="#111111", size=10),
            showline=False, zeroline=False,
            dtick=1,
        ),
        yaxis=dict(
            tickfont=dict(color="#111111", size=11, family="IBM Plex Sans"),
            showgrid=False,
        ),
        bargap=0.3,
    )
    return fig