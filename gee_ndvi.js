// https://code.earthengine.google.com/

// ndvi_baikalsk_YYYY.tif - растр NDVI за год (медианный композит)
// ndvi_irkutsk_YYYY.tif - то же для Иркутска
// ndvi_stats_baikalsk.csv - статистика по годам (mean, median, std, p25, p75)
// ndvi_stats_irkutsk.csv - то же для Иркутска


// Границы городов (точные полигоны из OSM)
var baikalsk = ee.Geometry.Polygon([[104.11753, 51.52273], [104.12203, 51.52205], [104.11872, 51.51485], [104.11983, 51.513], [104.11769, 51.50764], [104.12231, 51.50674], [104.12214, 51.51003], [104.12418, 51.51185], [104.12268, 51.51305], [104.12468, 51.51529], [104.13815, 51.51074], [104.13743, 51.50335], [104.14223, 51.49863], [104.15322, 51.5033], [104.15272, 51.50651], [104.17221, 51.50582], [104.17442, 51.5076], [104.1995, 51.50192], [104.20214, 51.50435], [104.20112, 51.51021], [104.18288, 51.52342], [104.16507, 51.52626], [104.14456, 51.52678], [104.11804, 51.52479], [104.11753, 51.52273]]);
var irkutsk = ee.Geometry.Polygon([[104.05892, 52.39701], [104.10006, 52.37727], [104.08618, 52.37015], [104.09121, 52.36676], [104.11448, 52.36563], [104.14894, 52.34538], [104.15266, 52.33991], [104.14168, 52.33742], [104.15106, 52.3286], [104.16184, 52.33355], [104.172, 52.32145], [104.18249, 52.32902], [104.19284, 52.31902], [104.2193, 52.30948], [104.20146, 52.30518], [104.19722, 52.29616], [104.18742, 52.29263], [104.18612, 52.28932], [104.19946, 52.28156], [104.18802, 52.27468], [104.19317, 52.26746], [104.18806, 52.2632], [104.19891, 52.25932], [104.19591, 52.25659], [104.19897, 52.25453], [104.21014, 52.25331], [104.18939, 52.24488], [104.19444, 52.24182], [104.22546, 52.24506], [104.2246, 52.25425], [104.23765, 52.24633], [104.25034, 52.2478], [104.26129, 52.24396], [104.26562, 52.2324], [104.28, 52.21765], [104.30079, 52.21364], [104.31822, 52.21801], [104.3222, 52.2096], [104.34928, 52.20923], [104.37755, 52.24024], [104.37113, 52.24574], [104.38617, 52.25244], [104.36477, 52.25404], [104.36502, 52.25921], [104.36055, 52.26001], [104.36362, 52.26298], [104.37954, 52.2648], [104.43256, 52.25639], [104.37292, 52.27552], [104.37386, 52.28372], [104.39616, 52.28694], [104.4086, 52.29513], [104.43035, 52.28805], [104.44412, 52.28957], [104.44519, 52.2954], [104.4367, 52.30146], [104.44847, 52.31008], [104.42042, 52.34003], [104.40133, 52.35461], [104.37077, 52.36721], [104.35582, 52.37121], [104.33317, 52.36758], [104.3212, 52.33791], [104.3095, 52.33404], [104.28894, 52.34615], [104.28233, 52.35717], [104.19286, 52.38469], [104.18491, 52.38941], [104.18077, 52.39928], [104.16279, 52.40263], [104.14082, 52.39989], [104.10822, 52.42167], [104.08884, 52.41135], [104.07815, 52.39985], [104.06409, 52.40355], [104.05892, 52.39701]]);

// Параметры
var YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025];
var MONTH_START = 5; // май - начало вегетационного периода
var MONTH_END = 9; // сентябрь - конец
var CLOUD_THR = 20; // максимальная облачность снимка, %
var SCALE = 30; // разрешение в метрах (Landsat 30м, Sentinel-2 10м)

// Функция расчёта NDVI
// Используем Sentinel-2 SR (Surface Reflectance)
// B8 = NIR, B4 = Red
function addNDVI(image) {
  var ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI");
  return image.addBands(ndvi);
}

function maskClouds(image) {
  var qa = image.select("QA60");
  // Биты 10 и 11 - облака и перистые облака
  var cloudBitMask = 1 << 10;
  var cirrusBitMask = 1 << 11;
  var mask = qa.bitwiseAnd(cloudBitMask).eq(0)
               .and(qa.bitwiseAnd(cirrusBitMask).eq(0));
  return image.updateMask(mask).divide(10000);  // нормализация SR
}

// Получение медианного NDVI-композита за вегетационный период
function getNDVIComposite(geometry, year) {
  var startDate = ee.Date.fromYMD(year, MONTH_START, 1);
  var endDate = ee.Date.fromYMD(year, MONTH_END, 30);

  var collection = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(geometry)
    .filterDate(startDate, endDate)
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", CLOUD_THR))
    .map(maskClouds)
    .map(addNDVI);

  // Если снимков нет, то возвращаем пустой образ
  var count = collection.size();
  var composite = ee.Algorithms.If(
    count.gt(0),
    collection.select("NDVI").median().clip(geometry),
    ee.Image.constant(-9999).rename("NDVI").clip(geometry)
  );

  return ee.Image(composite);
}

// Функция расчёта статистики NDVI по геометрии
function computeStats(geometry, year) {
  var composite = getNDVIComposite(geometry, year);

  var stats = composite.select("NDVI").reduceRegion({
    reducer: ee.Reducer.mean()
              .combine(ee.Reducer.median(), "", true)
              .combine(ee.Reducer.stdDev(), "", true)
              .combine(ee.Reducer.percentile([25, 75]), "", true)
              .combine(ee.Reducer.min(), "", true)
              .combine(ee.Reducer.max(), "", true)
              .combine(ee.Reducer.count(), "", true),
    geometry: geometry,
    scale: SCALE,
    maxPixels: 1e10,
    bestEffort: true
  });

  return ee.Feature(null, stats.set("year", year));
}

// Экспорт растров NDVI (один файл на год и город)
function exportRasters(geometry, cityName) {
  YEARS.forEach(function(year) {
    var composite = getNDVIComposite(geometry, year);
    Export.image.toDrive({
      image: composite.select("NDVI").multiply(10000).toInt16(),  // экономим место
      description: "ndvi_" + cityName + "_" + year,
      folder: "ndvi_export",
      fileNamePrefix: "ndvi_" + cityName + "_" + year,
      region: geometry,
      scale: SCALE,
      crs: "EPSG:4326",
      maxPixels: 1e10,
      fileFormat: "GeoTIFF"
    });
  });
}

// Экспорт статистики (один CSV на город)
function exportStats(geometry, cityName) {
  var statsCollection = ee.FeatureCollection(
    YEARS.map(function(year) {
      return computeStats(geometry, year);
    })
  );

  Export.table.toDrive({
    collection: statsCollection,
    description: "ndvi_stats_" + cityName,
    folder: "ndvi_export",
    fileNamePrefix: "ndvi_stats_" + cityName,
    fileFormat: "CSV"
  });
}

// Предпросмотр на карте (последний год)
var ndviVis = {
  min: -0.1,
  max: 0.8,
  palette: [
    "#d73027",  // < 0 = вода/снег/асфальт (красный)
    "#fc8d59",  // 0-0.1 = голая почва
    "#fee08b",  // 0.1-0.2 = редкая растительность
    "#d9ef8b",  // 0.2-0.3
    "#91cf60",  // 0.3-0.5 = умеренная зелень
    "#1a9850",  // 0.5-0.7 = густая растительность
    "#006837",  // > 0.7 = очень густая (тёмно-зелёный)
  ]
};

var previewYear = 2024;
var baikalskPreview = getNDVIComposite(baikalsk, previewYear);
var irkutskPreview = getNDVIComposite(irkutsk,  previewYear);

Map.centerObject(baikalsk, 12);
Map.addLayer(baikalskPreview.select("NDVI"), ndviVis, "NDVI Байкальск " + previewYear);
Map.addLayer(irkutskPreview.select("NDVI"), ndviVis, "NDVI Иркутск " + previewYear);

// Легенда на карте
var legend = ui.Panel({style: {position: "bottom-left", padding: "8px 15px"}});
legend.add(ui.Label("NDVI 2024", {fontWeight: "bold", fontSize: "14px"}));
[
  ["> 0.5","#1a9850", "Густая растительность"],
  ["0.3-0.5","#91cf60", "Умеренная"],
  ["0.1-0.3","#fee08b", "Редкая"],
  ["< 0.1","#fc8d59", "Почва / застройка"],
  ["< 0","#d73027", "Вода / асфальт"],
].forEach(function(item) {
  var row = ui.Panel({layout: ui.Panel.Layout.flow("horizontal")});
  row.add(ui.Label("", {backgroundColor: item[1], padding: "8px", margin: "0 8px 0 0"}));
  row.add(ui.Label(item[0] + " - " + item[2], {margin: "0", fontSize: "11px"}));
  legend.add(row);
});
Map.add(legend);

// ЭКСПОРТ СЕТКИ NDVI
// Для каждого года и города создаём регулярную сетку точек с координатами и значением NDVI. 
// Это используется в дашборде для отображения тепловой карты (вместо тяжёлых GeoTIFF).

var GRID_STEP_B = 0.001;   // ~80 м для Байкальска
var GRID_STEP_I = 0.003;   // ~250 м для Иркутска

function exportGrid(geometry, cityName, gridStep) {
  // Создаём регулярную сетку точек внутри геометрии
  var bounds = geometry.bounds();
  var coords = ee.List(bounds.coordinates().get(0));

  var xMin = ee.Number(ee.List(coords.get(0)).get(0));
  var yMin = ee.Number(ee.List(coords.get(0)).get(1));
  var xMax = ee.Number(ee.List(coords.get(2)).get(0));
  var yMax = ee.Number(ee.List(coords.get(2)).get(1));

  var xSteps = xMax.subtract(xMin).divide(gridStep).int();
  var ySteps = yMax.subtract(yMin).divide(gridStep).int();

  var xList = ee.List.sequence(0, xSteps).map(function(i) {
    return xMin.add(ee.Number(i).multiply(gridStep));
  });
  var yList = ee.List.sequence(0, ySteps).map(function(i) {
    return yMin.add(ee.Number(i).multiply(gridStep));
  });

  // Все точки сетки как FeatureCollection
  var points = ee.FeatureCollection(
    xList.map(function(x) {
      return yList.map(function(y) {
        var pt = ee.Geometry.Point([x, y]);
        return ee.Feature(pt, {lon: x, lat: y});
      });
    }).flatten()
  ).filterBounds(geometry);

  // Для каждого года добавляем значение NDVI в точках
  var allYears = ee.FeatureCollection(
    YEARS.map(function(year) {
      var composite = getNDVIComposite(geometry, year);

      var sampled = composite.select("NDVI").sampleRegions({
        collection: points,
        scale: SCALE,
        tileScale: 4,
        geometries: true,
      }).map(function(f) {
        return f.set("year", year);
      });

      return sampled;
    })
  ).flatten();

  Export.table.toDrive({
    collection: allYears,
    description: "ndvi_grid_" + cityName,
    folder: "ndvi_export",
    fileNamePrefix: "ndvi_grid_" + cityName,
    fileFormat: "CSV",
    selectors: ["lon", "lat", "NDVI", "year"],
  });
}

exportStats(baikalsk, "baikalsk");
exportStats(irkutsk, "irkutsk");
exportGrid(baikalsk, "baikalsk", GRID_STEP_B);
exportGrid(irkutsk, "irkutsk", GRID_STEP_I);
exportRasters(baikalsk, "baikalsk");
exportRasters(irkutsk, "irkutsk");