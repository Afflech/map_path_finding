import osmnx as ox
import os

def download_and_save_map():
    place_name = "Quận Đống Đa, Hà Nội, Việt Nam"

    os.makedirs("data", exist_ok=True)
    file_path = "data/map_dong_da.graphml"

    print(f"Đang kết nối tới OpenStreetMap để xử lý: {place_name}...")
    print("Vui lòng đợi, quá trình này có thể mất từ 15 - 40 giây...")

    try:
        print("3.1: Đang trích xuất ranh giới hành chính gốc...")
        gdf = ox.geocode_to_gdf(place_name)
        original_polygon = gdf['geometry'].iloc[0]
        
        print("3.2: Đang mở rộng vùng đệm (Buffer) lên ~330 mét...")
        buffered_polygon = original_polygon.buffer(0.003)
        
        print("3.3: Đang tải mạng lưới đường bộ dựa trên ranh giới mở rộng...")
        G = ox.graph_from_polygon(buffered_polygon, network_type="drive", truncate_by_edge=True)
        
        print("3.4: Đang nhồi dữ liệu tốc độ vào các đoạn đường...")
        G = ox.add_edge_speeds(G)
        
        print("Đang lưu dữ liệu vào ổ cứng...")
        ox.save_graphml(G, filepath=file_path)
        
        print("\nTẢI DỮ LIỆU THÀNH CÔNG!")
        print(f"File đã được lưu tại: {file_path}")
        print(f"Chi tiết bản đồ (đã mở rộng): {len(G.nodes)} nút (ngã rẽ) và {len(G.edges)} đoạn đường.")
        
    except Exception as e:
        print(f"\nLỖI: {e} ")
        print("Mẹo: Thử kiểm tra lại kết nối mạng hoặc đổi tên địa danh cho chuẩn xác hơn.")

if __name__ == "__main__":
    download_and_save_map()