from pathlib import Path
import re
import time
from osmnx._errors import ResponseStatusCodeError
import folium
import geopandas as gpd
import osmnx as ox
import networkx as nx
import pandas as pd
import numpy as np
import json
from shapely.ops import unary_union
import matplotlib.pyplot as plt

from network_isochrones import make_isochrone

# Меняйте только PLACE: для каждого района создаётся собственная папка.
PLACE = "Невский район, Санкт-Петербург"
TRIP_TIME = 10  # минуты
WALK_SPEED_M_PER_MIN = 75  # 4.5 км/ч
BUFFER_M = 35

BASE_DIR = Path(__file__).resolve().parent
# Добавляем хеш, чтобы разные PLACE не столкнулись после очистки имени.
import hashlib
place_slug = re.sub(r"[^\w-]+", "_", PLACE, flags=re.UNICODE).strip("_")
place_hash = hashlib.sha256(PLACE.encode("utf-8")).hexdigest()[:8]
DATA_DIR = BASE_DIR / "data" / f"{place_slug}_{place_hash}"
DATA_DIR.mkdir(parents=True, exist_ok=True)

GRAPH_FILE = DATA_DIR / "walk.graphml"
DOCTORS_FILE = DATA_DIR / "doctors.gpkg"
RESIDENTIAL_FILE = DATA_DIR / "residential.gpkg"
HOUSES_FILE = DATA_DIR / "living_houses.gpkg"

ox.settings.use_cache = True
ox.settings.cache_folder = str(BASE_DIR / "data" / "osmnx_cache")
ox.settings.log_console = True
print(f"Район: {PLACE}")
print(f"Каталог данных: {DATA_DIR}")

# Граница района нужна для единого пространственного охвата анализа.
district = ox.geocode_to_gdf(PLACE)

# Пешеходная сеть; время на каждом ребре задаётся в минутах.

# Файл для сохранения графа


# Если граф уже сохранён — загружаем с диска
if GRAPH_FILE.exists():
    print("Загружаем пешеходную сеть из файла...")
    g_walk = ox.load_graphml(GRAPH_FILE)

# Если файла нет — скачиваем из OSM
else:
    print("Загружаем пешеходную сеть из OpenStreetMap...")


# Загрузка пешеходной сети с повторными попытками

if GRAPH_FILE.exists():
    print("Загружаем пешеходную сеть с диска...")
    g_walk = ox.load_graphml(GRAPH_FILE)

else:
    print("Загружаем пешеходную сеть из OSM...")

    max_attempts = 5

    for attempt in range(max_attempts):
        try:
            g_walk = ox.graph_from_place(
                PLACE,
                network_type="walk"
            )

            ox.save_graphml(
                g_walk,
                filepath=GRAPH_FILE
            )

            print("Граф успешно загружен и сохранён!")
            break

        except ResponseStatusCodeError as error:
            if attempt == max_attempts - 1:
                raise RuntimeError(
                    "Не удалось загрузить граф: "
                    "сервер Overpass API недоступен."
                ) from error

            wait_seconds = min(15 * (2 ** attempt), 120)

            print(
                f"Ошибка Overpass API. "
                f"Попытка {attempt + 1}/{max_attempts}. "
                f"Повтор через {wait_seconds} сек."
            )

            time.sleep(wait_seconds)


    # Сохраняем граф для следующих запусков
    ox.save_graphml(
        g_walk,
        filepath=GRAPH_FILE
    )

    print("Граф сохранён!")

print(
    f"Пешеходная сеть: "
    f"{len(g_walk.nodes)} узлов, "
    f"{len(g_walk.edges)} рёбер"
)


for u, v, key, data in g_walk.edges(keys=True, data=True):
    length = data.get("length")
    if length is None:
        raise ValueError(f"У ребра {(u, v, key)} отсутствует length")
    data["time"] = float(length) / WALK_SPEED_M_PER_MIN

g_walk_proj = ox.project_graph(g_walk)
metric_crs = g_walk_proj.graph["crs"]
district_metric = district.to_crs(metric_crs)
district_geom = district_metric.geometry.union_all()

# OSMnx выбирает объекты, подходящие хотя бы под один из тегов.
tags = {
    "amenity": ["clinic", "doctors", "hospital"],
    "healthcare": ["clinic", "doctor", "hospital"],
}


#загрузка и сохранение поликлиник

# OSMnx выбирает объекты, подходящие хотя бы под один из тегов.
tags = {
    "amenity": ["clinic", "doctors", "hospital"],
    "healthcare": ["clinic", "doctor", "hospital"],
}


if DOCTORS_FILE.exists():
    print("Загружаем поликлиники с диска...")
    doctors = gpd.read_file(DOCTORS_FILE)
else:
    print("Загружаем поликлиники из OSM...")

    doctors = ox.features_from_place(PLACE, tags)


    # GeoPackage не поддерживает некоторые сложные
    # типы атрибутов OSM, поэтому сохраняем
    # только необходимые для анализа поля.
    doctors = doctors.reset_index()

    keep_cols = [
        c for c in [
            "element",
            "id",
            "name",
            "amenity",
            "healthcare",
            "geometry"
        ]
        if c in doctors.columns
    ]

    doctors = doctors[keep_cols].copy()
    doctors.to_file(DOCTORS_FILE, driver="GPKG")

    print("Поликлиники сохранены!")

print(f"Загружено медицинских объектов: {len(doctors)}")

doctors = doctors.loc[doctors.geometry.notna()].copy()
if doctors.empty:
    raise ValueError("В OSM не найдены медицинские объекты по указанным тегам")

if "name" not in doctors.columns:
    raise ValueError("У найденных медицинских объектов отсутствует колонка name")

pattern = re.compile(r"(поликлиника|цовп)", flags=re.IGNORECASE)
doctors = doctors.loc[
    doctors["name"].fillna("").astype(str).str.contains(pattern, na=False)
].copy()
if doctors.empty:
    raise ValueError("После фильтрации названий не осталось поликлиник/ЦОВП")
print(f"Отфильтровано поликлиник/ЦОВП: {len(doctors)}")

# Точки учреждений: для полигонов берём центроид в метрической CRS.
doctors_metric = doctors.to_crs(metric_crs)
doctors_metric["geometry"] = doctors_metric.geometry.centroid
doctors_pts = doctors_metric.to_crs("EPSG:4326")

# Идентификаторы узлов сохраняются после ox.project_graph().
doctors_nodes = ox.distance.nearest_nodes(
    g_walk_proj,
    X=doctors_metric.geometry.x.to_numpy(),
    Y=doctors_metric.geometry.y.to_numpy(),
)

# Возвращаемые make_isochrone полигоны имеют CRS проецированного графа.
isochrones = []
for node in set(doctors_nodes):
    poly = make_isochrone(
        g_walk_proj,
        node,
        max_time=TRIP_TIME,
        buffer_m=BUFFER_M,
    )
    if poly is not None and not poly.is_empty:
        isochrones.append(poly)
if not isochrones:
    raise RuntimeError("Не удалось построить изохроны: проверьте time и граф")

covered_geom = unary_union(isochrones).intersection(district_geom)
covered_metric = gpd.GeoDataFrame(
    {"geometry": [covered_geom]}, crs=metric_crs
)

# Жилые территории: приводим к той же CRS и обрезаем по границе.


if RESIDENTIAL_FILE.exists():
    print("Загружаем жилые территории с диска...")
    residential = gpd.read_file(RESIDENTIAL_FILE)

else:
    print("Загружаем жилые территории из OSM...")

    residential = ox.features_from_place(
        PLACE,
        {"landuse": "residential"}
    )

    # Оставляем полигоны жилых территорий
    residential = residential[
        residential.geom_type.isin(
            ["Polygon", "MultiPolygon"]
        )
    ].copy()

    # Оставляем необходимые столбцы
    residential = residential[
        ["landuse", "geometry"]
    ].reset_index(drop=True)

    residential.to_file(
        RESIDENTIAL_FILE,
        driver="GPKG"
    )

    print("Жилые территории сохранены!")

print(
    f"Загружено жилых территорий: {len(residential)}"
)
residential = residential.loc[
    residential.geometry.notna()
    & residential.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
].copy()
if residential.empty:
    raise ValueError("Не найдены полигональные жилые территории landuse=residential")

residential_metric = residential.to_crs(metric_crs)


# Объединение убирает двойной учёт перекрывающихся жилых полигонов.
residential_geom = residential_metric.geometry.union_all().intersection(district_geom)
if residential_geom.is_empty or residential_geom.area == 0:
    raise ValueError("После обрезки по границе района жилых зон не осталось")

covered_res_geom = residential_geom.intersection(covered_geom)
deserts_geom = residential_geom.difference(covered_geom)
pct_covered = 100 * covered_res_geom.area / residential_geom.area
print(f"Доля площади жилых зон в {TRIP_TIME}-минутной доступности: {pct_covered:.1f}%")


# Загружаем жилые здания



building_tags = {
    "building": [
        "apartments",
        "residential",
        "house",
        "detached",
        "terrace"
    ]
}

if HOUSES_FILE.exists():
    print("Загружаем жилые дома с диска...")
    living_house = gpd.read_file(HOUSES_FILE)
else:
    print("Загружаем жилые дома из OSM...")

    living_house = ox.features_from_place(
        PLACE,
        building_tags
    )

    living_house = living_house[
        living_house.geom_type.isin(
            ["Polygon", "MultiPolygon"]
        )
    ].copy()

    living_house = living_house[
        ["building", "geometry"]
    ].reset_index(drop=True)

    living_house.to_file(
        HOUSES_FILE,
        driver="GPKG"
    )

    print("Жилые дома сохранены!")

print(f"Загружено жилых зданий: {len(living_house)}")
print(living_house["building"].value_counts())

# Убираем объекты без геометрии
living_house = living_house[
    living_house.geometry.notna()
].copy()

# Оставляем полигоны зданий
living_house = living_house[
    living_house.geom_type.isin(
        ["Polygon", "MultiPolygon"]
    )
].copy()

# Переводим в метрическую CRS
living_house_metric = living_house.to_crs(metric_crs)

# Создаём отдельный слой точек
living_house_pts = living_house_metric.copy()

living_house_pts["geometry"] = (
    living_house_pts.geometry.centroid
)

# ВАЖНО: граф и точки для nearest_nodes должны иметь одинаковую CRS.
# living_house_pts уже в метрической CRS, как и g_walk_proj.
living_house_pts = living_house_pts.to_crs(g_walk_proj.graph["crs"])
assert living_house_pts.crs == g_walk_proj.graph["crs"], "CRS домов и графа различаются"

living_house_pts["nearest_node"] = ox.distance.nearest_nodes(
    g_walk_proj,
    X=living_house_pts.geometry.x.to_numpy(),
    Y=living_house_pts.geometry.y.to_numpy(),
)

print("CRS графа:", g_walk_proj.graph["crs"])
print("CRS домов:", living_house_pts.crs)
print("Уникальных узлов домов:", living_house_pts["nearest_node"].nunique())
print(living_house_pts[["building", "nearest_node"]].head())

# Дейкстры

# Разворачиваем направления рёбер
g_reverse = g_walk_proj.reverse(copy=False)

# Получаем уникальные узлы поликлиник
sources = list(dict.fromkeys(doctors_nodes))
if not sources:
    raise ValueError("Список узлов поликлиник пуст")
missing_doctors = set(sources) - set(g_walk_proj.nodes)
missing_houses = set(living_house_pts["nearest_node"]) - set(g_walk_proj.nodes)
if missing_doctors or missing_houses:
    raise ValueError(
        f"Узлы отсутствуют в графе: поликлиники={len(missing_doctors)}, "
        f"дома={len(missing_houses)}"
    )

print(f"Всего объектов поликлиник: {len(doctors_nodes)}")
print(f"Уникальных узлов: {len(sources)}")

# 3. Алгоритм Дейкстры
dist_map, path_map = nx.multi_source_dijkstra(
    g_reverse,
    sources=sources,
    weight="time"
)

# 4. Минимальное время до поликлиники
living_house_pts["min_time_min"] = (
    living_house_pts["nearest_node"].map(dist_map)
)

# 5. Маршрут до ближайшей поликлиники
# path_map хранит пути в развёрнутом графе
living_house_pts["min_path"] = (
    living_house_pts["nearest_node"].apply(
        lambda node: (
            list(reversed(path_map[node]))
            if node in path_map
            else None
        )
    )
)

# 6. Узел ближайшей поликлиники
living_house_pts["doctors_nearest_node"] = (
    living_house_pts["min_path"].apply(
        lambda path: path[-1] if path else None
    )
)


# 7. Статистика
found = living_house_pts["min_time_min"].notna().sum()
total = len(living_house_pts)

print(f"Найдено маршрутов: {found} из {total}")
print(f"Без маршрута: {total - found}")

# 8. Распределение времени
print(
    living_house_pts["min_time_min"].describe()
)

# 9. Доля домов в 10-минутной доступности
accessible = (
    living_house_pts["min_time_min"] <= 10
).sum()

pct = accessible / total * 100 if total else 0

print(
    f"Доля жилых зданий в 10-минутной "
    f"доступности: {pct:.1f}%"
)

#____________________________________________________________
# Интервалы времени
bins = [0, 5, 10, 15, 20, 30, 45, float("inf")]

labels = [
    "0–5",
    "5–10",
    "10–15",
    "15–20",
    "20–30",
    "30–45",
    ">45"
]

living_house_pts["time_category"] = pd.cut(
    living_house_pts["min_time_min"],
    bins=bins,
    labels=labels,
    include_lowest=True
)

print(
    living_house_pts["time_category"]
    .value_counts()
    .sort_index()
)

# Проверяем повторяющиеся узлы
print(
    "Уникальных узлов жилых домов:",
    living_house_pts["nearest_node"].nunique()
)

print(
    "Самые частые значения времени:"
)

print(
    living_house_pts["min_time_min"]
    .round(1)
    .value_counts()
    .head(10)
)

# Гистограмма
plt.figure(figsize=(10, 5))

plt.hist(
    living_house_pts["min_time_min"].dropna(),
    bins=40,
    edgecolor="black"
)

plt.axvline(
    10,
    color="red",
    linestyle="--",
    label="Порог 10 минут"
)

plt.xlabel("Время ходьбы до ближайшей поликлиники, мин")
plt.ylabel("Количество жилых зданий")
plt.title("Распределение сетевого времени доступности")
plt.legend()
plt.tight_layout()
plt.show()
#______________________________________________________________

# ============================================
# ИНТЕРАКТИВНАЯ КАРТА FOLIUM
# ============================================

# 1. Категории доступности
def time_category(t):
    if pd.isna(t):
        return "Нет маршрута"
    elif t <= 10:
        return "до 10 мин"
    elif t <= 20:
        return "10–20 мин"
    else:
        return "больше 20 мин"


living_house_pts["time_cat"] = (
    living_house_pts["min_time_min"].apply(time_category)
)

# 2. Цвета категорий
colors = {
    "до 10 мин": "green",
    "10–20 мин": "orange",
    "больше 20 мин": "red",
    "Нет маршрута": "gray",
}

# 3. Переводим все слои в EPSG:4326
covered_wgs = covered_metric.to_crs("EPSG:4326")

deserts_wgs = gpd.GeoDataFrame(
    {"geometry": [deserts_geom]},
    crs=metric_crs
).to_crs("EPSG:4326")

district_wgs = district.to_crs("EPSG:4326")

living_house_wgs = living_house_pts.to_crs("EPSG:4326")

# 4. Создаём карту
center = [
    district_metric.geometry.representative_point().to_crs("EPSG:4326").y.mean(),
    district_metric.geometry.representative_point().to_crs("EPSG:4326").x.mean()
]

m = folium.Map(
    location=center,
    zoom_start=13,
    tiles="OpenStreetMap"
)

# 5. Граница района
folium.GeoJson(
    district_wgs,
    name="Граница района",
    style_function=lambda feature: {
        "fillOpacity": 0,
        "color": "#333333",
        "weight": 2,
    },
).add_to(m)

# 6. Изохроны
folium.GeoJson(
    covered_wgs,
    name=f"Доступность {TRIP_TIME} минут",
    style_function=lambda feature: {
        "fillColor": "green",
        "color": "green",
        "weight": 1,
        "fillOpacity": 0.25,
    },
).add_to(m)

# 7. Жилые зоны вне охвата
folium.GeoJson(
    deserts_wgs,
    name="Жилые зоны вне охвата",
    style_function=lambda feature: {
        "fillColor": "grey",
        "color": "red",
        "weight": 1,
        "fillOpacity": 0.1,
    },
).add_to(m)

# 8. Отдельный слой поликлиник
doctors_layer = folium.FeatureGroup(
    name="Поликлиники",
    show=True
)

for _, row in doctors_pts.iterrows():
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=6,
        color="blue",
        fill=True,
        fill_color="blue",
        popup=folium.Popup(
            str(row.get("name", "Поликлиника")),
            max_width=300
        ),
    ).add_to(doctors_layer)

doctors_layer.add_to(m)

# 9. Отдельный слой жилых домов
houses_layer = folium.FeatureGroup(
    name="Жилые здания по времени доступности",
    show=True
)

for _, row in living_house_wgs.iterrows():
    category = row["time_cat"]

    folium.CircleMarker(
        location=[
            row.geometry.y,
            row.geometry.x
        ],
        radius=4,
        color=colors[category],
        fill=True,
        fill_color=colors[category],
        fill_opacity=0.4,
        tooltip=(
            f"{category}: "
            f"{row['min_time_min']:.1f} мин"
            if pd.notna(row["min_time_min"])
            else "Нет маршрута"
        ),
    ).add_to(houses_layer)

houses_layer.add_to(m)

# 10. Легенда

legend_html = """
<div style="
    position: fixed;
    bottom: 20px;
    left: 20px;
    z-index: 9999;
    background: white;
    padding: 14px;
    border: 1px solid grey;
    border-radius: 6px;
    font-size: 13px;
    max-width: 310px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
">

    <b>Жилые дома по времени доступности до ближайшей поликлиники</b><br><br>

    <div style="margin-bottom: 6px;">
        <span style="
            display: inline-block;
            width: 12px;
            height: 12px;
            background: green;
            margin-right: 6px;
        "></span>
        до 10 мин
    </div>

    <div style="margin-bottom: 6px;">
        <span style="
            display: inline-block;
            width: 12px;
            height: 12px;
            background: orange;
            margin-right: 6px;
        "></span>
        10–20 мин
    </div>

    <div style="margin-bottom: 12px;">
        <span style="
            display: inline-block;
            width: 12px;
            height: 12px;
            background: red;
            margin-right: 6px;
        "></span>
        больше 20 мин — зона для рассмотрения
        размещения поликлиники
    </div>

    <hr style="border: 0; border-top: 1px solid #ddd;">

    <b>Действующие поликлиники ОМС</b><br><br>

    <div>
        <span style="
            display: inline-block;
            width: 15px;
            height: 15px;
            background: gray;
            border: 3px solid darkblue;
            border-radius: 70%;
            margin-right: 6px;
        "></span>
        действующая поликлиника
    </div>

</div>
"""

m.get_root().html.add_child(
    folium.Element(legend_html)
)
def style_func(feature):
    cat = feature["properties"]["time_cat"]
    c = colors.get(cat, "gray")          # страховка от опечаток
    return {
        "fillColor": c,
        "color": c,          # цвет контура
        "weight": 0.5,       # толщина контура (для тысяч домов тонкий лучше)
        "fillOpacity": 0.6,  # прозрачность заливки
    }
# Полигоны домов: переносим рассчитанные категории по позициям строк.
# Индексы совпадают, так как living_house_pts создан из living_house_metric.copy().
house_polygons_wgs = living_house_metric.copy()
house_polygons_wgs["time_cat"] = living_house_pts["time_cat"].to_numpy()
house_polygons_wgs["min_time_min"] = living_house_pts["min_time_min"].to_numpy()
house_polygons_wgs = house_polygons_wgs.to_crs("EPSG:4326")
house_polygons_layer = folium.FeatureGroup(name="Контуры жилых зданий", show=False)
folium.GeoJson(
    house_polygons_wgs[["time_cat", "min_time_min", "geometry"]],
    style_function=style_func,
    tooltip=folium.features.GeoJsonTooltip(
        fields=["time_cat", "min_time_min"],
        aliases=["Доступность:", "Время:"],
        localize=True,
    ),
).add_to(house_polygons_layer)
house_polygons_layer.add_to(m)

# 11. Управление слоями
folium.LayerControl(
    collapsed=False
).add_to(m)

# 12. Сохранение карты
output_path = DATA_DIR / "accessibility_map.html"

m.save(str(output_path))

print(f"Карта сохранена: {output_path}")
