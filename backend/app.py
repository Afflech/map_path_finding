from flask import Flask, request, jsonify
from flask_cors import CORS
from solver import load_graph, find_shortest_path

app = Flask(__name__)
CORS(app)

map_graph = load_graph("map_dong_da.graphml") 

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
    if algorithm not in ('astar', 'bidirectional', 'dstar_lite'):
        return jsonify({"status": "error", "message": "algorithm phải là astar, bidirectional hoặc dstar_lite."}), 400

    turn_cost = data.get('turn_cost', False)
    if not isinstance(turn_cost, bool):
        turn_cost = str(turn_cost).lower() in ('true', '1', 'yes')

    result = find_shortest_path(
        map_graph, start_coords, end_coords, vehicle, jammed, flooded, top_k,
        traffic_level=traffic_level, rain_mm=rain_mm,
        algorithm=algorithm, turn_cost=turn_cost,
    )

    if result.get("status") == "success":
        return jsonify(result), 200
    return jsonify(result), 404

if __name__ == '__main__':
    print("Server chạy tại: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)