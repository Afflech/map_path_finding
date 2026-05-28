import math
import os
import random
from heapq import heappop, heappush
from itertools import count

import networkx as nx
import osmnx as ox

ox.settings.log_console = False

VEHICLE_SPEED_KMH = {"walk": 5, "bike": 25, "car": 35}
JAMMED_PENALTY_FACTOR = 8.0
FLOODED_BIKE_PENALTY_FACTOR = 20.0
FLOODED_BLOCKED_VEHICLES = {"walk", "car"}
DEFAULT_TOP_K_ROUTES = 3
MAX_DIVERSE_ATTEMPTS_MULTIPLIER = 6
RANDOM_NODE_PENALTY_MIN = 1.10
RANDOM_NODE_PENALTY_MAX = 1.45
MIN_ROUTE_DIVERGENCE_RATIO = 0.08

# Các loại đường ô tô được phép đi
CAR_ALLOWED_HIGHWAY = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "unclassified", "residential", "motorway_link", "trunk_link",
    "primary_link", "secondary_link", "tertiary_link",
}

# Các loại đường chỉ dành cho ngõ/hẻm (không phải đường ô tô)
ALLEY_HIGHWAY = {"living_street", "service", "pedestrian", "footway", "path", "track", "steps"}

TRAFFIC_PENALTY = {"Low": 1.2, "Normal": 1.5, "High": 2.0}


def apply_mock_conditions(graph, traffic_level="Normal", rain_mm=0.0):
    """
    Cập nhật trọng số đồ thị dựa trên mức tắc đường và lượng mưa.
    - traffic_level: 'Low' | 'Normal' | 'High' → tăng cost theo hệ số a
    - rain_mm: nếu rain_mm > C = lanes * 3 * 15 → set cost = inf (ngập)
    Trả về (jammed_edges, flooded_edges) để dùng trong routing.
    """
    a = TRAFFIC_PENALTY.get(traffic_level, TRAFFIC_PENALTY["Normal"])
    jammed_edges = set()
    flooded_edges = set()

    rng = random.Random(42)  # seed cố định để kết quả nhất quán

    for u, v, key, data in graph.edges(keys=True, data=True):
        length = _flatten_length(data.get("length", 1.0))

        # Tắc đường: áp dụng ngẫu nhiên ~30% cạnh (hoặc tất cả nếu High)
        if traffic_level == "High" or (traffic_level != "Low" and rng.random() < 0.3):
            graph[u][v][key]["_traffic_cost"] = length * a
            jammed_edges.add((u, v))
        else:
            graph[u][v][key]["_traffic_cost"] = length

        # Ngập lụt: dựa vào lanes
        lanes = data.get("lanes", 1)
        if isinstance(lanes, list):
            lanes = max(int(x) for x in lanes if str(x).isdigit()) if lanes else 1
        try:
            lanes = int(lanes)
        except (ValueError, TypeError):
            lanes = 1
        lanes = max(1, lanes)
        capacity = lanes * 3 * 15  # C = lanes * 3m * 15mm/h
        if rain_mm > capacity:
            graph[u][v][key]["_flooded"] = True
            flooded_edges.add((u, v))
        else:
            graph[u][v][key]["_flooded"] = False

    return jammed_edges, flooded_edges


def _is_car_accessible(graph, u, v):
    """Kiểm tra cạnh (u,v) có phải đường ô tô không."""
    edges = graph.get_edge_data(u, v, default={})
    for data in edges.values():
        hw = data.get("highway", "")
        if isinstance(hw, list):
            hw = hw[0] if hw else ""
        if str(hw) in CAR_ALLOWED_HIGHWAY:
            return True
    return False


def _node_is_in_alley(graph, node):
    """Kiểm tra node có nằm trong ngõ/hẻm không (tất cả cạnh kề đều là alley)."""
    neighbors = list(graph.neighbors(node))
    if not neighbors:
        return False
    for nb in neighbors:
        edges = graph.get_edge_data(node, nb, default={})
        for data in edges.values():
            hw = data.get("highway", "")
            if isinstance(hw, list):
                hw = hw[0] if hw else ""
            if str(hw) in CAR_ALLOWED_HIGHWAY:
                return False
    return True


def _find_nearest_car_node(graph, alley_node):
    """BFS từ alley_node để tìm node gần nhất có đường ô tô."""
    from collections import deque
    visited = {alley_node}
    queue = deque([alley_node])
    while queue:
        current = queue.popleft()
        for nb in graph.neighbors(current):
            if nb in visited:
                continue
            visited.add(nb)
            if not _node_is_in_alley(graph, nb):
                return nb
            queue.append(nb)
    return alley_node  # fallback


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

        # Dùng traffic_cost nếu đã apply_mock_conditions, ngược lại dùng length
        traffic_cost = attrs.get("_traffic_cost", length)
        travel_time = traffic_cost / speed_ms

        # Ngập lụt từ apply_mock_conditions
        if attrs.get("_flooded", False):
            if vehicle in FLOODED_BLOCKED_VEHICLES:
                travel_time = float("inf")
            else:
                travel_time *= FLOODED_BIKE_PENALTY_FACTOR

        # Fallback: jammed/flooded nodes từ tham số cũ
        if u in jammed_nodes or v in jammed_nodes:
            travel_time *= JAMMED_PENALTY_FACTOR
        if u in flooded_nodes or v in flooded_nodes:
            if vehicle in FLOODED_BLOCKED_VEHICLES:
                travel_time = float("inf")
            else:
                travel_time *= FLOODED_BIKE_PENALTY_FACTOR

        # Car chỉ đi đường ô tô
        if vehicle == "car":
            hw = attrs.get("highway", "")
            if isinstance(hw, list):
                hw = hw[0] if hw else ""
            if str(hw) not in CAR_ALLOWED_HIGHWAY:
                travel_time = float("inf")

        if travel_time < best_weight:
            best_attrs = attrs
            best_weight = travel_time
            best_length = length

    return best_attrs, best_weight, best_length


def _astar_path_with_exploration(graph, source, target, heuristic, weight):
    push = heappush
    pop = heappop
    c = count()
    queue = [(0.0, next(c), source, 0.0, None)]
    enqueued = {}
    explored = {}
    explored_order = []

    while queue:
        _, __, current, dist, parent = pop(queue)
        if current in explored:
            continue
        explored[current] = parent
        explored_order.append(current)

        if current == target:
            path = [current]
            node = parent
            while node is not None:
                path.append(node)
                node = explored[node]
            path.reverse()
            return path, explored_order

        for neighbor, edge_data in graph[current].items():
            cost = weight(current, neighbor, edge_data)
            if not math.isfinite(cost):
                continue
            ncost = dist + cost
            if neighbor in enqueued:
                qcost, h_val = enqueued[neighbor]
                if qcost <= ncost:
                    continue
            else:
                h_val = heuristic(neighbor, target)

            enqueued[neighbor] = (ncost, h_val)
            push(queue, (ncost + h_val, next(c), neighbor, ncost, current))

    raise nx.NetworkXNoPath


def _route_to_payload(
    graph,
    route_nodes,
    explored_nodes,
    speed_ms,
    vehicle,
    jammed_nodes,
    flooded_nodes,
    node_penalties,
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
    explored_coords = [
        [float(graph.nodes[node]["y"]), float(graph.nodes[node]["x"])]
        for node in explored_nodes
        if node in graph.nodes
    ]
    return {
        "path": path_points,
        "explored_nodes": explored_coords,
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
    traffic_level="Normal",
    rain_mm=0.0,
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

        # Áp dụng điều kiện động (traffic + flood) lên đồ thị
        _, flooded_edge_set = apply_mock_conditions(graph, traffic_level, float(rain_mm))

        speed_kmh = VEHICLE_SPEED_KMH.get(vehicle, VEHICLE_SPEED_KMH["bike"])
        speed_ms = speed_kmh / 3.6
        top_k = max(1, int(top_k))
        random_seed = hash((start_node, end_node, vehicle, len(jammed_nodes), len(flooded_nodes)))
        rng = random.Random(random_seed)
        node_penalties = {}

        # Multi-modal: Car + điểm trong ngõ → tách 3 chặng
        multimodal_segments = None
        if vehicle == "car":
            start_in_alley = _node_is_in_alley(graph, start_node)
            end_in_alley = _node_is_in_alley(graph, end_node)
            if start_in_alley or end_in_alley:
                car_start = _find_nearest_car_node(graph, start_node) if start_in_alley else start_node
                car_end = _find_nearest_car_node(graph, end_node) if end_in_alley else end_node
                multimodal_segments = {
                    "walk_start": (start_node, car_start) if start_in_alley else None,
                    "car": (car_start, car_end),
                    "walk_end": (car_end, end_node) if end_in_alley else None,
                }

        def weight_func(u, v, edge_data):
            _, best_weight, _ = _pick_best_edge_attrs(
                graph, u, v, speed_ms, vehicle, jammed_nodes, flooded_nodes
            )
            if not math.isfinite(best_weight):
                return best_weight
            node_factor = max(node_penalties.get(u, 1.0), node_penalties.get(v, 1.0))
            return best_weight * node_factor

        def weight_func_walk(u, v, edge_data):
            _, best_weight, _ = _pick_best_edge_attrs(
                graph, u, v, VEHICLE_SPEED_KMH["walk"] / 3.6, "walk", jammed_nodes, flooded_nodes
            )
            return best_weight if math.isfinite(best_weight) else float("inf")

        route_nodes_list = []
        route_payloads = []
        seen_signatures = set()
        max_attempts = max(top_k * MAX_DIVERSE_ATTEMPTS_MULTIPLIER, top_k)

        # Xác định node bắt đầu/kết thúc cho thuật toán chính
        algo_start = multimodal_segments["car"][0] if multimodal_segments else start_node
        algo_end = multimodal_segments["car"][1] if multimodal_segments else end_node

        for _ in range(max_attempts):
            try:
                route_nodes, explored_nodes = _astar_path_with_exploration(
                    graph,
                    algo_start,
                    algo_end,
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

            # Ghép chặng đi bộ nếu multi-modal
            if multimodal_segments:
                full_nodes, full_explored, segments = _build_multimodal_route(
                    graph, multimodal_segments, route_nodes, explored_nodes,
                    speed_ms, jammed_nodes, flooded_nodes, node_penalties
                )
                route_payload = _route_to_payload(
                    graph, full_nodes, full_explored, speed_ms, vehicle,
                    jammed_nodes, flooded_nodes, node_penalties
                )
                route_payload["segments"] = segments
                route_payload["multimodal"] = True
            else:
                route_payload = _route_to_payload(
                    graph, route_nodes, explored_nodes, speed_ms, vehicle,
                    jammed_nodes, flooded_nodes, node_penalties
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

        # Tọa độ các cạnh bị ngập để frontend vẽ màu xanh
        flooded_edges_coords = []
        for u, v in flooded_edge_set:
            if u in graph.nodes and v in graph.nodes:
                u_data = graph.nodes[u]
                v_data = graph.nodes[v]
                flooded_edges_coords.append([
                    [float(u_data["y"]), float(u_data["x"])],
                    [float(v_data["y"]), float(v_data["x"])],
                ])

        return {
            "status": "success",
            "flooded_edges": flooded_edges_coords,
            "data": {
                "path": primary_route["path"],
                "explored_nodes": primary_route["explored_nodes"],
                "distance_m": primary_route["distance_m"],
                "duration_min": primary_route["duration_min"],
                "routes": route_payloads,
                "flooded_edges": flooded_edges_coords,
            },
            # Backward compatibility with old frontend schema.
            "path": primary_path_legacy,
            "explored_nodes": primary_route["explored_nodes"],
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


def _build_multimodal_route(graph, segments, car_nodes, car_explored, car_speed_ms,
                             jammed_nodes, flooded_nodes, node_penalties):
    """Ghép 3 chặng: đi bộ → ô tô → đi bộ cho multi-modal routing."""
    walk_speed_ms = VEHICLE_SPEED_KMH["walk"] / 3.6
    full_nodes = []
    full_explored = list(car_explored)
    segment_payloads = []

    # Chặng 1: đi bộ từ start → car_start
    if segments["walk_start"]:
        w_start, w_end = segments["walk_start"]
        try:
            walk_nodes, walk_explored = _astar_path_with_exploration(
                graph, w_start, w_end,
                heuristic=lambda u, v: _heuristic_time(u, v, graph, walk_speed_ms),
                weight=lambda u, v, d: _pick_best_edge_attrs(
                    graph, u, v, walk_speed_ms, "walk", jammed_nodes, flooded_nodes
                )[1],
            )
            full_nodes.extend(walk_nodes[:-1])
            full_explored.extend(walk_explored)
            seg = _route_to_payload(graph, walk_nodes, walk_explored, walk_speed_ms,
                                    "walk", jammed_nodes, flooded_nodes, {})
            seg["mode"] = "walk"
            seg["label"] = "Đi bộ ra đường lớn"
            segment_payloads.append(seg)
        except nx.NetworkXNoPath:
            full_nodes.append(w_start)

    # Chặng 2: ô tô
    full_nodes.extend(car_nodes[:-1] if segments["walk_end"] else car_nodes)
    car_seg = _route_to_payload(graph, car_nodes, car_explored, car_speed_ms,
                                "car", jammed_nodes, flooded_nodes, node_penalties)
    car_seg["mode"] = "car"
    car_seg["label"] = "Đi ô tô"
    segment_payloads.append(car_seg)

    # Chặng 3: đi bộ từ car_end → end
    if segments["walk_end"]:
        w_start, w_end = segments["walk_end"]
        try:
            walk_nodes, walk_explored = _astar_path_with_exploration(
                graph, w_start, w_end,
                heuristic=lambda u, v: _heuristic_time(u, v, graph, walk_speed_ms),
                weight=lambda u, v, d: _pick_best_edge_attrs(
                    graph, u, v, walk_speed_ms, "walk", jammed_nodes, flooded_nodes
                )[1],
            )
            full_nodes.extend(walk_nodes)
            full_explored.extend(walk_explored)
            seg = _route_to_payload(graph, walk_nodes, walk_explored, walk_speed_ms,
                                    "walk", jammed_nodes, flooded_nodes, {})
            seg["mode"] = "walk"
            seg["label"] = "Đi bộ vào điểm đích"
            segment_payloads.append(seg)
        except nx.NetworkXNoPath:
            full_nodes.append(w_end)
    elif car_nodes:
        full_nodes.append(car_nodes[-1])

    return full_nodes, full_explored, segment_payloads