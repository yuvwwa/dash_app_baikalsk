import pandas as pd
import numpy as np
import geopandas as gpd
import os as _os2
import os as _os

DATA_DIR = "data"

def _p(filename):
    # Путь к файлу данных
    return _os2.path.join(DATA_DIR, filename)


# Остановки и маршруты

routes_stops_df = pd.read_csv(_p("baikalsk_routes_stops.csv"))
stops_coords_df = pd.read_csv(_p("baikalsk_stops_routes_coords_final.csv"))

stops_unique = (
    stops_coords_df
    .drop_duplicates("stop_name")[["stop_name", "lat", "lon"]]
    .reset_index(drop=True)
)

stops_routes_map = (
    stops_coords_df
    .groupby("stop_name")["route"]
    .apply(lambda x: sorted(x.unique().tolist()))
    .to_dict()
)

# Геоданные

roads_gdf = gpd.read_file(_p("baikal_roads_clipped.geojson"))
boundary_gdf = gpd.read_file(_p("baikalsk_boundary.geojson"))

boundary_shape = boundary_gdf.geometry.unary_union

# bbox для вспомогательных расчётов
_bounds = boundary_gdf.geometry.total_bounds   # minx, miny, maxx, maxy
LAT_MIN = stops_unique["lat"].min() - 0.005
LAT_MAX = stops_unique["lat"].max() + 0.005
LON_MIN = stops_unique["lon"].min() - 0.008
LON_MAX = stops_unique["lon"].max() + 0.008

CENTER_LAT = (_bounds[1] + _bounds[3]) / 2
CENTER_LON = (_bounds[0] + _bounds[2]) / 2
_span = max(_bounds[3] - _bounds[1], _bounds[2] - _bounds[0])
INIT_ZOOM = 13 if _span < 0.05 else 12 if _span < 0.15 else 11

# POI

def _norm(obj):
    obj = obj.copy()
    obj.columns = [c.strip().lower() for c in obj.columns]
    for col in ["name", "название", "title", "имя", "наименование"]:
        if col in obj.columns:
            return obj.rename(columns={col: "name"})
    obj["name"] = [f"Объект #{i+1}" for i in range(len(obj))]
    return obj

def load_csv(path):
    return _norm(pd.read_csv(path))[["lat", "lon", "name"]].dropna().reset_index(drop=True)

def load_geojson(path):
    gdf = _norm(gpd.read_file(path))
    if "lat" not in gdf.columns or "lon" not in gdf.columns:
        gdf["lon"] = gdf.geometry.x
        gdf["lat"] = gdf.geometry.y
    return gdf[["lat", "lon", "name"]].dropna().reset_index(drop=True)

cafe_df = load_csv(_p("cafe_baikalsk_clean.csv"))
parks_df = load_csv(_p("parks_baikalsk.csv"))
hotels_df = load_csv(_p("hotels_baikalsk.csv"))
hospitals_df = load_csv(_p("hospitals_baikalsk.csv"))
places_df = load_csv(_p("places_baikalsk.csv"))

poi_groups = {
    "cafes": {"df": cafe_df, "label": "Кафе", "color": "#FF6B6B"},
    "parks": {"df": parks_df, "label": "Парки", "color": "#51CF66"},
    "hotels": {"df": hotels_df, "label": "Отели", "color": "#339AF0"},
    "hospitals": {"df": hospitals_df, "label": "Больницы", "color": "#F06595"},
    "places": {"df": places_df, "label": "Достопримечательности", "color": "#FAB005"},
}

# Буфер и расстояния

BUFFER_KM = 0.5
BUF_LAT = BUFFER_KM / 111.0
BUF_LON = BUFFER_KM / (111.0 * np.cos(np.radians(51.5)))

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dp = np.radians(lat2 - lat1)
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dl/2)**2
    return R * 2 * np.arcsin(np.sqrt(a))

def pois_in_buffer(slat, slon, group_key):
    df = poi_groups[group_key]["df"].copy()
    dlat = (df["lat"] - slat) / BUF_LAT
    dlon = (df["lon"] - slon) / BUF_LON
    sub = df[(dlat**2 + dlon**2) <= 1.0].copy()
    if len(sub):
        sub["dist_m"] = sub.apply(
            lambda r: haversine_m(slat, slon, r.lat, r.lon), axis=1
        )
    return sub

def circle_latlon(lat, lon, n=64):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    lats = (lat + BUF_LAT * np.sin(a)).tolist()
    lons = (lon + BUF_LON * np.cos(a)).tolist()
    return lats + [lats[0]], lons + [lons[0]]

# Дороги -> плоские списки для Plotly

road_lats, road_lons = [], []
for geom in roads_gdf.geometry:
    if geom is None:
        continue
    lines = ([geom] if geom.geom_type == "LineString"
             else list(geom.geoms) if geom.geom_type == "MultiLineString"
             else [])
    for line in lines:
        xs, ys = line.xy
        road_lons.extend(list(xs) + [None])
        road_lats.extend(list(ys) + [None])


# Данные застройки

# Категории зданий -> укрупнённые группы и цвета
BUILDING_GROUPS = {
    "residential": {
        "types": ["apartments", "residential", "house"],
        "label": "Жилая",
        "color": "#4ECDC4",
    },
    "commercial": {
        "types": ["commercial", "retail", "kiosk"],
        "label": "Коммерческая",
        "color": "#FF6B6B",
    },
    "public": {
        "types": ["public", "hospital", "train_station"],
        "label": "Общественная",
        "color": "#FAB005",
    },
    "industrial": {
        "types": ["industrial", "garages", "roof"],
        "label": "Промышленная / прочее",
        "color": "#868E96",
    },
}

# Обратный словарь: тип здания -> группа
BUILDING_TYPE_TO_GROUP = {
    t: gkey
    for gkey, ginfo in BUILDING_GROUPS.items()
    for t in ginfo["types"]
}

buildings_gdf = None
neighborhoods_gdf = None

_bld_path = _p("baikalsk_analiz_zastroyki.geojson")
if _os.path.exists(_bld_path):
    buildings_gdf = gpd.read_file(_bld_path)
    buildings_gdf["group"] = buildings_gdf["building"].map(
        BUILDING_TYPE_TO_GROUP
    ).fillna("industrial")
    buildings_gdf["group_label"] = buildings_gdf["group"].map(
        lambda g: BUILDING_GROUPS[g]["label"]
    )
    buildings_gdf["group_color"] = buildings_gdf["group"].map(
        lambda g: BUILDING_GROUPS[g]["color"]
    )

_nbr_path = _p("baikalsk_neighborhoods.geojson")
if _os.path.exists(_nbr_path):
    neighborhoods_gdf = gpd.read_file(_nbr_path)