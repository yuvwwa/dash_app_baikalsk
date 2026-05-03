#!/bin/bash

set -e

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo "Python3 не найден. Установка.."
    sudo apt update -q && sudo apt install -y python3 python3-pip python3-venv
fi

echo "Создаём виртуальное окружение"
python3 -m venv venv
source venv/bin/activate

echo "Устанавливаем зависимости"
pip install --upgrade pip -q
pip install \
    dash \
    plotly \
    geopandas \
    shapely \
    pandas \
    numpy \
    h3 \
    rasterio \
    geopy \
    osmnx \
    requests \
    beautifulsoup4 \
    -q

echo "Готово!"