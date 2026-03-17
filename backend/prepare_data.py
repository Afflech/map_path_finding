import osmnx as ox
import os

def download_and_save_map():
    # 1. Tên địa danh chính xác (lấy từ OSM như bạn đã tra cứu)
    place_name = "Phường Đống Đa, Vĩnh Yên, Vĩnh Phúc, Việt Nam" 
    
    # LƯU Ý QUAN TRỌNG: 
    # Nếu bạn đang tìm Quận Đống Đa ở Hà Nội, OSM dùng tên là "Đống Đa, Hà Nội, Việt Nam" 
    # Còn "Phường Đống Đa" thì thường nằm ở Vĩnh Yên. 
    # Dựa vào ảnh của bạn (Dong Da Ward), có vẻ bạn đang muốn lấy Quận Đống Đa. 
    # Hãy thử dùng: place_name = "Quận Đống Đa, Hà Nội, Việt Nam" nếu code dưới bị lỗi nhé.
    
    # Để chắc chắn chạy được cho ảnh bạn gửi, ta dùng Quận:
    place_name = "Quận Đống Đa, Hà Nội, Việt Nam"

    # 2. Đảm bảo thư mục 'data' đã tồn tại
    os.makedirs("data", exist_ok=True)
    file_path = "data/map_dong_da.graphml"

    print(f"⏳ Đang kết nối tới OpenStreetMap để tải: {place_name}...")
    print("Vui lòng đợi, quá trình này có thể mất từ 10 - 30 giây...")

    try:
        # 3. Tải đồ thị mạng lưới đường bộ (chỉ lấy đường cho xe cộ)
        G = ox.graph_from_place(place_name, network_type="drive")
        
        # 4. Lưu đồ thị thành file .graphml
        ox.save_graphml(G, filepath=file_path)
        
        print("\n✅ TẢI DỮ LIỆU THÀNH CÔNG!")
        print(f"📁 File đã được lưu tại: {file_path}")
        print(f"📊 Chi tiết bản đồ: {len(G.nodes)} nút (ngã rẽ/điểm) và {len(G.edges)} đoạn đường.")
        
    except Exception as e:
        print(f"\n❌ CÓ LỖI XẢY RA: {e}")
        print("Mẹo: Thử kiểm tra lại kết nối mạng hoặc đổi tên địa danh cho chuẩn xác hơn.")

if __name__ == "__main__":
    download_and_save_map()