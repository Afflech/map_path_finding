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

    data = request.get_json()
    if not data or 'start' not in data or 'end' not in data:
        return jsonify({"status": "error", "message": "Thiếu tọa độ!"}), 400

    # Lấy cả xe cộ và danh sách ngập/tắc
    start_coords = data['start']
    end_coords = data['end']
    vehicle = data.get('vehicle', 'bike')
    jammed = data.get('jammed', [])
    flooded = data.get('flooded', [])

    result = find_shortest_path(map_graph, start_coords, end_coords, vehicle, jammed, flooded)

    if result["status"] == "success":
        return jsonify(result), 200
    else:
        return jsonify(result), 404

if __name__ == '__main__':
    print("Server chạy tại: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)