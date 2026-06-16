# Ứng dụng AI trong Định tuyến Giao thông Khu vực Quận Đống Đa, Hà Nội

Dự án này là một hệ thống **định tuyến giao thông thông minh** được thiết kế riêng cho mạng lưới đường phố thuộc quận **Đống Đa, Hà Nội**. Chương trình sử dụng các thuật toán Tìm kiếm có Thông tin (Informed Search) trong Trí tuệ Nhân tạo để tìm kiếm lộ trình tối ưu dựa trên thời gian di chuyển thực tế dưới sự ảnh hưởng của các yếu tố động như ùn tắc giao thông và ngập lụt.

Hệ thống được thiết kế chạy hoàn toàn trên **Localhost**, kết nối trực tiếp đến dữ liệu đồ thị đường phố thực tế từ nguồn **OpenStreetMap (OSM)** mà không cần phụ thuộc vào bất kỳ dịch vụ API tính phí bên ngoài nào.

---

## Mục lục

1. [Cấu trúc Thư mục & Mã nguồn](#1-cấu-trúc-thư-mục--mã-nguồn)
2. [Mô hình hóa Không gian Trạng thái (State Space)](#2-mô-hình-hóa-không-gian-trạng-thái-state-space)
3. [Các Giải thuật & Cơ chế Cốt lõi](#3-các-giải-thuật--cơ-chế-cốt-lõi)
   - [Thuật toán A* & Hàm Đánh giá](#thuật-toán-a--hàm-đánh-giá)
   - [Định tuyến Top-K Lộ trình đa dạng (Diverse Routes)](#định-tuyến-top-k-lộ-trình-đa-dạng-diverse-routes)
   - [Định tuyến đa phương thức & Nhận diện Ngõ nhỏ (Multi-modal & Alley Detection)](#định-tuyến-đa-phương-thức--nhận-diện-ngõ-nhỏ-multi-modal--alley-detection)
   - [Mô phỏng Giao thông động (Traffic Simulation)](#mô-phỏng-giao-thông-động-traffic-simulation)
   - [Mô phỏng và Tránh Ngập lụt (Flood Avoidance)](#mô-phỏng-và-tránh-ngập-lụt-flood-avoidance)
4. [Công nghệ Sử dụng](#4-công-nghệ-sử-dụng)
5. [Hướng dẫn Cài đặt & Vận hành](#5-hướng-dẫn-cài-đặt--vận-hành)
   - [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
   - [Cách 1: Cài đặt thủ công](#cách-1-cài-đặt-thủ-công)
   - [Cách 2: Chạy bằng Docker](#cách-2-chạy-bằng-docker)
6. [API Documentation](#6-api-documentation)

---

## 1. Cấu trúc Thư mục & Mã nguồn

Dự án được phân chia rõ ràng thành hai phần chính: **Backend** (xử lý logic tìm đường bằng Python) và **Frontend** (giao diện người dùng web tương tác).

```text
map_finding_path/
├── backend/
│   ├── data/
│   │   └── map_dong_da.graphml      # File đồ thị đường phố đã được biên dịch lưu cục bộ
│   ├── cache/                       # Cache kết quả truy vấn địa lý
│   ├── app.py                       # Flask API Server nhận và trả về dữ liệu định tuyến
│   ├── prepare_data.py              # Script tải, xây dựng và lưu đồ thị địa lý từ OSMnx
│   ├── solver.py                    # Nhân tính toán định tuyến (A*, Top-K, Multi-modal, Trọng số)
│   ├── requirements.txt             # Danh sách thư viện Python cần thiết
│   └── Dockerfile                   # Cấu hình container hóa cho backend
├── frontend/
│   ├── css/
│   │   └── style.css                # Định dạng giao diện Web, hiệu ứng và các bảng điều khiển
│   ├── js/
│   │   └── map_logic.js             # Điều khiển bản đồ Leaflet, tương tác chuột, vẽ các chặng và animation
│   ├── index.html                   # Giao diện hiển thị bản đồ trực quan
│   └── Dockerfile                   # Cấu hình container hóa cho frontend (Nginx)
├── docker-compose.yml               # Quản lý chạy ứng dụng đa container
└── README.md                        # Tài liệu hướng dẫn sử dụng (File này)
```

---

## 2. Mô hình hóa Không gian Trạng thái (State Space)

Để giải quyết bài toán tìm đường bằng thuật toán AI, mạng lưới giao thông quận Đống Đa được hình thức hóa thành không gian trạng thái như sau:

| Thành phần | Định nghĩa toán học & Thực tiễn trong Dự án |
|---|---|
| **Môi trường** | Một đồ thị có hướng đa cạnh $G = (V, E)$. Mỗi nút $v \in V$ đại diện cho một ngã rẽ hoặc điểm tọa độ địa lý. Mỗi cạnh có hướng $e \in E$ nối giữa hai nút đại diện cho một làn/đoạn đường một chiều. Đồ thị được lưu trong file `backend/data/map_dong_da.graphml`. |
| **Trạng thái ($S$)** | Một nút $v \in V$, được đặc trưng bởi tọa độ địa lý $(\text{vĩ độ}, \text{kinh độ}) = (\text{lat}, \text{lng})$. |
| **Trạng thái bắt đầu ($S_0$)** | Nút $v_{start} \in V$ gần nhất với tọa độ nhấp chuột chọn điểm xuất phát của người dùng trên bản đồ. |
| **Trạng thái đích ($S_g$)** | Nút $v_{goal} \in V$ gần nhất với tọa độ điểm đến mong muốn của người dùng. |
| **Hành động ($A$)** | Di chuyển từ nút hiện tại $u$ sang nút liền kề $v$ thông qua cạnh $e(u, v) \in E$. Hành động này bị ràng buộc bởi loại phương tiện (ví dụ: ô tô không đi vào ngõ) và trạng thái ngập lụt (đường ngập không thể đi qua). |
| **Hàm chuyển trạng thái ($Result$)** | $Result(u, \text{đi qua cạnh } e(u,v)) = v$. |
| **Chi phí đường đi ($Path\ Cost$)** | **Thời gian di chuyển tích lũy** (tính bằng giây). Chi phí của một cạnh $e(u, v)$ được tính bằng công thức: $T = \frac{\text{Độ dài thực tế } (m)}{\text{Vận tốc hiệu dụng } (m/s)}$. Vận tốc hiệu dụng phụ thuộc vào loại phương tiện, mức độ tắc đường và mưa ngập trên đoạn đường đó. |

---

## 3. Các Giải thuật & Cơ chế Cốt lõi

Hệ thống định vị thông minh này không chỉ tìm đường đơn thuần mà còn tích hợp các cơ chế mô phỏng phức tạp để mô tả đúng điều kiện giao thông tại Việt Nam:

### Thuật toán A* & Hàm Đánh giá
Giải thuật tìm đường cốt lõi là **A\*** với hàm đánh giá:
$$f(n) = g(n) + h(n)$$
*   **$g(n)$**: Chi phí thời gian thực tế đã tích lũy từ điểm xuất phát đến nút $n$.
*   **$h(n)$**: Hàm heuristic ước lượng thời gian đi từ $n$ tới đích. Heuristic này được tính bằng **khoảng cách Haversine** (đường chim bay trên bề mặt Trái Đất) chia cho vận tốc lớn nhất có thể của phương tiện đang sử dụng:
    $$h(n) = \frac{d_{\text{Haversine}}(n, \text{goal})}{v_{\text{max}}}$$
    Do khoảng cách đường chim bay luôn nhỏ hơn hoặc bằng quãng đường đi thực tế, hàm heuristic này luôn **admissible** (chấp nhận được - không bao giờ đánh giá cao hơn chi phí thực tế) và **consistent** (nhất quán), đảm bảo thuật toán A\* tìm ra **đường đi tối ưu tuyệt đối về thời gian**.

### Định tuyến Top-K Lộ trình đa dạng (Diverse Routes)
Để cung cấp cho người dùng 3 tuyến đường lựa chọn (Tuyến 1, Tuyến 2, Tuyến 3):
1.  Hệ thống chạy A\* lần đầu để tìm tuyến đường tối ưu nhất.
2.  Để tìm tuyến thứ 2 và thứ 3 có độ đa dạng cao (tránh trùng lặp đường cũ quá nhiều):
    *   Hệ thống kiểm tra mức độ trùng lặp giữa lộ trình ứng viên với các lộ trình đã được duyệt nhận dạng thông qua chỉ số:
        $$\text{Trùng lặp} = \frac{|V_{\text{ứng viên}} \cap V_{\text{đã nhận}}|}{|V_{\text{ứng viên}}|}$$
    *   Nếu tỷ lệ không trùng lặp (divergence) nhỏ hơn **$8\%$** (`MIN_ROUTE_DIVERGENCE_RATIO` = 0.08, tức trùng lặp quá 92%), lộ trình ứng viên sẽ bị loại bỏ.
    *   Khi xảy ra trùng lặp hoặc khi muốn khám phá lộ trình mới, các nút trên lộ trình cũ sẽ bị phạt trọng số thời gian bằng cách nhân thêm một hệ số ngẫu nhiên từ **$1.10$ đến $1.45$** (`RANDOM_NODE_PENALTY_MIN` và `RANDOM_NODE_PENALTY_MAX`).
    *   Thuật toán A\* được chạy lại trên đồ thị đã bị phạt trọng số để ép tìm đường đi tránh các nút của tuyến trước đó.

### Định tuyến đa phương thức & Nhận diện Ngõ nhỏ (Multi-modal & Alley Detection)
Một điểm đặc trưng của đô thị Hà Nội là hệ thống ngõ nhỏ. Nếu người dùng chọn đi bằng **Ô tô** nhưng điểm xuất phát hoặc điểm kết thúc nằm trong ngõ hẻm (`living_street`, `service`, `pedestrian`, `footway`, `path`):
1.  Hệ thống sẽ tự động nhận diện các điểm này nằm trong khu vực ô tô không thể vào được (`_node_is_in_alley`).
2.  Hệ thống chạy thuật toán loang BFS từ ngõ ra ngoài để tìm nút giao lộ gần nhất có đường lớn ô tô đi được (`_find_nearest_car_node`).
3.  Lộ trình được chia làm **3 chặng**:
    *   **Chặng 1 (Đi bộ - nét đứt xanh lá):** Từ điểm xuất phát trong ngõ đi bộ ra điểm kết nối đường lớn.
    *   **Chặng 2 (Ô tô - nét liền xanh dương):** Di chuyển bằng ô tô trên hệ thống đường lớn liên kết.
    *   **Chặng 3 (Đi bộ - nét đứt xanh lá):** Từ điểm đỗ xe ở đường lớn đi bộ vào đích nằm trong ngõ nhỏ.

### Mô phỏng Giao thông động (Traffic Simulation)
Trước mỗi phiên tìm kiếm đường đi, backend sẽ áp dụng ngẫu nhiên một trạng thái ùn tắc giao thông giả lập trên khoảng $30\%$ số cạnh (hoặc $100\%$ nếu mức tắc đường là Cao) thông qua hàm `apply_mock_conditions` trong `solver.py`:
*   **Vắng vẻ (Low):** Nhân chiều dài cạnh với hệ số phạt $1.2$.
*   **Bình thường (Normal):** Nhân chiều dài cạnh với hệ số phạt $1.5$.
*   **Đông đúc (High):** Nhân chiều dài cạnh với hệ số phạt $2.0$.

### Mô phỏng và Tránh Ngập lụt (Flood Avoidance)
Hệ thống sử dụng lượng mưa đo bằng milimét (người dùng kéo trên thanh trượt từ $0\text{mm}$ đến $100\text{mm}$) và số làn đường (`lanes`) có sẵn trong metadata của cạnh để xác định xem một đoạn đường có bị ngập hay không.
*   **Công thức tính công suất thoát nước của đường:**
    $$C = \text{lanes} \times 3 \text{ (mét)} \times 15 \text{ (mm/h)}$$
*   **Nếu lượng mưa $\text{rain\_mm} > C$**: Đường bị coi là **Ngập lụt**.
*   **Quy tắc điều hướng khi ngập lụt:**
    *   **Người đi bộ (`walk`) & Ô tô (`car`):** Bị cấm hoàn toàn qua đoạn đường ngập (trọng số thời gian trở thành vô cùng lớn $\infty$).
    *   **Xe máy (`bike`):** Vẫn có thể lội nước nhưng bị phạt thời gian di chuyển gấp **$20$ lần** bình thường (`FLOODED_BIKE_PENALTY_FACTOR` = 20.0).

---

## 4. Công nghệ Sử dụng

| Tầng công nghệ | Các thư viện & Công cụ chi tiết |
|---|---|
| **Backend** | **Python 3.9+** làm ngôn ngữ chính. **OSMnx** trích xuất và chuẩn hóa đồ thị giao thông từ OpenStreetMap. **NetworkX** quản lý cấu trúc dữ liệu đồ thị có hướng đa cạnh (`MultiDiGraph`). **Flask & Flask-CORS** tạo REST API giao tiếp dữ liệu JSON giữa Backend và Frontend. |
| **Frontend** | **HTML5, CSS3** thiết kế giao diện phẳng dạng thẻ (card) nổi hiện đại, hỗ trợ hiệu ứng bóng mờ và nút switch phong cách Material Design. **Vanilla JavaScript (ES6)** xử lý logic sự kiện, tương tác bản đồ, gọi fetch API không đồng bộ. |
| **Bản đồ trực quan** | **Leaflet.js** bản đồ nền tương tác mã nguồn mở gọn nhẹ. **OpenStreetMap Tiles** cung cấp các mảnh bản đồ nền hình ảnh. **Nominatim API** truy vấn ranh giới hành chính Quận Đống Đa để vẽ viền đa giác bao quanh quận. |
| **Container hóa** | **Docker & Docker Compose** đóng gói backend (Python) và frontend (Nginx) thành các container độc lập, triển khai bằng một lệnh duy nhất. |

---

## 5. Hướng dẫn Cài đặt & Vận hành

### Yêu cầu hệ thống
*   **Python 3.9** trở lên (nếu cài thủ công).
*   **Docker & Docker Compose** (nếu dùng phương án container).
*   Một trình duyệt web hiện đại (Chrome, Edge, Firefox, Safari).

### Cách 1: Cài đặt thủ công

#### Bước 1: Chuẩn bị mã nguồn
Tải dự án về máy và di chuyển vào thư mục dự án:
```bash
git clone https://github.com/<your-username>/map_finding_path.git
cd map_finding_path
```

#### Bước 2: Khởi tạo Môi trường ảo Python
```bash
python -m venv backend/venv

# Kích hoạt môi trường ảo:
# Trên Windows (PowerShell/CMD):
backend\venv\Scripts\activate

# Trên Linux/macOS:
source backend/venv/bin/activate
```

#### Bước 3: Cài đặt các thư viện phụ thuộc
```bash
pip install -r backend/requirements.txt
```

#### Bước 4: Tải dữ liệu bản đồ nền (Chỉ chạy một lần đầu tiên)
Để tạo file đồ thị `map_dong_da.graphml`, hãy chạy script tải dữ liệu từ OpenStreetMap:
```bash
cd backend
python prepare_data.py
```
*Lưu ý: Quá trình này yêu cầu máy tính có kết nối Internet để tải dữ liệu địa lý của Quận Đống Đa (~330m vùng đệm). Khi màn hình thông báo `TẢI DỮ LIỆU THÀNH CÔNG!` và file `backend/data/map_dong_da.graphml` được tạo ra, bạn có thể chạy server ngoại tuyến.*

#### Bước 5: Khởi động Flask Server (Backend)
Vẫn ở trong thư mục `backend`, khởi chạy backend API:
```bash
python app.py
```
Server sẽ được kích hoạt tại địa chỉ: `http://localhost:5000`.

#### Bước 6: Khởi chạy Giao diện (Frontend)
*   Mở trực tiếp tệp `frontend/index.html` bằng trình duyệt web.
*   Hoặc sử dụng extension **Live Server** trên VS Code để khởi động một local server tĩnh cho frontend.

### Cách 2: Chạy bằng Docker

Đảm bảo `backend/data/map_dong_da.graphml` đã tồn tại (chạy `prepare_data.py` trước nếu chưa có), sau đó:

```bash
docker compose up --build
```

*   **Backend:** `http://localhost:5000`
*   **Frontend:** `http://localhost:80`

Để chạy ngầm (background):
```bash
docker compose up --build -d
```

Để dừng tất cả container:
```bash
docker compose down
```

---

## 6. API Documentation

### `POST /api/find-path`

Tìm đường đi giữa hai điểm trên bản đồ.

**Request body (JSON):**

```json
{
  "start": { "lat": 21.012, "lng": 105.824 },
  "end": { "lat": 21.018, "lng": 105.832 },
  "vehicle": "bike",
  "top_k": 3,
  "traffic_level": "Normal",
  "rain_mm": 0,
  "jammed": [{ "lat": 21.015, "lng": 105.828 }],
  "flooded": []
}
```

| Trường | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `start` | `{lat, lng}` | *bắt buộc* | Tọa độ điểm xuất phát |
| `end` | `{lat, lng}` | *bắt buộc* | Tọa độ điểm đến |
| `vehicle` | `string` | `"bike"` | Phương tiện: `walk` (5 km/h), `bike` (25 km/h), `car` (35 km/h) |
| `top_k` | `int` | `3` | Số tuyến đường trả về (1-10) |
| `traffic_level` | `string` | `"Normal"` | Mức độ tắc đường: `Low`, `Normal`, `High` |
| `rain_mm` | `float` | `0.0` | Lượng mưa (mm), ảnh hưởng đến ngập lụt |
| `jammed` | `array` | `[]` | Danh sách tọa độ các điểm tắc đường thủ công |
| `flooded` | `array` | `[]` | Danh sách tọa độ các điểm ngập lụt thủ công |

**Response thành công (200):**

```json
{
  "status": "success",
  "flooded_edges": [[[21.012, 105.824], [21.013, 105.825]]],
  "data": {
    "path": [{"lat": 21.012, "lng": 105.824}],
    "explored_nodes": [[21.012, 105.824]],
    "distance_m": 1234.5,
    "duration_min": 3.2,
    "routes": [
      {
        "rank": 1,
        "path": [{"lat": 21.012, "lng": 105.824}],
        "explored_nodes": [[21.012, 105.824]],
        "distance_m": 1234.5,
        "duration_min": 3.2,
        "instructions": [
          {"action": "straight", "street": "Phố Tây Sơn", "distance_m": 120.0},
          {"action": "left", "street": "Phố Chùa Bộc", "distance_m": 85.3}
        ]
      }
    ]
  }
}
```

**Response lỗi (400/404/500):**

```json
{
  "status": "error",
  "message": "Không tìm thấy tuyến phù hợp với điều kiện hiện tại."
}
```

---

## Hướng dẫn sử dụng trên Bản đồ

1.  **Chọn điểm Đi và Đến:** Click chuột trái lần lượt vào 2 điểm bất kỳ trên khu vực Quận Đống Đa trên bản đồ để đặt điểm đi (ghim màu xanh) và điểm đến (ghim màu đỏ).
2.  **Định cấu hình các thông số:**
    *   Chọn phương tiện: *Đi bộ*, *Xe máy*, *Ô tô*.
    *   Điều chỉnh mức độ tắc đường và kéo thanh trượt lượng mưa (nếu lượng mưa vượt công suất thoát nước của đường, đường sẽ hiển thị màu xanh lam báo ngập).
    *   Chọn các tuyến thay thế: Tuyến 1, Tuyến 2 hoặc Tuyến 3.
3.  **Tạo chướng ngại vật thủ công:**
    *   Chuyển mục "Chọn Điểm Đi/Đến" sang "Đánh dấu Tắc đường" hoặc "Đánh dấu Ngập lụt".
    *   Click vào bản đồ để tạo các điểm chướng ngại vật tùy ý để xem thuật toán tự động tránh các điểm đó như thế nào.
4.  **Bật/Tắt Animation:** Để xem cách thuật toán A\* loang rộng (các node đã được duyệt - màu xanh lam nhạt) trước khi tìm thấy tuyến tối ưu.
