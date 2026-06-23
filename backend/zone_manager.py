import networkx as nx
import math

class ZoneManager:
    def __init__(self, graph, cell_size_m=500):
        self.graph = graph
        self.cell_size_m = cell_size_m
        self.node_to_zone = {}
        self.zone_graph = nx.DiGraph()
        self.zone_centers = {}
        print(f"Bắt đầu xây dựng ZoneGraph (kích thước {cell_size_m}m x {cell_size_m}m)...")
        self._build_zones()

    def _build_zones(self):
        # 1. Tìm Bounding box
        min_lat = min(data['y'] for n, data in self.graph.nodes(data=True))
        min_lon = min(data['x'] for n, data in self.graph.nodes(data=True))
        max_lat = max(data['y'] for n, data in self.graph.nodes(data=True))
        max_lon = max(data['x'] for n, data in self.graph.nodes(data=True))

        # 2. Tính toán kích thước lưới (dựa trên tọa độ)
        lat_len_m = 111320.0
        avg_lat = (min_lat + max_lat) / 2.0
        lon_len_m = 111320.0 * math.cos(math.radians(avg_lat))

        d_lat = self.cell_size_m / lat_len_m
        d_lon = self.cell_size_m / lon_len_m

        # 3. Gán node vào các zone
        zone_nodes = {}
        for node, data in self.graph.nodes(data=True):
            lat = data['y']
            lon = data['x']
            zx = int((lon - min_lon) / d_lon)
            zy = int((lat - min_lat) / d_lat)
            zone_id = f"Z_{zx}_{zy}"
            
            self.node_to_zone[node] = zone_id
            self.graph.nodes[node]['zone_id'] = zone_id

            if zone_id not in zone_nodes:
                zone_nodes[zone_id] = []
            zone_nodes[zone_id].append(node)

        # 4. Tính toán tâm của từng zone (cho macro heuristic)
        for zid, nodes in zone_nodes.items():
            avg_y = sum(self.graph.nodes[n]['y'] for n in nodes) / len(nodes)
            avg_x = sum(self.graph.nodes[n]['x'] for n in nodes) / len(nodes)
            self.zone_centers[zid] = (avg_y, avg_x)
            self.zone_graph.add_node(zid, y=avg_y, x=avg_x)

        # 5. Xây dựng Macro-graph (kết nối giữa các Zone)
        for u, v, data in self.graph.edges(data=True):
            zu = self.node_to_zone[u]
            zv = self.node_to_zone[v]
            if zu != zv:
                if not self.zone_graph.has_edge(zu, zv):
                    lat1, lon1 = self.zone_centers[zu]
                    lat2, lon2 = self.zone_centers[zv]
                    dist = self._haversine(lat1, lon1, lat2, lon2)
                    self.zone_graph.add_edge(zu, zv, weight=dist)

        print(f"Xây dựng ZoneGraph hoàn tất: {self.zone_graph.number_of_nodes()} zones, {self.zone_graph.number_of_edges()} macro-edges.")

    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371000.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def get_zone_path(self, start_zone, end_zone):
        try:
            return nx.shortest_path(self.zone_graph, source=start_zone, target=end_zone, weight='weight')
        except nx.NetworkXNoPath:
            return None

    def get_zone_bounds(self, zone_id):
        parts = zone_id.split('_')
        if len(parts) != 3: return None
        zx = int(parts[1])
        zy = int(parts[2])
        
        min_lat = min(data['y'] for n, data in self.graph.nodes(data=True))
        min_lon = min(data['x'] for n, data in self.graph.nodes(data=True))
        max_lat = max(data['y'] for n, data in self.graph.nodes(data=True))
        
        lat_len_m = 111320.0
        avg_lat = (min_lat + max_lat) / 2.0
        lon_len_m = 111320.0 * math.cos(math.radians(avg_lat))

        d_lat = self.cell_size_m / lat_len_m
        d_lon = self.cell_size_m / lon_len_m
        
        z_min_lon = min_lon + zx * d_lon
        z_max_lon = min_lon + (zx + 1) * d_lon
        z_min_lat = min_lat + zy * d_lat
        z_max_lat = min_lat + (zy + 1) * d_lat
        
        return [[z_min_lat, z_min_lon], [z_max_lat, z_max_lon]]
