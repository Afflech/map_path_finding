import osmnx as ox
import os

def download_and_save_map():
    # 1. Tên địa danh chính xác (lấy từ OSM)
    # Dùng Quận Đống Đa để khớp với hình ảnh ranh giới bạn đang làm
    place_name = "Quận Đống Đa, Hà Nội, Việt Nam"

    # 2. Đảm bảo thư mục 'data' đã tồn tại
    os.makedirs("data", exist_ok=True)
    file_path = "data/map_dong_da.graphml"

    print(f"⏳ Đang kết nối tới OpenStreetMap để xử lý: {place_name}...")
    print("Vui lòng đợi, quá trình này có thể mất từ 15 - 40 giây...")

    try:
        # =========================================================
        # BƯỚC 3: XỬ LÝ RANH GIỚI VÀ TẠO VÙNG ĐỆM (BUFFER)
        # =========================================================
        print("🔍 3.1: Đang trích xuất ranh giới hành chính gốc...")
        # Lấy dữ liệu ranh giới (Polygon) của quận Đống Đa từ OSM
        gdf = ox.geocode_to_gdf(place_name)
        original_polygon = gdf['geometry'].iloc[0]
        
        print("📐 3.2: Đang mở rộng vùng đệm (Buffer) thêm ~100 mét...")
        # Tạo vùng đệm mở rộng thêm 0.001 độ tọa độ địa lý (tương đương khoảng 110-111 mét)
        # Điều này giúp bản đồ "bao trọn" các tuyến đường chạy dọc biên giới như Đường Láng, Tôn Đức Thắng
        buffered_polygon = original_polygon.buffer(0.001)
        
        print("🌍 3.3: Đang tải mạng lưới đường bộ dựa trên ranh giới mở rộng...")
        # Thay vì graph_from_place, ta dùng graph_from_polygon để nạp ranh giới tự chế này vào
        G = ox.graph_from_polygon(buffered_polygon, network_type="drive")
        # =========================================================
        
        # 4. Lưu đồ thị thành file .graphml
        print("💾 Đang lưu dữ liệu vào ổ cứng...")
        ox.save_graphml(G, filepath=file_path)
        
        print("\n✅ TẢI DỮ LIỆU THÀNH CÔNG!")
        print(f"📁 File đã được lưu tại: {file_path}")
        print(f"📊 Chi tiết bản đồ (đã mở rộng): {len(G.nodes)} nút (ngã rẽ) và {len(G.edges)} đoạn đường.")
        
    except Exception as e:
        print(f"\n❌ CÓ LỖI XẢY RA: {e}")
        print("Mẹo: Thử kiểm tra lại kết nối mạng hoặc đổi tên địa danh cho chuẩn xác hơn.")

if __name__ == "__main__":
    download_and_save_map()