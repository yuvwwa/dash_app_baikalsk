"""
tiff_to_csv.py - конвертация TIFF файлов NDVI в CSV для дашборда
Читает data/ndvi_baikalsk_YYYY.tif и data/ndvi_irkutsk_YYYY.tif
Конвертирует в data/ndvi_grid_baikalsk.csv и data/ndvi_grid_irkutsk.csv
Формат CSV: lon, lat, ndvi, year
"""

import os
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import xy

data_dir = "data"
years = list(range(2017, 2026))

# Прореживание - каждый N-й пиксель (уменьшает размер файла)
step_baikalsk = 2
step_irkutsk = 4

# Значение nodata (GEE экспортирует -9999 или -32768 для Int16)
nodata_values = {-9999, -32768, -10000}


def tiff_to_dataframe(tiff_path: str, year: int, step: int = 1) -> pd.DataFrame:
    with rasterio.open(tiff_path) as src:
        data = src.read(1)  # первый (и единственный) band
        transform = src.transform
        nodata = src.nodata

        rows, cols = data.shape

        # Прореживаем
        row_idx = np.arange(0, rows, step)
        col_idx = np.arange(0, cols, step)
        rr, cc = np.meshgrid(row_idx, col_idx, indexing="ij")
        rr_flat = rr.flatten()
        cc_flat = cc.flatten()

        # Координаты пикселей
        lons, lats = xy(transform, rr_flat, cc_flat)
        values = data[rr_flat, cc_flat].astype(float)

        # Маска. убираем nodata и значения вне [-1, 1]
        # GEE экспортирует NDVI * 10000, поэтому делим обратно
        if values.max() > 10:
            values = values / 10000.0

        # Убираем nodata
        mask = np.ones(len(values), dtype=bool)
        if nodata is not None:
            mask &= (values != nodata / 10000.0) if nodata > 10 else (values != nodata)
        for nd in nodata_values:
            mask &= values != nd / 10000.0
            mask &= values != nd

        # Убираем физически невозможные значения
        mask &= (values >= -1.0) & (values <= 1.0)

        df = pd.DataFrame(
            {
                "lon": np.array(lons)[mask],
                "lat": np.array(lats)[mask],
                "ndvi": np.round(values[mask], 4),
                "year": year,
            }
        )
    return df


def process_city(city: str, step: int):
    # Обрабатывает все годы для одного города
    frames = []
    missing = []

    for year in years:
        path = os.path.join(data_dir, f"ndvi_{city}_{year}.tif")
        if not os.path.exists(path):
            print(f"[{year}] файл не найден: {path}")
            missing.append(year)
            continue

        df = tiff_to_dataframe(path, year, step=step)
        frames.append(df)

    result = pd.concat(frames, ignore_index=True)
    out_path = os.path.join(data_dir, f"ndvi_grid_{city}.csv")
    result.to_csv(out_path, index=False)


process_city("baikalsk", step=step_baikalsk)
process_city("irkutsk", step=step_irkutsk)
