import osmnx as ox
import networkx as nx
import math
import os

# Tắt bớt log không cần thiết của thư viện
ox.settings.log_console = False

def load_graph(filename="map_dong_da.graphml"):
    """Tải đồ thị từ thư mục data vào bộ nhớ (RAM)"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, 'data', filename)
    
    print(f"Đang nạp dữ liệu bản đồ từ: {file_path}...")
    try:
        G = ox.load_graphml(file_path)
        print("✅ Đã nạp bản đồ thành công!")
        return G
    except Exception as e:
        print(f"❌ Lỗi nạp bản đồ: {e}")
        return None

def heuristic_haversine(node1, node2, G):
    """
    Hàm Heuristic ước lượng khoảng cách (đường chim bay) giữa 2 node bằng công thức Haversine.
    Đây là điểm cộng lớn cho thuật toán A* trên bản đồ địa lý thực tế.
    """
    y1, x1 = G.nodes[node1]['y'], G.nodes[node1]['x']
    y2, x2 = G.nodes[node2]['y'], G.nodes[node2]['x']
    
    # Bán kính trái đất (mét)
    R = 6371000 
    phi1, phi2 = math.radians(y1), math.radians(y2)
    delta_phi = math.radians(y2 - y1)
    delta_lambda = math.radians(x2 - x1)

    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def find_shortest_path(G, start_coords, end_coords):
    """
    Chạy thuật toán A* để tìm đường đi ngắn nhất.
    Input: Đồ thị G, tọa độ bắt đầu [lat, lon], tọa độ kết thúc [lat, lon]
    """
    start_lat, start_lon = start_coords
    end_lat, end_lon = end_coords

    try:
        # 1. Tìm 2 Node trong đồ thị gần với tọa độ người dùng chọn nhất
        start_node = ox.distance.nearest_nodes(G, start_lon, start_lat)
        end_node = ox.distance.nearest_nodes(G, end_lon, end_lat)

        # 2. Thuật toán A* (Dùng trọng số 'length' là chiều dài đoạn đường)
        route = nx.astar_path(
            G, 
            source=start_node, 
            target=end_node, 
            heuristic=lambda u, v: heuristic_haversine(u, v, G), 
            weight='length'
        )

        # 3. Chuyển đổi ID các node thành tọa độ [lat, lon] để gửi cho Frontend vẽ
        route_coords = []
        total_distance = []
        for i in range(len(route)):
            node = route[i]
            lat, lon = G.nodes[node]['y'], G.nodes[node]['x']
            route_coords.append([lat, lon])

    # Tính tổng khoảng cách
            if i < len(route) - 1:
                u = route[i]
                v = route[i+1]
        # Lấy độ dài của đoạn đường nối giữa 2 node
                edge_data = G.get_edge_data(u, v)[0] 
                total_distance += edge_data.get('length', 0)

        return {"status": "success", "path": route_coords, "distance": total_distance}

    except nx.NetworkXNoPath:
        return {"status": "error", "message": "Không có đường đi nào kết nối 2 điểm này."}
    except Exception as e:
        return {"status": "error", "message": str(e)}