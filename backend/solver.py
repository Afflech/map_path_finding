import math
import os
import random
from heapq import heappop, heappush
from itertools import count

import networkx as nx
import osmnx as ox
import time

from cost_model import MultiCriteriaCostCalculator
from aco import ACOZoneSolver

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

TURN_COST_SECONDS = {"straight": 0.0, "right": 5.0, "left": 15.0, "u_turn": 30.0}
TURN_THRESHOLD_DEG = 25.0
UTURN_THRESHOLD_DEG = 150.0

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


def _compute_bearing(graph, u, v):
    node_u = graph.nodes[u]
    node_v = graph.nodes[v]
    lat1 = math.radians(float(node_u["y"]))
    lat2 = math.radians(float(node_v["y"]))
    delta_lon = math.radians(float(node_v["x"]) - float(node_u["x"]))
    y_val = math.sin(delta_lon) * math.cos(lat2)
    x_val = math.cos(lat1) * math.sin(lat2) - (
        math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
    )
    return (math.degrees(math.atan2(y_val, x_val)) + 360.0) % 360.0


def _classify_turn(bearing_in, bearing_out):
    delta = (bearing_out - bearing_in + 540.0) % 360.0 - 180.0
    abs_delta = abs(delta)
    if abs_delta <= TURN_THRESHOLD_DEG:
        return "straight", TURN_COST_SECONDS["straight"]
    if abs_delta >= UTURN_THRESHOLD_DEG:
        return "u_turn", TURN_COST_SECONDS["u_turn"]
    if delta > 0:
        return "right", TURN_COST_SECONDS["right"]
    return "left", TURN_COST_SECONDS["left"]


DEFAULT_COST_CALC = MultiCriteriaCostCalculator()

def _pick_best_edge_attrs(graph, u, v, speed_ms, vehicle, jammed_nodes, flooded_nodes):
    edges_between = graph.get_edge_data(u, v, default={})
    if not edges_between:
        return None, float("inf"), 0.0

    best_attrs = None
    best_weight = float("inf")
    best_length = 0.0

    for attrs in edges_between.values():
        length = _flatten_length(attrs.get("length", 1.0))
        traffic_cost = attrs.get("_traffic_cost", length)

        is_flooded_attr = attrs.get("_flooded", False)
        is_jammed_node = (u in jammed_nodes or v in jammed_nodes)
        is_flooded_node = (u in flooded_nodes or v in flooded_nodes)
        
        is_flooded = is_flooded_attr or is_flooded_node
        is_blocked = False

        if is_flooded and vehicle in FLOODED_BLOCKED_VEHICLES:
            is_blocked = True

        if vehicle == "car":
            hw = attrs.get("highway", "")
            if isinstance(hw, list):
                hw = hw[0] if hw else ""
            if str(hw) not in CAR_ALLOWED_HIGHWAY:
                is_blocked = True

        total_cost, _ = DEFAULT_COST_CALC.evaluate_edge(
            length, speed_ms, traffic_cost, is_flooded, is_jammed_node, is_blocked
        )

        if total_cost < best_weight:
            best_attrs = attrs
            best_weight = total_cost
            best_length = length

    return best_attrs, best_weight, best_length


def _astar_path_with_exploration(graph, source, target, heuristic, weight, turn_cost_enabled=False):
    push = heappush
    pop = heappop
    c = count()
    queue = [(0.0, next(c), source, 0.0, None, None)]
    enqueued = {}
    explored = {}
    explored_order = []

    while queue:
        _, __, current, dist, parent, incoming_bearing = pop(queue)
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

            new_bearing = None
            if turn_cost_enabled:
                new_bearing = _compute_bearing(graph, current, neighbor)
                if incoming_bearing is not None:
                    _, turn_penalty = _classify_turn(incoming_bearing, new_bearing)
                    cost += turn_penalty

            ncost = dist + cost
            if neighbor in enqueued:
                qcost, h_val = enqueued[neighbor]
                if qcost <= ncost:
                    continue
            else:
                h_val = heuristic(neighbor, target)

            enqueued[neighbor] = (ncost, h_val)
            push(queue, (ncost + h_val, next(c), neighbor, ncost, current, new_bearing))

    raise nx.NetworkXNoPath


def _hierarchical_astar_with_exploration(graph, source, target, heuristic, weight, turn_cost_enabled=False, zone_manager=None):
    if not zone_manager:
        t_s = time.perf_counter()
        p, e = _astar_path_with_exploration(graph, source, target, heuristic, weight, turn_cost_enabled)
        t_e = time.perf_counter()
        return p, e, None, 0, (t_e - t_s) * 1000

    t0 = time.perf_counter()
    start_zone = zone_manager.node_to_zone.get(source)
    end_zone = zone_manager.node_to_zone.get(target)
    
    if not start_zone or not end_zone:
        t_s = time.perf_counter()
        p, e = _astar_path_with_exploration(graph, source, target, heuristic, weight, turn_cost_enabled)
        t_e = time.perf_counter()
        return p, e, None, 0, (t_e - t_s) * 1000

    macro_path = zone_manager.get_zone_path(start_zone, end_zone)
    if not macro_path:
        t_s = time.perf_counter()
        p, e = _astar_path_with_exploration(graph, source, target, heuristic, weight, turn_cost_enabled)
        t_e = time.perf_counter()
        return p, e, None, 0, (t_e - t_s) * 1000
    t1 = time.perf_counter()

    allowed_zones = set(macro_path)
    sub_nodes = {n for n, data in graph.nodes(data=True) if data.get('zone_id') in allowed_zones}
    
    expanded_sub_nodes = set(sub_nodes)
    for n in sub_nodes:
        for nb in graph.neighbors(n):
            expanded_sub_nodes.add(nb)

    expanded_sub_nodes.add(source)
    expanded_sub_nodes.add(target)

    sub_graph = graph.subgraph(expanded_sub_nodes)

    t2 = time.perf_counter()
    try:
        path, explored = _astar_path_with_exploration(sub_graph, source, target, heuristic, weight, turn_cost_enabled)
        t3 = time.perf_counter()
        return path, explored, macro_path, (t1 - t0) * 1000, (t3 - t2) * 1000
    except nx.NetworkXNoPath:
        path, explored = _astar_path_with_exploration(graph, source, target, heuristic, weight, turn_cost_enabled)
        t3 = time.perf_counter()
        return path, explored, macro_path, (t1 - t0) * 1000, (t3 - t2) * 1000

def _hierarchical_astar_with_macro_path(graph, source, target, macro_path, heuristic, weight, turn_cost_enabled=False):
    t0 = time.perf_counter()
    allowed_zones = set(macro_path)
    sub_nodes = {n for n, data in graph.nodes(data=True) if data.get('zone_id') in allowed_zones}
    
    expanded_sub_nodes = set(sub_nodes)
    for n in sub_nodes:
        for nb in graph.neighbors(n):
            expanded_sub_nodes.add(nb)

    expanded_sub_nodes.add(source)
    expanded_sub_nodes.add(target)

    sub_graph = graph.subgraph(expanded_sub_nodes)

    t1 = time.perf_counter()
    try:
        path, explored = _astar_path_with_exploration(sub_graph, source, target, heuristic, weight, turn_cost_enabled)
        t2 = time.perf_counter()
        return path, explored, macro_path, 0, (t2 - t1) * 1000
    except nx.NetworkXNoPath:
        path, explored = _astar_path_with_exploration(graph, source, target, heuristic, weight, turn_cost_enabled)
        t2 = time.perf_counter()
        return path, explored, macro_path, 0, (t2 - t1) * 1000


def _bidirectional_astar_with_exploration(graph, source, target, heuristic, weight_forward, weight_backward):
    push = heappush
    pop = heappop
    c = count()

    if source == target:
        return [source], [source], []

    queue_f = [(0.0, next(c), source, 0.0, None)]
    queue_b = [(0.0, next(c), target, 0.0, None)]

    enqueued_f = {source: (0.0, heuristic(source, target))}
    enqueued_b = {target: (0.0, heuristic(target, source))}

    explored_f = {}
    explored_b = {}
    explored_order_f = []
    explored_order_b = []

    g_f = {source: 0.0}
    g_b = {target: 0.0}

    best_cost = float("inf")
    meeting_node = None

    def _expand_forward():
        nonlocal best_cost, meeting_node
        if not queue_f:
            return float("inf")
        f_val, _, current, dist, parent = pop(queue_f)
        if current in explored_f:
            return f_val
        explored_f[current] = parent
        explored_order_f.append(current)
        g_f[current] = dist

        if current in explored_b:
            total = dist + g_b[current]
            if total < best_cost:
                best_cost = total
                meeting_node = current

        for neighbor, edge_data in graph[current].items():
            cost = weight_forward(current, neighbor, edge_data)
            if not math.isfinite(cost):
                continue
            ncost = dist + cost
            if neighbor in enqueued_f:
                if enqueued_f[neighbor][0] <= ncost:
                    continue
            h_val = heuristic(neighbor, target)
            enqueued_f[neighbor] = (ncost, h_val)
            g_f[neighbor] = ncost
            push(queue_f, (ncost + h_val, next(c), neighbor, ncost, current))
        return f_val

    def _expand_backward():
        nonlocal best_cost, meeting_node
        if not queue_b:
            return float("inf")
        f_val, _, current, dist, parent = pop(queue_b)
        if current in explored_b:
            return f_val
        explored_b[current] = parent
        explored_order_b.append(current)
        g_b[current] = dist

        if current in explored_f:
            total = g_f[current] + dist
            if total < best_cost:
                best_cost = total
                meeting_node = current

        for pred in graph.predecessors(current):
            edge_data = graph[pred][current]
            cost = weight_backward(pred, current, edge_data)
            if not math.isfinite(cost):
                continue
            ncost = dist + cost
            if pred in enqueued_b:
                if enqueued_b[pred][0] <= ncost:
                    continue
            h_val = heuristic(pred, source)
            enqueued_b[pred] = (ncost, h_val)
            g_b[pred] = ncost
            push(queue_b, (ncost + h_val, next(c), pred, ncost, current))
        return f_val

    while queue_f or queue_b:
        min_f = queue_f[0][0] if queue_f else float("inf")
        min_b = queue_b[0][0] if queue_b else float("inf")

        if min(min_f, min_b) >= best_cost:
            break

        if min_f <= min_b:
            _expand_forward()
        else:
            _expand_backward()

    if meeting_node is None:
        raise nx.NetworkXNoPath

    path_forward = []
    node = meeting_node
    while node is not None:
        path_forward.append(node)
        node = explored_f.get(node)
    path_forward.reverse()

    path_backward = []
    node = explored_b.get(meeting_node)
    while node is not None:
        path_backward.append(node)
        node = explored_b.get(node)

    full_path = path_forward + path_backward
    return full_path, explored_order_f, explored_order_b


def _route_to_payload(
    graph,
    route_nodes,
    explored_nodes,
    speed_ms,
    vehicle,
    jammed_nodes,
    flooded_nodes,
    node_penalties,
    explored_backward=None,
    turn_cost_enabled=False,
):
    route_coords = []
    total_distance = 0.0
    total_time_sec = 0.0
    instructions = []
    total_travel_time_s = 0.0
    total_traffic_penalty_s = 0.0
    total_flood_risk_s = 0.0
    total_turn_penalty_s = 0.0
    previous_bearing = None

    for idx in range(len(route_nodes) - 1):
        u = route_nodes[idx]
        v = route_nodes[idx + 1]
        edge_attrs, edge_weight, edge_length = _pick_best_edge_attrs(
            graph, u, v, speed_ms, vehicle, jammed_nodes, flooded_nodes
        )
        if edge_attrs is None or not math.isfinite(edge_weight):
            continue

        length = _flatten_length(edge_attrs.get("length", 1.0))
        traffic_cost = edge_attrs.get("_traffic_cost", length)
        is_flooded = edge_attrs.get("_flooded", False) or (u in flooded_nodes or v in flooded_nodes)
        is_jammed = (u in jammed_nodes or v in jammed_nodes)
        
        _, breakdown = DEFAULT_COST_CALC.evaluate_edge(
            length, speed_ms, traffic_cost, is_flooded, is_jammed, False
        )

        node_factor = max(node_penalties.get(u, 1.0), node_penalties.get(v, 1.0))
        edge_weight *= node_factor

        total_distance += edge_length
        total_time_sec += edge_weight
        
        total_travel_time_s += breakdown.get("travel_time_s", 0.0) * node_factor
        total_traffic_penalty_s += breakdown.get("traffic_penalty_s", 0.0) * node_factor
        total_flood_risk_s += breakdown.get("flood_risk_s", 0.0) * node_factor

        current_bearing = edge_attrs.get("bearing")
        if current_bearing is None:
            current_bearing = _compute_bearing(graph, u, v)
        else:
            current_bearing = float(current_bearing)

        turn_action = "straight"
        turn_penalty_s = 0.0
        if previous_bearing is not None:
            turn_action, turn_penalty_s = _classify_turn(previous_bearing, current_bearing)
            if turn_action == "u_turn":
                turn_action = "straight"
            if turn_cost_enabled:
                total_time_sec += turn_penalty_s
                total_turn_penalty_s += turn_penalty_s

        street_name = edge_attrs.get("name", "Đường không tên")
        if isinstance(street_name, list):
            street_name = street_name[0] if street_name else "Đường không tên"
        if not street_name:
            street_name = "Đường không tên"

        step = {
            "action": turn_action,
            "street": str(street_name),
            "distance_m": round(edge_length, 1),
        }
        if turn_cost_enabled and turn_penalty_s > 0:
            step["turn_penalty_s"] = round(turn_penalty_s, 1)
        instructions.append(step)
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
    result = {
        "path": path_points,
        "explored_nodes": explored_coords,
        "distance_m": total_distance,
        "duration_min": total_time_sec / 60.0,
        "node_count": len(route_nodes),
        "instructions": _merge_instructions(instructions),
        "cost_breakdown": {
            "travel_time_s": round(total_travel_time_s, 2),
            "traffic_penalty_s": round(total_traffic_penalty_s, 2),
            "flood_risk_s": round(total_flood_risk_s, 2),
            "turn_penalty_s": round(total_turn_penalty_s, 2),
            "total_cost": round(total_time_sec, 2)
        }
    }
    if explored_backward is not None:
        result["explored_nodes_backward"] = [
            [float(graph.nodes[node]["y"]), float(graph.nodes[node]["x"])]
            for node in explored_backward
            if node in graph.nodes
        ]
    return result


def _merge_instructions(instructions):
    if not instructions:
        return []

    merged = []
    for step in instructions:
        action = step.get("action", "straight")
        street = step.get("street", "Đường không tên")
        distance_m = float(step.get("distance_m", 0.0))
        turn_penalty_s = step.get("turn_penalty_s")

        if merged:
            previous = merged[-1]
            if previous["action"] == action and previous["street"] == street:
                previous["distance_m"] = round(previous["distance_m"] + distance_m, 1)
                continue

        entry = {
            "action": action,
            "street": street,
            "distance_m": round(distance_m, 1),
        }
        if turn_penalty_s is not None:
            entry["turn_penalty_s"] = turn_penalty_s
        merged.append(entry)

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


class DStarLite:
    def __init__(self, graph, start, goal, heuristic, weight_func):
        self.graph = graph
        self.start = start
        self.goal = goal
        self.heuristic = heuristic
        self.weight_func = weight_func
        self.km = 0.0
        self.g = {}
        self.rhs = {}
        self._queue = []
        self._counter = count()
        self.explored_order = []

        self.rhs[goal] = 0.0
        heappush(self._queue, (self._calc_key(goal), next(self._counter), goal))

    def _g(self, s):
        return self.g.get(s, float("inf"))

    def _rhs(self, s):
        return self.rhs.get(s, float("inf"))

    def _calc_key(self, s):
        min_val = min(self._g(s), self._rhs(s))
        return (min_val + self.heuristic(self.start, s) + self.km, min_val)

    def _update_vertex(self, u):
        if u != self.goal:
            min_rhs = float("inf")
            for v in self.graph[u]:
                c = self.weight_func(u, v)
                if math.isfinite(c):
                    min_rhs = min(min_rhs, c + self._g(v))
            self.rhs[u] = min_rhs
        if self._g(u) != self._rhs(u):
            heappush(self._queue, (self._calc_key(u), next(self._counter), u))

    def compute_shortest_path(self):
        self.explored_order = []
        expanded = set()
        while self._queue:
            k_old, _, u = heappop(self._queue)

            if u in expanded:
                continue

            k_new = self._calc_key(u)
            start_key = self._calc_key(self.start)

            if k_old >= start_key and self._rhs(self.start) == self._g(self.start):
                break

            self.explored_order.append(u)
            expanded.add(u)

            if k_old < k_new:
                heappush(self._queue, (k_new, next(self._counter), u))
                expanded.discard(u)
            elif self._g(u) > self._rhs(u):
                self.g[u] = self.rhs[u]
                for pred in self.graph.predecessors(u):
                    self._update_vertex(pred)
            else:
                self.g[u] = float("inf")
                self._update_vertex(u)
                for pred in self.graph.predecessors(u):
                    self._update_vertex(pred)

        return self.explored_order

    def extract_path(self):
        path = [self.start]
        current = self.start
        visited = {current}
        max_steps = len(self.graph.nodes) + 1
        for _ in range(max_steps):
            if current == self.goal:
                return path
            best_next = None
            best_cost = float("inf")
            for v in self.graph[current]:
                c = self.weight_func(current, v)
                if math.isfinite(c) and v not in visited:
                    total = c + self._g(v)
                    if total < best_cost:
                        best_cost = total
                        best_next = v
            if best_next is None:
                raise nx.NetworkXNoPath
            path.append(best_next)
            visited.add(best_next)
            current = best_next
        raise nx.NetworkXNoPath


def _dstar_lite_find_path(graph, source, target, speed_ms, vehicle,
                          jammed_nodes, flooded_nodes, node_penalties):
    def weight_func(u, v):
        _, best_weight, _ = _pick_best_edge_attrs(
            graph, u, v, speed_ms, vehicle, jammed_nodes, flooded_nodes
        )
        if not math.isfinite(best_weight):
            return best_weight
        node_factor = max(node_penalties.get(u, 1.0), node_penalties.get(v, 1.0))
        return best_weight * node_factor

    dstar = DStarLite(
        graph, source, target,
        heuristic=lambda a, b: _heuristic_time(a, b, graph, speed_ms),
        weight_func=weight_func,
    )
    explored = dstar.compute_shortest_path()
    path = dstar.extract_path()
    return path, explored


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
    algorithm="astar",
    turn_cost=False,
    zone_manager=None,
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

        if algorithm == "dstar_lite":
            top_k = 1

        aco_macro_paths = []
        aco_time_ms = 0
        if algorithm == "aco" and zone_manager:
            start_zone = zone_manager.node_to_zone.get(algo_start)
            end_zone = zone_manager.node_to_zone.get(algo_end)
            if start_zone and end_zone:
                t0_aco = time.perf_counter()
                aco_solver = ACOZoneSolver(zone_manager, start_zone, end_zone, num_ants=10, iterations=5)
                aco_macro_paths = aco_solver.run(top_k=max_attempts)
                t1_aco = time.perf_counter()
                aco_time_ms = (t1_aco - t0_aco) * 1000
            else:
                algorithm = "hierarchical" # fallback if zones missing

        for attempt_idx in range(max_attempts):
            explored_backward = None
            macro_path = None
            try:
                if algorithm == "aco":
                    if not aco_macro_paths:
                        break
                    macro_path = aco_macro_paths.pop(0)
                    t_m_s = time.perf_counter()
                    route_nodes, explored_nodes, macro_path, zone_t, local_t = _hierarchical_astar_with_macro_path(
                        graph,
                        algo_start,
                        algo_end,
                        macro_path,
                        heuristic=lambda u, v: _heuristic_time(u, v, graph, speed_ms),
                        weight=weight_func,
                        turn_cost_enabled=turn_cost,
                    )
                    zone_time_ms = zone_t + aco_time_ms # we'll track aco_time outside
                    local_time_ms = local_t
                elif algorithm == "dstar_lite":
                    route_nodes, explored_nodes = _dstar_lite_find_path(
                        graph, algo_start, algo_end, speed_ms, vehicle,
                        jammed_nodes, flooded_nodes, node_penalties,
                    )
                elif algorithm == "bidirectional":
                    route_nodes, explored_nodes, explored_backward = (
                        _bidirectional_astar_with_exploration(
                            graph,
                            algo_start,
                            algo_end,
                            heuristic=lambda u, v: _heuristic_time(u, v, graph, speed_ms),
                            weight_forward=weight_func,
                            weight_backward=weight_func,
                        )
                    )
                elif algorithm == "hierarchical":
                    route_nodes, explored_nodes, macro_path, zone_time_ms, local_time_ms = _hierarchical_astar_with_exploration(
                        graph,
                        algo_start,
                        algo_end,
                        heuristic=lambda u, v: _heuristic_time(u, v, graph, speed_ms),
                        weight=weight_func,
                        turn_cost_enabled=turn_cost,
                        zone_manager=zone_manager,
                    )
                else:
                    route_nodes, explored_nodes = _astar_path_with_exploration(
                        graph,
                        algo_start,
                        algo_end,
                        heuristic=lambda u, v: _heuristic_time(u, v, graph, speed_ms),
                        weight=weight_func,
                        turn_cost_enabled=(turn_cost and algorithm == "astar"),
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
                    jammed_nodes, flooded_nodes, node_penalties,
                    explored_backward=explored_backward,
                    turn_cost_enabled=turn_cost,
                )
                route_payload["segments"] = segments
                route_payload["multimodal"] = True
                if macro_path:
                    route_payload["zones_traversed"] = macro_path
                    if zone_manager:
                        route_payload["zones_bounds"] = [zone_manager.get_zone_bounds(z) for z in macro_path]
                    route_payload["zone_time_ms"] = round(zone_time_ms, 2)
                    route_payload["local_time_ms"] = round(local_time_ms, 2)
            else:
                payload = _route_to_payload(
                    graph,
                    route_nodes,
                    explored_nodes,
                    speed_ms,
                    vehicle,
                    jammed_nodes,
                    flooded_nodes,
                    node_penalties,
                    explored_backward=explored_backward,
                    turn_cost_enabled=turn_cost,
                )
            
                if macro_path:
                    payload["zones_traversed"] = macro_path
                    if zone_manager:
                        payload["zones_bounds"] = [zone_manager.get_zone_bounds(z) for z in macro_path]
                    payload["zone_time_ms"] = round(zone_time_ms, 2)
                    payload["local_time_ms"] = round(local_time_ms, 2)
                    
                route_payload = payload

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