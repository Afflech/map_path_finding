# 🗺️ Báo cáo Bài tập lớn: Ứng dụng AI trong Định tuyến Giao thông Khu vực Đống Đa

> **Môn học:** Nhập môn Trí tuệ Nhân tạo  
> **Trường:** *Trường Công nghệ Thông tin và Truyền thông *  
> **Học kỳ:** *20252*


---

## 📋 Mục lục

1. [Giới thiệu tổng quan](#1-giới-thiệu-tổng-quan)
2. [Mô hình hóa bài toán](#2-mô-hình-hóa-bài-toán-state-space)
3. [Thuật toán cốt lõi — A\*](#3-thuật-toán-cốt-lõi--a-star)
4. [Tính năng nổi bật](#4-tính-năng-nổi-bật)
5. [Công nghệ sử dụng](#5-công-nghệ-sử-dụng)
6. [Hướng dẫn cài đặt](#6-hướng-dẫn-cài-đặt-localhost)
7. [Nhóm tác giả](#7-nhóm-tác-giả)

---

## 1. Giới thiệu tổng quan

Dự án xây dựng một hệ thống **định tuyến giao thông thông minh** trên bản đồ đường phố quận **Đống Đa, Hà Nội**, ứng dụng các kỹ thuật tìm kiếm trong Trí tuệ Nhân tạo để giải quyết bài toán thực tế.

**Mục tiêu chính:**

- Tìm **đường đi ngắn nhất / nhanh nhất** giữa hai điểm bất kỳ trên đồ thị đường phố thực.
- Hỗ trợ **nhiều phương tiện** với vận tốc và ràng buộc đường đi khác nhau.
- Mô phỏng các điều kiện giao thông động: **tắc đường** và **ngập lụt**.
- Trực quan hóa quá trình tìm kiếm và kết quả trên bản đồ tương tác.

Dữ liệu bản đồ được trích xuất từ **OpenStreetMap** và lưu dưới dạng file tĩnh `.graphml`, hệ thống chạy hoàn toàn trên **localhost** mà không phụ thuộc API bên ngoài.

---

## 2. Mô hình hóa bài toán (State Space)

Bài toán tìm đường được hình thức hóa theo mô hình **không gian trạng thái** như sau:

| Thành phần | Định nghĩa |
|---|---|
| **Môi trường** | Đồ thị có hướng `G = (V, E)` — mỗi **node** `v ∈ V` là một giao lộ/điểm trên đường phố, mỗi **cạnh** `e ∈ E` là một đoạn đường nối hai node. Đồ thị được load từ file `map_dong_da.graphml`. |
| **Trạng thái** | Một node `v` xác định bởi tọa độ địa lý `(lat, lng)`. Trạng thái ban đầu là node gần nhất với điểm xuất phát do người dùng chọn. |
| **Hành động** | Di chuyển từ node `u` sang node `v` qua cạnh `(u, v) ∈ E`, với điều kiện cạnh đó **không bị ngập** và **phù hợp với phương tiện** đang dùng. |
| **Goal** | Node đích — node gần nhất với tọa độ điểm đến do người dùng chọn. |
| **Path Cost** | Tổng **thời gian di chuyển** (giây) trên toàn bộ lộ trình, tính theo công thức `T = S / v` với `S` là chiều dài cạnh (m) và `v` là vận tốc phương tiện (m/s). Chi phí được điều chỉnh động bởi hệ số tắc đường và trạng thái ngập lụt. |

---

## 3. Thuật toán cốt lõi — A* (A-Star)

Hệ thống sử dụng thuật toán **A\*** — một thuật toán tìm kiếm có thông tin (informed search) — để tìm đường đi tối ưu theo chi phí thời gian.

### Hàm đánh giá

$$f(n) = g(n) + h(n)$$

| Ký hiệu | Ý nghĩa |
|---|---|
| `f(n)` | Ước lượng tổng chi phí của đường đi qua node `n` |
| `g(n)` | Chi phí thực tế đã đi từ node xuất phát đến node `n` (tổng thời gian di chuyển tích lũy) |
| `h(n)` | Hàm heuristic — ước lượng chi phí từ `n` đến đích |

### Hàm Heuristic h(n) — Khoảng cách Haversine

Heuristic sử dụng **khoảng cách đường chim bay** giữa node `n` và node đích, tính bằng công thức **Haversine**:

$$h(n) = \frac{d_{\text{Haversine}}(n,\ \text{goal})}{v}$$

Trong đó:

$$d_{\text{Haversine}} = 2R \cdot \arctan2\!\left(\sqrt{a},\ \sqrt{1-a}\right)$$

$$a = \sin^2\!\left(\frac{\Delta\phi}{2}\right) + \cos\phi_1 \cdot \cos\phi_2 \cdot \sin^2\!\left(\frac{\Delta\lambda}{2}\right)$$

- `R = 6,371,000 m` — bán kính Trái Đất
- `φ`, `λ` — vĩ độ và kinh độ (radian)
- `v` — vận tốc phương tiện (m/s)

Heuristic này **admissible** (không bao giờ ước lượng vượt quá chi phí thực) vì khoảng cách đường chim bay luôn ≤ khoảng cách đường thực tế, đảm bảo A\* trả về **lộ trình tối ưu**.

### Tìm kiếm đa tuyến (Top-K Routes)

Để đề xuất nhiều lộ trình thay thế, hệ thống chạy A\* nhiều lần với **hệ số phạt ngẫu nhiên** trên các node đã dùng, kết hợp kiểm tra **độ đa dạng tối thiểu** giữa các tuyến để tránh trùng lặp.

---

## 4. Tính năng nổi bật

### 🚗 Định tuyến Đa phương tiện (Multi-modal Routing)

| Phương tiện | Vận tốc | Ràng buộc đường đi |
|---|---|---|
| 🚶 Đi bộ | 5 km/h | Tất cả các loại đường |
| 🏍️ Xe máy | 25 km/h | Tất cả các loại đường |
| 🚗 Ô tô | 35 km/h | Chỉ đường ô tô (`primary`, `secondary`, `residential`...) |

**Tính năng tự động chia 3 chặng (Car + Alley Detection):**

Khi người dùng chọn phương tiện **Ô tô** nhưng điểm đi hoặc điểm đến nằm trong **ngõ nhỏ** (không có đường ô tô), hệ thống tự động phát hiện và chia lộ trình thành 3 chặng:

```
[Điểm xuất phát] ──🚶 Đi bộ──▶ [Đường lớn gần nhất]
                                        │
                               🚗 Đi ô tô
                                        │
                               [Đường lớn gần đích] ──🚶 Đi bộ──▶ [Điểm đến]
```

Mỗi chặng được vẽ với màu và kiểu đường riêng biệt trên bản đồ.

---

### 🚦 Mô phỏng Tắc đường (Dynamic Traffic Simulation)

Hàm `apply_mock_conditions(graph, traffic_level, rain_mm)` cập nhật trọng số đồ thị **trước mỗi lần tìm đường**:

Chi phí cạnh được điều chỉnh theo công thức:

$$\text{Cost}_{\text{new}} = \text{length} \times a$$

| Mức độ (`traffic_level`) | Hệ số phạt `a` |
|---|---|
| `Low` — Vắng | 1.2 |
| `Normal` — Bình thường | 1.5 |
| `High` — Đông đúc | 2.0 |

---

### 🌧️ Cảnh báo Ngập lụt (Flood Avoidance)

Dựa vào thuộc tính **số làn đường** (`lanes`) của mỗi cạnh để ước tính **công suất thoát nước**:

$$C = \text{lanes} \times 3\ (\text{m}) \times 15\ (\text{mm/h})$$

- Nếu `rain_mm > C`: cạnh bị đánh dấu **ngập** → **chặn hoàn toàn** với đi bộ và ô tô, tăng chi phí ×20 với xe máy.
- Người dùng điều chỉnh lượng mưa qua thanh trượt (0–100 mm) trên giao diện.

---

## 5. Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| **Backend** | Python 3.x, [OSMnx](https://osmnx.readthedocs.io/), [NetworkX](https://networkx.org/), [Flask](https://flask.palletsprojects.com/) |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **Bản đồ** | [Leaflet.js](https://leafletjs.com/) + OpenStreetMap tiles |
| **Dữ liệu** | File tĩnh `map_dong_da.graphml` (trích xuất từ OSM) |
| **Giao tiếp** | REST API (JSON) qua `fetch` |

---

## 6. Hướng dẫn cài đặt (Localhost)

### Yêu cầu

- Python **3.9+**
- Trình duyệt hiện đại (Chrome, Firefox, Edge)

### Bước 1 — Clone repository

```bash
git clone https://github.com/<your-username>/map_finding_path.git
cd map_finding_path
```

### Bước 2 — Tạo và kích hoạt môi trường ảo

```bash
# Tạo venv
python -m venv backend/venv

# Kích hoạt (Linux/macOS)
source backend/venv/bin/activate

# Kích hoạt (Windows)
backend\venv\Scripts\activate
```

### Bước 3 — Cài đặt dependencies

```bash
pip install -r backend/requirements.txt
```

### Bước 4 — Khởi động backend

```bash
cd backend
python app.py
```

Server sẽ chạy tại: **`http://localhost:5000`**

### Bước 5 — Mở giao diện

Mở file `frontend/index.html` trực tiếp trong trình duyệt, hoặc dùng Live Server (VS Code extension).

> **Lưu ý:** Đảm bảo file `backend/data/map_dong_da.graphml` tồn tại trước khi khởi động server.

---

<div align="center">

</div>
