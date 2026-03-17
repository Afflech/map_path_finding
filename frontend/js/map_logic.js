// 1. Khởi tạo bản đồ Leaflet
// Tọa độ [21.012, 105.824] là trung tâm khu vực Đống Đa, mức zoom 15
const map = L.map('map').setView([21.012, 105.824], 15);

// 2. Thêm lớp bản đồ từ OpenStreetMap
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// Biến lưu trữ trạng thái
let startMarker = null;
let endMarker = null;
let routePolyline = null;

// Tham chiếu đến các phần tử HTML để cập nhật giao diện
const startText = document.getElementById('start-coords');
const endText = document.getElementById('end-coords');
const statusText = document.getElementById('status-text');

// 3. Xử lý sự kiện click chuột trên bản đồ
map.on('click', function(e) {
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;

    // Nếu chưa có điểm bắt đầu -> Đặt điểm bắt đầu
    if (!startMarker) {
        startMarker = L.marker([lat, lng]).addTo(map).bindPopup("Điểm xuất phát").openPopup();
        startText.innerText = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        updateStatus("Đã chọn điểm đi, vui lòng chọn điểm đến...", "idle");
    } 
    // Nếu đã có điểm đi, nhưng chưa có điểm đến -> Đặt điểm đến và gọi API
    else if (!endMarker) {
        endMarker = L.marker([lat, lng]).addTo(map).bindPopup("Điểm đến").openPopup();
        endText.innerText = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        
        // Gọi API lên Flask Backend
        findShortestPath(startMarker.getLatLng(), endMarker.getLatLng());
    }
});

// 4. Hàm gọi API Backend (Fetch API)
function findShortestPath(start, end) {
    updateStatus("Đang tính toán thuật toán A*...", "loading");

    const requestData = {
        start: [start.lat, start.lng],
        end: [end.lat, end.lng]
    };

    // Gọi tới cổng 5000 của Flask
    fetch('http://localhost:5000/api/find-path', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            drawPath(data.path);
            updateStatus("Tìm đường thành công!", "success");
            const distanceKm = (data.distance / 1000).toFixed(2); 
            document.getElementById('distance-info').innerText = distanceKm + " km";
        } else {
            updateStatus(`Lỗi: ${data.message}`, "error");
        }
    })
    .catch(error => {
        console.error("Lỗi kết nối Backend:", error);
        updateStatus("Không thể kết nối đến máy chủ Backend.", "error");
    });
}

// 5. Hàm vẽ đường đi (Polyline) lên bản đồ
function drawPath(pathCoords) {
    // Xóa đường cũ nếu có
    if (routePolyline) {
        map.removeLayer(routePolyline);
    }

    // Vẽ đường mới màu đỏ, nét đậm
    routePolyline = L.polyline(pathCoords, {
        color: 'red', 
        weight: 5,
        opacity: 0.7
    }).addTo(map);

    // Tự động zoom bản đồ để hiển thị trọn vẹn đường đi
    map.fitBounds(routePolyline.getBounds());
}

// 6. Các hàm hỗ trợ giao diện
function resetMap() {
    if (startMarker) map.removeLayer(startMarker);
    if (endMarker) map.removeLayer(endMarker);
    if (routePolyline) map.removeLayer(routePolyline);
    
    startMarker = null;
    endMarker = null;
    routePolyline = null;

    startText.innerText = "Chưa chọn";
    endText.innerText = "Chưa chọn";
    updateStatus("Đang chờ...", "idle");
    
    // Đưa camera về lại trung tâm Đống Đa
    map.setView([21.012, 105.824], 15);
    document.getElementById('distance-info').innerText = "0 km";
}

function updateStatus(message, className) {
    statusText.innerText = message;
    statusText.className = className;
}

// ==========================================
// TÍNH NĂNG: VẼ RẠNH GIỚI QUẬN ĐỐNG ĐA
// ==========================================
function drawDistrictBoundary() {
    // API lấy dữ liệu GeoJSON ranh giới của Quận Đống Đa
    const nominatimUrl = "https://nominatim.openstreetmap.org/search?q=Quận+Đống+Đa,+Hà+Nội,+Việt+Nam&polygon_geojson=1&format=json";

    fetch(nominatimUrl)
        .then(response => response.json())
        .then(data => {
            if (data && data.length > 0) {
                // Lấy tọa độ ranh giới từ kết quả đầu tiên
                const boundaryGeoJSON = data[0].geojson;
                
                // Vẽ lên bản đồ bằng Leaflet
                L.geoJSON(boundaryGeoJSON, {
                    style: {
                        color: "#007bff",       // Màu đường viền (Xanh dương)
                        weight: 3,              // Độ dày đường viền
                        opacity: 0.6,           // Độ đậm nhạt của viền
                        fillColor: "#007bff",   // Màu nền bên trong
                        fillOpacity: 0.05       // Nền trong suốt (rất nhạt để không che đường)
                    }
                }).addTo(map);
            }
        })
        .catch(error => {
            console.error("Lỗi khi tải ranh giới quận:", error);
        });
}

// Gọi hàm này ngay khi file JS được tải xong
drawDistrictBoundary();