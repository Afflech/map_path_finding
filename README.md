# AI Pathfinding cho bản đồ Đống Đa, Hà Nội

Ứng dụng web mô phỏng tìm đường trên mạng lưới đường phố quận Đống Đa. Frontend dùng Leaflet để chọn điểm đi/đến, thiết lập phương tiện và điều kiện mô phỏng; backend dùng đồ thị OpenStreetMap lưu cục bộ để tính nhiều tuyến đường theo thời gian di chuyển.

Giao diện hiện tại được tổ chức theo kiểu dashboard:

- Sidebar bên trái để chọn điểm, thuật toán, phương tiện, tắc đường, lớp ngập và các tuyến thay thế.
- Thẻ kết quả ở đáy giữa để xem quãng đường, thời gian và trạng thái xử lý.
- Thẻ chú giải riêng ở góc phải để đọc nhanh các lớp bản đồ.

Dự án chạy local, không phụ thuộc API định tuyến trả phí. Dữ liệu bản đồ được chuẩn bị một lần bằng OSMnx và lưu tại `backend/data/map_dong_da.graphml`.

## Tính năng chính

- Tìm đường bằng 3 thuật toán: A*, Bidirectional A* và D* Lite.
- Trả về tối đa 3 tuyến thay thế cho A* và Bidirectional A*.
- Mô hình chi phí theo phương tiện: đi bộ, xe máy, ô tô.
- Mô phỏng tắc đường theo mức `Low`, `Normal`, `High`.
- Mô phỏng ngập theo lượng mưa và số làn đường.
- Hỗ trợ đánh dấu điểm tắc/ngập thủ công trên bản đồ.
- Có animation cho các node đã mở rộng; Bidirectional A* hiển thị cả hai hướng.
- Tự sinh chỉ dẫn theo từng đoạn đường.
- Khi ô tô không đi được vào ngõ, backend ghép route đi bộ + ô tô + đi bộ.

## Kiến trúc dự án

```text
map_finding_path/
├── backend/
│   ├── data/
│   │   └── map_dong_da.graphml      # Đồ thị đường phố Đống Đa đã lưu cục bộ
│   ├── app.py                       # Flask API server
│   ├── prepare_data.py              # Tải và lưu dữ liệu bản đồ từ OpenStreetMap
│   ├── solver.py                    # Logic định tuyến và mô hình chi phí
│   ├── requirements.txt             # Dependency Python
│   └── Dockerfile
├── frontend/
│   ├── css/style.css                # Giao diện dashboard và bản đồ
│   ├── js/map_logic.js              # Logic Leaflet, gọi API, vẽ route/animation
│   ├── index.html                   # Bố cục dashboard
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## Luồng xử lý

1. Người dùng click lên bản đồ để chọn điểm đi và điểm đến.
2. Frontend lấy các tham số: phương tiện, thuật toán, mức tắc đường và các điểm cản trở thủ công; lượng mưa và chi phí rẽ hiện được giữ cố định trong giao diện.
3. Frontend gửi request `POST /api/find-path` đến backend.
4. Backend nạp đồ thị, áp điều kiện động lên cạnh, sau đó chạy thuật toán được chọn.
5. Backend trả về route chính, các route thay thế, node đã mở rộng, chỉ dẫn từng đoạn và các cạnh bị ngập.
6. Frontend hiển thị route, animation, chỉ dẫn và thẻ kết quả.

## Mô hình đồ thị

Mạng đường được biểu diễn bằng `networkx.MultiDiGraph`:

- Node là nút giao hoặc điểm tọa độ trên đường.
- Edge là đoạn đường có hướng, chứa chiều dài, loại đường, số làn và metadata từ OpenStreetMap.
- Điểm start/end của người dùng sẽ được map sang node gần nhất bằng `ox.distance.nearest_nodes`.

Chi phí tìm đường trong backend chủ yếu là thời gian di chuyển:

```text
travel_time = effective_length_or_cost / vehicle_speed
```

Trong đó `effective_length_or_cost` có thể bị thay đổi bởi:

- Tắc đường.
- Ngập lụt.
- Điểm cản trở thủ công.
- Penalty trên node để tạo route thay thế.
- Chi phí rẽ khi bật `turn_cost`.

Tốc độ mặc định:

| Phương tiện | API | Tốc độ |
|---|---:|---:|
| Đi bộ | `walk` | 5 km/h |
| Xe máy | `bike` | 25 km/h |
| Ô tô | `car` | 35 km/h |

## Thuật toán định tuyến

### A*

Chế độ `astar` là mặc định. Backend dùng công thức:

```text
f(n) = g(n) + h(n)
```

- `g(n)`: thời gian đã đi từ điểm xuất phát đến node `n`.
- `h(n)`: heuristic Haversine từ `n` đến đích, đổi sang thời gian bằng tốc độ phương tiện.

Chi phí rẽ được cộng thẳng vào cost của route trong frontend hiện tại; backend vẫn hỗ trợ `turn_cost` cho A*.

### Bidirectional A*

Chế độ `bidirectional` mở rộng đồng thời từ điểm đi và điểm đến.

- Nhánh tiến và nhánh lùi đều dùng cùng hàm cost/heuristic.
- Backend trả thêm `explored_nodes_backward` để frontend animate hai hướng bằng hai màu khác nhau.
- Thuật toán dừng khi hai front không còn khả năng tạo đường tốt hơn đường tốt nhất đã tìm thấy.

### D* Lite

Chế độ `dstar_lite` dùng lớp `DStarLite` trong `solver.py`.

- `g` lưu chi phí tốt nhất đã biết.
- `rhs` lưu giá trị nhất quán một bước trước của node.
- Frontier được quản lý bằng priority queue với key dựa trên `g`, `rhs`, heuristic và biến `km`.

Trong phiên bản hiện tại, D* Lite được dùng như một lựa chọn tìm đường trên đồ thị đã được áp điều kiện động trước khi chạy. Khi chọn D* Lite, backend ép `top_k = 1`, nên frontend chỉ hiển thị một tuyến.

## Tạo nhiều tuyến thay thế

A* và Bidirectional A* có thể trả về tối đa 3 tuyến.

Cách làm:

- Chạy thuật toán nhiều lần.
- Sau mỗi route, nhân penalty ngẫu nhiên lên các node trung gian của route vừa chọn.
- Loại route mới nếu độ khác biệt so với các route đã nhận nhỏ hơn ngưỡng `8%`.

Cách này không phải k-shortest path chuẩn, nhưng đủ để tạo các route thay thế có mức phân tán hợp lý trong bối cảnh đồ thị đường phố thực tế.

## Tắc đường, ngập lụt và vật cản

Hàm `apply_mock_conditions` cập nhật trạng thái các cạnh trước mỗi lần tìm đường:

- `Low`: chỉ tăng nhẹ cost theo hệ số `1.2`.
- `Normal`: tăng cost theo hệ số `1.5`, áp dụng ngẫu nhiên khoảng 30% cạnh bằng seed cố định.
- `High`: tăng cost theo hệ số `2.0` cho toàn bộ cạnh.

Ngập lụt được xác định từ `rain_mm` và số làn:

```text
capacity = lanes * 3 * 15
```

Nếu `rain_mm > capacity`:

- `walk` và `car` không được đi qua cạnh đó.
- `bike` vẫn đi được nhưng bị nhân thời gian với hệ số lớn.

Người dùng cũng có thể click để đánh dấu điểm tắc hoặc ngập thủ công. Backend map các điểm này về node gần nhất và áp penalty tương ứng.

## Ô tô trong ngõ

Khi phương tiện là `car`, backend kiểm tra điểm đi hoặc điểm đến có nằm trong ngõ/hẻm hay không.

Nếu có, route sẽ được ghép thành nhiều chặng:

- Đi bộ từ điểm trong ngõ ra node có thể đi ô tô.
- Đi ô tô trên phần đường chính.
- Đi bộ từ node ô tô gần nhất vào điểm đích nếu cần.

Frontend vẽ chặng đi bộ bằng nét đứt và chặng ô tô bằng nét liền. Phần chỉ dẫn lộ trình cũng hiển thị theo từng chặng riêng biệt.

## Backend API

### `POST /api/find-path`

Request body cơ bản:

```json
{
  "start": { "lat": 21.0, "lng": 105.8 },
  "end": { "lat": 21.01, "lng": 105.82 },
  "vehicle": "bike",
  "top_k": 3,
  "traffic_level": "Normal",
  "rain_mm": 100,
  "algorithm": "astar",
  "turn_cost": true,
  "obstacles": {
    "jammed": [],
    "flooded": []
  }
}
```

Response thành công trả về:

- `data.path`: tuyến chính.
- `data.routes`: danh sách route.
- `data.explored_nodes`: node đã mở rộng.
- `data.explored_nodes_backward`: node đã mở rộng theo hướng lùi, nếu là Bidirectional A*.
- `data.flooded_edges`: các cạnh bị ngập để frontend tô màu.
- `status: success`.

## Công nghệ sử dụng

| Phần | Công nghệ |
|---|---|
| Backend | Python, Flask, Flask-CORS, OSMnx, NetworkX |
| Frontend | HTML, CSS, Vanilla JavaScript, Leaflet |
| Dữ liệu bản đồ | OpenStreetMap, lưu cục bộ bằng GraphML |
| Triển khai local | Docker, Docker Compose |

## Cài đặt và chạy thủ công

Yêu cầu:

- Python 3.9+.
- Trình duyệt hiện đại.
- Kết nối Internet nếu cần tải lại dữ liệu bản đồ bằng `prepare_data.py`.
- Nếu máy bạn không có lệnh `python`, hãy dùng `python3` tương đương.

Tạo môi trường Python và cài dependency:

```bash
python -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```

Trên Windows:

```powershell
backend\venv\Scripts\activate
```

Nếu chưa có `backend/data/map_dong_da.graphml`, tải dữ liệu bản đồ:

```bash
cd backend
python prepare_data.py
```

Chạy backend:

```bash
cd backend
python app.py
```

Backend chạy tại `http://localhost:5000`.

Sau đó mở `frontend/index.html` trong trình duyệt hoặc dùng một static server/Live Server cho thư mục `frontend`.

## Chạy bằng Docker

Đảm bảo file `backend/data/map_dong_da.graphml` đã tồn tại, rồi chạy:

```bash
docker compose up --build --force-recreate
```

Frontend được mount vào container Nginx trong `docker-compose.yml`, nên khi sửa `frontend/index.html`, `frontend/css/style.css` hoặc `frontend/js/map_logic.js`, refresh trình duyệt sẽ thấy thay đổi ngay. Nếu vẫn thấy giao diện cũ, hard refresh trình duyệt hoặc chạy lại lệnh trên để tạo container mới.

Địa chỉ mặc định:

- Frontend: `http://localhost`
- Backend: `http://localhost:5000`

Dừng container:

```bash
docker compose down
```

## Cách dùng giao diện

1. Click lên bản đồ để chọn điểm đi.
2. Click lần nữa để chọn điểm đến.
3. Chọn phương tiện và thuật toán trong sidebar.
4. Điều chỉnh tắc đường và lớp ngập lụt theo trạng thái hiện tại.
5. Chọn chế độ click `Đánh dấu Tắc đường` hoặc `Đánh dấu Ngập lụt` nếu muốn thêm vật cản thủ công.
6. Xem Tuyến 1/2/3 trong hộp chọn tuyến. Với D* Lite chỉ có Tuyến 1.
7. Mở `Chi tiết lộ trình` để xem chỉ dẫn theo từng đoạn đường.

## Ghi chú triển khai

- `turn_cost` vẫn được backend hỗ trợ cho A* và hiện được frontend giữ bật mặc định.
- `clickMode` được reset về chế độ chọn điểm khi bấm làm mới bản đồ.
- `syncControlSummary()` trong frontend đồng bộ các chip trạng thái với giá trị select hiện tại.
- Chỉ dẫn lộ trình được gom lại để tránh lặp từng bước nhỏ cùng một street.
