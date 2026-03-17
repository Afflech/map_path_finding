from flask import Flask, request, jsonify
from flask_cors import CORS
from solver import load_graph, find_shortest_path

app = Flask(__name__)
# Cho phép Frontend gọi API mà không bị lỗi bảo mật CORS
CORS(app)

# Nạp bản đồ 1 lần duy nhất khi khởi động Server để tối ưu tốc độ phản hồi API
# ĐẢM BẢO TÊN FILE KHỚP VỚI FILE BẠN VỪA TẢI
map_graph = load_graph("map_dong_da.graphml") 

@app.route('/api/find-path', methods=['POST'])
def api_find_path():
    if map_graph is None:
        return jsonify({"status": "error", "message": "Dữ liệu bản đồ chưa sẵn sàng!"}), 500

    # Lấy dữ liệu tọa độ từ Frontend gửi lên
    data = request.get_json()
    
    if not data or 'start' not in data or 'end' not in data:
        return jsonify({"status": "error", "message": "Thiếu tọa độ start hoặc end!"}), 400

    start_coords = data['start'] # Ví dụ: [21.010, 105.824]
    end_coords = data['end']     # Ví dụ: [21.015, 105.830]

    # Gọi hàm xử lý thuật toán
    result = find_shortest_path(map_graph, start_coords, end_coords)

    if result["status"] == "success":
        return jsonify(result), 200
    else:
        return jsonify(result), 404

if __name__ == '__main__':
    print("🚀 Server đang chạy tại: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)