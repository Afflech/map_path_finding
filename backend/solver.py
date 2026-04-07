import math
import os

import networkx as nx
import osmnx as ox

ox.settings.log_console = False

VEHICLE_SPEED_KMH = {"walk": 5, "bike": 30, "car": 50}
JAMMED_PENALTY_FACTOR = 8.0
FLOODED_BIKE_PENALTY_FACTOR = 20.0
FLOODED_BLOCKED_VEHICLES = {"walk", "car"}


def load_graph(filename="map_dong_da.graphml"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "data", filename)
    print(f"Đang nạp: {file_path}...")
    try:
        graph = ox.load_graphml(file_path)
        print("Nạp map thành công.")
        return graph
    except Exception as error:
        print(f"Lỗi nạp map: {error}")
        return None


def _parse_point(point):
    if isinstance(point, dict):
        lat = point.get("lat")
        lon = point.get("lng", point.get("lon"))
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        lat, lon = point[0], point[1]
    else:
        raise ValueError(f"Tọa độ không hợp lệ: {point}")
    return float(lat), float(lon)


def _normalize_points(points):
    if not points:
        return []
    return [_parse_point(point) for point in points]


def _haversine_distance_m(lat1, lon1, lat2, lon2):
    earth_radius_m = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a_val = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c_val = 2 * math.atan2(math.sqrt(a_val), math.sqrt(1 - a_val))
    return earth_radius_m * c_val


def _heuristic_time(node1, node2, graph, speed_ms):
    node1_data = graph.nodes[node1]
    node2_data = graph.nodes[node2]
    distance = _haversine_distance_m(
        node1_data["y"], node1_data["x"], node2_data["y"], node2_data["x"]
    )
    return distance / speed_ms


def _flatten_length(length):
    if isinstance(length, list):
        return float(sum(length))
    return float(length)


def _pick_best_edge_attrs(graph, u, v, speed_ms, vehicle, jammed_nodes, flooded_nodes):
    edges_between = graph.get_edge_data(u, v, default={})
    if not edges_between:
        return None, float("inf"), 0.0

    best_attrs = None
    best_weight = float("inf")
    best_length = 0.0

    for attrs in edges_between.values():
        length = _flatten_length(attrs.get("length", 1.0))
        travel_time = length / speed_ms

        if u in jammed_nodes or v in jammed_nodes:
            travel_time *= JAMMED_PENALTY_FACTOR

        if u in flooded_nodes or v in flooded_nodes:
            if vehicle in FLOODED_BLOCKED_VEHICLES:
                travel_time = float("inf")
            else:
                travel_time *= FLOODED_BIKE_PENALTY_FACTOR

        if travel_time < best_weight:
            best_attrs = attrs
            best_weight = travel_time
            best_length = length

    return best_attrs, best_weight, best_length


def find_shortest_path(
    graph,
    start_coords,
    end_coords,
    vehicle="bike",
    jammed_points=None,
    flooded_points=None,
):
    try:
        start_lat, start_lon = _parse_point(start_coords)
        end_lat, end_lon = _parse_point(end_coords)
        jammed_coords = _normalize_points(jammed_points)
        flooded_coords = _normalize_points(flooded_points)

        start_node = ox.distance.nearest_nodes(graph, start_lon, start_lat)
        end_node = ox.distance.nearest_nodes(graph, end_lon, end_lat)
        jammed_nodes = {
            ox.distance.nearest_nodes(graph, lon, lat) for lat, lon in jammed_coords
        }
        flooded_nodes = {
            ox.distance.nearest_nodes(graph, lon, lat) for lat, lon in flooded_coords
        }

        speed_kmh = VEHICLE_SPEED_KMH.get(vehicle, VEHICLE_SPEED_KMH["bike"])
        speed_ms = speed_kmh / 3.6

        def weight_func(u, v, edge_data):
            attrs = edge_data if "length" in edge_data else None
            if attrs is None:
                attrs, best_weight, _ = _pick_best_edge_attrs(
                    graph, u, v, speed_ms, vehicle, jammed_nodes, flooded_nodes
                )
                return best_weight

            length = _flatten_length(attrs.get("length", 1.0))
            travel_time = length / speed_ms
            if u in jammed_nodes or v in jammed_nodes:
                travel_time *= JAMMED_PENALTY_FACTOR
            if u in flooded_nodes or v in flooded_nodes:
                if vehicle in FLOODED_BLOCKED_VEHICLES:
                    return float("inf")
                travel_time *= FLOODED_BIKE_PENALTY_FACTOR
            return travel_time

        route_nodes = nx.astar_path(
            graph,
            source=start_node,
            target=end_node,
            heuristic=lambda u, v: _heuristic_time(u, v, graph, speed_ms),
            weight=weight_func,
        )

        route_coords = []
        total_distance = 0.0
        total_time_sec = 0.0

        for idx in range(len(route_nodes) - 1):
            u = route_nodes[idx]
            v = route_nodes[idx + 1]
            edge_attrs, edge_weight, edge_length = _pick_best_edge_attrs(
                graph, u, v, speed_ms, vehicle, jammed_nodes, flooded_nodes
            )
            if edge_attrs is None or not math.isfinite(edge_weight):
                continue

            total_distance += edge_length
            total_time_sec += edge_weight

            geometry = edge_attrs.get("geometry")
            if geometry:
                for lon, lat in geometry.coords:
                    route_coords.append([float(lat), float(lon)])
            else:
                route_coords.append([float(graph.nodes[u]["y"]), float(graph.nodes[u]["x"])])

        last_node = route_nodes[-1]
        route_coords.append(
            [float(graph.nodes[last_node]["y"]), float(graph.nodes[last_node]["x"])]
        )

        path_points = [{"lat": lat, "lng": lon} for lat, lon in route_coords]
        return {
            "status": "success",
            "data": {
                "path": path_points,
                "distance_m": total_distance,
                "duration_min": total_time_sec / 60.0,
            },
            # Backward compatibility with old frontend schema.
            "path": route_coords,
            "distance": total_distance,
            "time_minutes": total_time_sec / 60.0,
        }
    except nx.NetworkXNoPath:
        return {
            "status": "error",
            "message": "Không tìm thấy tuyến phù hợp với điều kiện hiện tại.",
        }
    except ValueError as error:
        return {"status": "error", "message": str(error)}
    except Exception as error:
        return {"status": "error", "message": f"Lỗi xử lý đường đi: {error}"}