import networkx as nx
import geopandas as gpd

from shapely.geometry import Point, LineString
from shapely.ops import substring



def make_isochrone(
    graph,
    source_node,
    max_time=10,
    buffer_m=35
):
    """
    Строит приближённую зону доступности
    по достижимым участкам пешеходной сети.

    max_time — минуты
    buffer_m — ширина буфера в метрах
    """

    # 1. Переводим граф в метрическую проекцию
    G = graph

    # 2. Кратчайшее время до всех достижимых узлов
    times = nx.single_source_dijkstra_path_length(
        G,
        source=source_node,
        cutoff=max_time,
        weight="time"
    )

    reachable_lines = []

    # 3. Перебираем направленные рёбра
    for u, v, key, data in G.edges(
        keys=True, data=True
    ):
        if u not in times:
            continue

        remaining_time = max_time - times[u]

        edge_time = data.get("time")

        if edge_time is None or edge_time <= 0:
            continue

        if remaining_time <= 0:
            continue

        # Геометрия ребра или прямая между узлами
        line = data.get("geometry")

        if line is None:
            line = LineString([
                (G.nodes[u]["x"], G.nodes[u]["y"]),
                (G.nodes[v]["x"], G.nodes[v]["y"])
            ])

        # Доля ребра, которую можно пройти
        fraction = min(1.0, remaining_time / edge_time)

        if fraction >= 1:
            reachable_lines.append(line)
        else:
            # Ориентируем геометрию от u к v
            start = Point(G.nodes[u]["x"], G.nodes[u]["y"])

            if Point(line.coords[-1]).distance(start) < (
                Point(line.coords[0]).distance(start)
            ):
                line = LineString(list(line.coords)[::-1])

            partial = substring(
                line,
                0,
                line.length * fraction
            )

            reachable_lines.append(partial)

    if not reachable_lines:
        return None

    # 4. Превращаем достижимые линии в GeoDataFrame
    edges_gdf = gpd.GeoDataFrame(
        geometry=reachable_lines,
        crs=G.graph["crs"]
    )

    # 5. Строим буферы в метрах
    buffered = edges_gdf.geometry.buffer(buffer_m)

    # 6. Объединяем их в один полигон
    return buffered.union_all()
