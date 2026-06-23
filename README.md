# Đống Đa Navigator 🗺️

Hệ thống dẫn đường thông minh và phân tích đồ thị đường phố nâng cao dành riêng cho khu vực Quận Đống Đa, Hà Nội. Dự án khai thác dữ liệu thực tế từ OpenStreetMap (OSM) và áp dụng các mô hình thuật toán đa tiêu chí phức tạp để mô phỏng, tối ưu hoá lộ trình di chuyển.

## 🌟 Các tính năng nổi bật

### 1. Giao diện trực quan (Modern Navy Theme)
- Thiết kế UI hiện đại, tập trung vào trải nghiệm người dùng với hoạt ảnh tương tác (Micro-animations).
- **Node Exploration Animation**: Hiển thị trực quan quá trình thuật toán quét các node trên bản đồ.
- **Zone Visualization**: Tuỳ chọn vẽ lưới phân lô không gian (Zones Bounds) để trực quan hóa cách thức thuật toán phân cấp hoạt động.
- Tính năng ẩn/hiện bảng Đánh giá hiệu năng thuật toán ngay trên Result Card.

### 2. Mô hình Chi phí Đa tiêu chí (Multi-Criteria Cost Model)
Thay vì chỉ tính khoảng cách đơn thuần, hệ thống đánh giá thời gian di chuyển thật qua 4 yếu tố:
- **Travel Time (Cơ bản)**: Phụ thuộc vào loại phương tiện (Ô tô, Xe máy, Đi bộ) và tốc độ cho phép của tuyến đường.
- **Traffic Penalty**: Tự động tính toán độ trễ dựa trên lưu lượng giao thông (Low, Normal, High).
- **Flood Risk**: Tránh hoặc cộng thêm hình phạt thời gian nếu di chuyển qua các điểm ngập úng khi trời mưa lón.
- **Turn Penalty**: Phạt thời gian nếu lộ trình bắt người dùng phải rẽ trái, rẽ ngược (U-turn) quá nhiều.

### 3. Phân cấp Không gian (Zone-Based Hierarchical Pathfinding)
- Phân vùng toàn bộ đồ thị đường phố (Micro-graph) lên tới hàng vạn node thành các ô **Grid 500m x 500m** (Macro-graph).
- Kỹ thuật **Tách đồ thị con (Sub-graph extraction)** giúp thu hẹp phạm vi tìm kiếm, giảm tải tính toán từ $O(N \log N)$ xuống mức tối thiểu, đem lại kết quả phản hồi gần như ngay lập tức kể cả với các tuyến đường dài.

### 4. Thuật toán Đàn Kiến phân cấp (ACO trên Zone Graph)
- Khắc phục nhược điểm cực kỳ chậm của thuật toán ACO (Ant Colony Optimization) trên đồ thị lớn.
- Bầy kiến thám hiểm trên Macro-graph (66 zones) thay vì dò dẫm trên Micro-graph.
- Kết hợp với Local A* để hoàn thiện các nét đứt gãy, giúp hệ thống không chỉ nhanh mà còn cung cấp **nhiều giải pháp lộ trình thay thế (Diverse routes)** thay vì chỉ cứng nhắc 1 đường đi ngắn nhất.

### 5. So sánh Hiệu năng trực tiếp (Benchmarking)
Mỗi truy vấn đều được đối chiếu chéo (Cross-check) giữa nhiều thuật toán khác nhau:
- **A* Tiêu chuẩn**
- **Bidirectional A***
- **D* Lite** (Động)
- **Hierarchical A***
- **ACO trên Zone Graph**

Các chỉ số (Nodes explored, Computation Time, Distance, Memory footprint) được hiển thị trực tiếp để người dùng tiện đánh giá sự tối ưu của các phương pháp.

---

## 🛠️ Kiến trúc hệ thống & Công nghệ sử dụng
- **Ngôn ngữ cốt lõi**: Python 3.9+ (Backend), JavaScript (Frontend)
- **Xử lý Đồ thị**: `NetworkX`, `OSMnx`
- **Web Backend Framework**: `Flask`, `Flask-CORS`
- **Frontend**: Vanilla JS, HTML5, CSS3 kết hợp thư viện Bản đồ `Leaflet.js`
- **Triển khai**: `Docker` & `Docker Compose`

---

## 🚀 Hướng dẫn cài đặt và chạy dự án

### Yêu cầu
- Đã cài đặt Docker và Docker Compose.

### Bước 1: Khởi động hệ thống
Mở terminal tại thư mục gốc của dự án và chạy lệnh sau:
```bash
docker compose up -d --build
```
*Lưu ý: Quá trình khởi động lần đầu có thể mất một chút thời gian để tải dữ liệu graphml của Đống Đa.*

### Bước 2: Truy cập ứng dụng
- **Frontend** (Trang tương tác trực tiếp): Mở file `frontend/index.html` bằng trình duyệt của bạn (Chrome, Edge, Safari...).
- **Backend API**: Chạy mặc định tại địa chỉ `http://localhost:5000/api/find-path`.

### Bước 3: Đóng hệ thống
Khi không còn sử dụng, chạy lệnh sau để dọn dẹp container:
```bash
docker compose down
```

---

## 📂 Cấu trúc thư mục
```text
.
├── backend/
│   ├── algorithms/       # (Tích hợp bên trong solver.py & aco.py)
│   ├── app.py            # API Server (Flask)
│   ├── solver.py         # Lõi thuật toán A*, D* Lite, Hierarchical
│   ├── aco.py            # Thuật toán Đàn Kiến (Ant Colony Optimization)
│   ├── zone_manager.py   # Phân cấp đồ thị lưới (Zone Graph)
│   ├── cost_model.py     # Tính toán Multi-criteria Cost Breakdown
│   └── data/
│       └── map_dong_da.graphml  # Dữ liệu OSM tĩnh (Cache)
├── frontend/
│   ├── index.html        # Giao diện chính
│   ├── css/
│   │   └── style.css     # Navy Theme, Responsive layout
│   └── js/
│       └── map_logic.js  # Tương tác Leaflet bản đồ & API Calls
├── docker-compose.yml
└── README.md
```

---
*Dự án được phát triển và tối ưu hoá nhằm mục đích trình diễn các thuật toán lý thuyết đồ thị ứng dụng vào thực tiễn.*
