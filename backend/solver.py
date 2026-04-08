import math
import os
import random

import networkx as nx
import osmnx as ox

ox.settings.log_console = False

VEHICLE_SPEED_KMH = {"walk": 5, "bike": 30, "car": 50}
JAMMED_PENALTY_FACTOR = 8.0
FLOODED_BIKE_PENALTY_FACTOR = 20.0
FLOODED_BLOCKED_VEHICLES = {"walk", "car"}
DEFAULT_TOP_K_ROUTES = 3
MAX_DIVERSE_ATTEMPTS_MULTIPLIER = 6
RANDOM_NODE_PENALTY_MIN = 1.10
RANDOM_NODE_PENALTY_MAX = 1.45
MIN_ROUTE_DIVERGENCE_RATIO = 0.08


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


def _route_to_payload(
    graph, route_nodes, speed_ms, vehicle, jammed_nodes, flooded_nodes, node_penalties
):
    route_coords = []
    total_distance = 0.0
    total_time_sec = 0.0
    instructions = []
    previous_bearing = None

    for idx in range(len(route_nodes) - 1):
        u = route_nodes[idx]
        v = route_nodes[idx + 1]
        edge_attrs, edge_weight, edge_length = _pick_best_edge_attrs(
            graph, u, v, speed_ms, vehicle, jammed_nodes, flooded_nodes
        )
        if edge_attrs is None or not math.isfinite(edge_weight):
            continue

        node_factor = max(node_penalties.get(u, 1.0), node_penalties.get(v, 1.0))
        edge_weight *= node_factor

        total_distance += edge_length
        total_time_sec += edge_weight

        node_u = graph.nodes[u]
        node_v = graph.nodes[v]
        current_bearing = edge_attrs.get("bearing")
        if current_bearing is None:
            lat1 = math.radians(float(node_u["y"]))
            lat2 = math.radians(float(node_v["y"]))
            delta_lon = math.radians(float(node_v["x"]) - float(node_u["x"]))
            y_val = math.sin(delta_lon) * math.cos(lat2)
            x_val = math.cos(lat1) * math.sin(lat2) - (
                math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
            )
            current_bearing = (math.degrees(math.atan2(y_val, x_val)) + 360.0) % 360.0
        else:
            current_bearing = float(current_bearing)

        turn_action = "straight"
        if previous_bearing is not None:
            delta = (current_bearing - previous_bearing + 540.0) % 360.0 - 180.0
            if delta <= -25.0:
                turn_action = "left"
            elif delta >= 25.0:
                turn_action = "right"

        street_name = edge_attrs.get("name", "Đường không tên")
        if isinstance(street_name, list):
            street_name = street_name[0] if street_name else "Đường không tên"
        if not street_name:
            street_name = "Đường không tên"

        instructions.append(
            {
                "action": turn_action,
                "street": str(street_name),
                "distance_m": round(edge_length, 1),
            }
        )
        previous_bearing = current_bearing

        geometry = edge_attrs.get("geometry")
        if geometry:
            for lon, lat in geometry.coords:
                route_coords.append([float(lat), float(lon)])
        else:
            route_coords.append([float(graph.nodes[u]["y"]), float(graph.nodes[u]["x"])])

    last_node = route_nodes[-1]
    route_coords.append([float(graph.nodes[last_node]["y"]), float(graph.nodes[last_node]["x"])])

    path_points = [{"lat": lat, "lng": lon} for lat, lon in route_coords]
    return {
        "path": path_points,
        "distance_m": total_distance,
        "duration_min": total_time_sec / 60.0,
        "node_count": len(route_nodes),
        "instructions": _merge_instructions(instructions),
    }


def _merge_instructions(instructions):
    if not instructions:
        return []

    merged = []
    for step in instructions:
        action = step.get("action", "straight")
        street = step.get("street", "Đường không tên")
        distance_m = float(step.get("distance_m", 0.0))

        if merged:
            previous = merged[-1]
            if previous["action"] == action and previous["street"] == street:
                previous["distance_m"] = round(previous["distance_m"] + distance_m, 1)
                continue

        merged.append(
            {
                "action": action,
                "street": street,
                "distance_m": round(distance_m, 1),
            }
        )

    return merged


def _is_diverse_enough(candidate_nodes, accepted_routes):
    candidate_set = set(candidate_nodes)
    if not candidate_set:
        return False

    for accepted in accepted_routes:
        accepted_set = set(accepted)
        common_ratio = len(candidate_set & accepted_set) / max(len(candidate_set), 1)
        if (1.0 - common_ratio) < MIN_ROUTE_DIVERGENCE_RATIO:
            return False
    return True


def find_shortest_path(
    graph,
    start_coords,
    end_coords,
    vehicle="bike",
    jammed_points=None,
    flooded_points=None,
    top_k=DEFAULT_TOP_K_ROUTES,
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
        top_k = max(1, int(top_k))
        random_seed = hash((start_node, end_node, vehicle, len(jammed_nodes), len(flooded_nodes)))
        rng = random.Random(random_seed)
        node_penalties = {}

        def weight_func(u, v, edge_data):
            attrs = edge_data if "length" in edge_data else None
            if attrs is None:
                attrs, best_weight, _ = _pick_best_edge_attrs(
                    graph, u, v, speed_ms, vehicle, jammed_nodes, flooded_nodes
                )
                if not math.isfinite(best_weight):
                    return best_weight
                node_factor = max(node_penalties.get(u, 1.0), node_penalties.get(v, 1.0))
                return best_weight * node_factor

            length = _flatten_length(attrs.get("length", 1.0))
            travel_time = length / speed_ms
            if u in jammed_nodes or v in jammed_nodes:
                travel_time *= JAMMED_PENALTY_FACTOR
            if u in flooded_nodes or v in flooded_nodes:
                if vehicle in FLOODED_BLOCKED_VEHICLES:
                    return float("inf")
                travel_time *= FLOODED_BIKE_PENALTY_FACTOR
            node_factor = max(node_penalties.get(u, 1.0), node_penalties.get(v, 1.0))
            return travel_time * node_factor

        route_nodes_list = []
        route_payloads = []
        seen_signatures = set()
        max_attempts = max(top_k * MAX_DIVERSE_ATTEMPTS_MULTIPLIER, top_k)

        for _ in range(max_attempts):
            try:
                route_nodes = nx.astar_path(
                    graph,
                    source=start_node,
                    target=end_node,
                    heuristic=lambda u, v: _heuristic_time(u, v, graph, speed_ms),
                    weight=weight_func,
                )
            except nx.NetworkXNoPath:
                break

            signature = tuple(route_nodes)
            if signature in seen_signatures:
                for node in route_nodes[1:-1]:
                    node_penalties[node] = node_penalties.get(node, 1.0) * rng.uniform(
                        RANDOM_NODE_PENALTY_MIN, RANDOM_NODE_PENALTY_MAX
                    )
                continue

            seen_signatures.add(signature)
            if route_nodes_list and not _is_diverse_enough(route_nodes, route_nodes_list):
                for node in route_nodes[1:-1]:
                    node_penalties[node] = node_penalties.get(node, 1.0) * rng.uniform(
                        RANDOM_NODE_PENALTY_MIN, RANDOM_NODE_PENALTY_MAX
                    )
                continue

            route_nodes_list.append(route_nodes)
            route_payload = _route_to_payload(
                graph, route_nodes, speed_ms, vehicle, jammed_nodes, flooded_nodes, node_penalties
            )
            route_payload["rank"] = len(route_payloads) + 1
            route_payloads.append(route_payload)

            for node in route_nodes[1:-1]:
                node_penalties[node] = node_penalties.get(node, 1.0) * rng.uniform(
                    RANDOM_NODE_PENALTY_MIN, RANDOM_NODE_PENALTY_MAX
                )

            if len(route_payloads) >= top_k:
                break

        if not route_payloads:
            raise nx.NetworkXNoPath

        primary_route = route_payloads[0]
        primary_path_legacy = [[point["lat"], point["lng"]] for point in primary_route["path"]]
        return {
            "status": "success",
            "data": {
                "path": primary_route["path"],
                "distance_m": primary_route["distance_m"],
                "duration_min": primary_route["duration_min"],
                "routes": route_payloads,
            },
            # Backward compatibility with old frontend schema.
            "path": primary_path_legacy,
            "distance": primary_route["distance_m"],
            "time_minutes": primary_route["duration_min"],
            "routes": route_payloads,
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