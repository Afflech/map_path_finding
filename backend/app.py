import time
import tracemalloc

from flask import Flask, request, jsonify
from flask_cors import CORS
from solver import load_graph, find_shortest_path
from zone_manager import ZoneManager

app = Flask(__name__)
CORS(app)

map_graph = load_graph("map_dong_da.graphml") 
zone_manager = None
if map_graph is not None:
    zone_manager = ZoneManager(map_graph, cell_size_m=500)

@app.route('/api/find-path', methods=['POST'])
def api_find_path():
    if map_graph is None:
        return jsonify({"status": "error", "message": "Bản đồ chưa sẵn sàng!"}), 500

    data = request.get_json(silent=True) or {}
    if 'start' not in data or 'end' not in data:
        return jsonify({"status": "error", "message": "Thiếu tọa độ!"}), 400

    start_coords = data['start']
    end_coords = data['end']

    vehicle = data.get('vehicle', 'bike')
    if vehicle not in ('walk', 'bike', 'car'):
        return jsonify({"status": "error", "message": "vehicle phải là walk, bike hoặc car."}), 400

    try:
        top_k = int(data.get('top_k', 3))
        if not (1 <= top_k <= 10):
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "top_k phải là số nguyên từ 1 đến 10."}), 400

    obstacles = data.get('obstacles', {})
    jammed = data.get('jammed', obstacles.get('jammed', []))
    flooded = data.get('flooded', obstacles.get('flooded', []))

    traffic_level = data.get('traffic_level', 'Normal')
    if traffic_level not in ('Low', 'Normal', 'High'):
        return jsonify({"status": "error", "message": "traffic_level phải là Low, Normal hoặc High."}), 400

    try:
        rain_mm = float(data.get('rain_mm', 0.0))
        if rain_mm < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "rain_mm phải là số không âm."}), 400

    algorithm = data.get('algorithm', 'astar')
    if algorithm not in ('astar', 'bidirectional', 'dstar_lite', 'hierarchical', 'aco'):
        return jsonify({"status": "error", "message": "algorithm phải là astar, bidirectional, dstar_lite, hierarchical hoặc aco."}), 400

    turn_cost = data.get('turn_cost', False)
    if not isinstance(turn_cost, bool):
        turn_cost = str(turn_cost).lower() in ('true', '1', 'yes')

    tracemalloc.start()
    t_start = time.perf_counter()
    result = find_shortest_path(
        map_graph, start_coords, end_coords, vehicle, jammed, flooded, top_k,
        traffic_level=traffic_level, rain_mm=rain_mm,
        algorithm=algorithm, turn_cost=turn_cost,
        zone_manager=zone_manager,
    )
    t_end = time.perf_counter()
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    if result.get("status") == "success":
        result["computation_time_ms"] = round((t_end - t_start) * 1000, 1)

        comparison = {}
        
        # Current algorithm stats
        nodes_cnt = len(result.get("data", {}).get("explored_nodes", []))
        if result.get("data", {}).get("explored_nodes_backward"):
            nodes_cnt += len(result.get("data", {}).get("explored_nodes_backward"))
        comparison[algorithm] = {
            "time_ms": result["computation_time_ms"],
            "nodes": nodes_cnt,
            "distance": round(result.get("data", {}).get("distance_m", 0), 1),
            "memory_kb": round(peak_memory / 1024, 1)
        }

        # Run other algorithms
        for algo in ["astar", "bidirectional", "dstar_lite", "hierarchical", "aco"]:
            if algo == algorithm:
                continue
            
            tracemalloc.start()
            t_s = time.perf_counter()
            try:
                res = find_shortest_path(
                    map_graph, start_coords, end_coords, vehicle, jammed, flooded, top_k=1,
                    traffic_level=traffic_level, rain_mm=rain_mm,
                    algorithm=algo, turn_cost=turn_cost,
                    zone_manager=zone_manager,
                )
                t_e = time.perf_counter()
                _, peak_mem_algo = tracemalloc.get_traced_memory()
                tracemalloc.stop()

                if res.get("status") == "success":
                    n_cnt = len(res.get("data", {}).get("explored_nodes", []))
                    if res.get("data", {}).get("explored_nodes_backward"):
                        n_cnt += len(res.get("data", {}).get("explored_nodes_backward"))
                    comparison[algo] = {
                        "time_ms": round((t_e - t_s) * 1000, 1),
                        "nodes": n_cnt,
                        "distance": round(res.get("data", {}).get("distance_m", 0), 1),
                        "memory_kb": round(peak_mem_algo / 1024, 1)
                    }
                else:
                    comparison[algo] = {"time_ms": "-", "nodes": "-", "distance": "-", "memory_kb": "-"}
            except Exception:
                if tracemalloc.is_tracing():
                    tracemalloc.stop()
                comparison[algo] = {"time_ms": "-", "nodes": "-", "distance": "-", "memory_kb": "-"}
                
        result["comparison"] = comparison

        return jsonify(result), 200
    return jsonify(result), 404

if __name__ == '__main__':
    print("Server chạy tại: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)