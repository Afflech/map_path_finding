import osmnx as ox
import networkx as nx
import math
import os

ox.settings.log_console = False

def load_graph(filename="map_dong_da.graphml"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, 'data', filename)
    print(f"Đang nạp: {file_path}...")
    try:
        G = ox.load_graphml(file_path)
        print("✅ Nạp map thành công!")
        return G
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return None

def heuristic_haversine(node1, node2, G):
    y1, x1 = G.nodes[node1]['y'], G.nodes[node1]['x']
    y2, x2 = G.nodes[node2]['y'], G.nodes[node2]['x']
    R = 6371000 
    phi1, phi2 = math.radians(y1), math.radians(y2)
    delta_phi = math.radians(y2 - y1)
    delta_lambda = math.radians(x2 - x1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Heuristic tính bằng THỜI GIAN (giây) thay vì KHOẢNG CÁCH để hợp rơ với Weight func
def heuristic_time(node1, node2, G, speed_ms):
    dist = heuristic_haversine(node1, node2, G)
    return dist / speed_ms

def find_shortest_path(G, start_coords, end_coords, vehicle='bike', jammed_points=[], flooded_points=[]):
    start_lat, start_lon = start_coords
    end_lat, end_lon = end_coords

    try:
        start_node = ox.distance.nearest_nodes(G, start_lon, start_lat)
        end_node = ox.distance.nearest_nodes(G, end_lon, end_lat)

        # Chuyển đổi điểm ngập/tắc người dùng click thành các Nút (Nodes) trên đồ thị
        jammed_nodes = set([ox.distance.nearest_nodes(G, p[1], p[0]) for p in jammed_points])
        flooded_nodes = set([ox.distance.nearest_nodes(G, p[1], p[0]) for p in flooded_points])

        # Vận tốc m/s
        speed_kmh = {'walk': 5, 'bike': 30, 'car': 50}.get(vehicle, 30)
        speed_ms = speed_kmh / 3.6

        # HÀM TRỌNG SỐ TÍNH BẰNG THỜI GIAN
        def weight_func(u, v, edge_data):
            length = edge_data.get('length', 1.0)
            if isinstance(length, list): length = sum(length)
            else: length = float(length)
            
            base_time_sec = length / speed_ms
            
            # Phạt thời gian nếu đi qua vùng tắc
            if u in jammed_nodes or v in jammed_nodes:
                base_time_sec *= 5  # Đi chậm gấp 5 lần
                
            # Xử lý vùng ngập
            if u in flooded_nodes or v in flooded_nodes:
                if vehicle in ['walk', 'car']:
                    return float('inf') # Đi bộ/Ô tô gặp ngập là "cooked", cấm đi
                else:
                    base_time_sec *= 10 # Xe máy phi qua được nhưng rủi ro, x10 thời gian
                    
            return base_time_sec

        # Chạy A* với weight là hàm tính thời gian
        route = nx.astar_path(
            G, source=start_node, target=end_node, 
            heuristic=lambda u, v: heuristic_time(u, v, G, speed_ms), 
            weight=weight_func
        )

        route_coords = []
        total_distance = 0 
        total_time_sec = 0
        
        for i in range(len(route)):
            node = route[i]
            route_coords.append([G.nodes[node]['y'], G.nodes[node]['x']])
            
            if i < len(route) - 1:
                u, v = route[i], route[i+1]
                edge_data = G.get_edge_data(u, v)
                if edge_data and 0 in edge_data:
                    e_data = edge_data[0]
                    # Tính khoảng cách
                    l = e_data.get('length', 0)
                    total_distance += sum(l) if isinstance(l, list) else float(l)
                    # Tính tổng thời gian thực tế
                    total_time_sec += weight_func(u, v, e_data)

        return {
            "status": "success", 
            "path": route_coords, 
            "distance": total_distance,
            "time_minutes": total_time_sec / 60
        }

    except nx.NetworkXNoPath:
        return {"status": "error", "message": "Đường ngập hoặc tắc hết cụ nó rồi, không có lối thoát! 😭"}
    except Exception as e:
        return {"status": "error", "message": str(e)}