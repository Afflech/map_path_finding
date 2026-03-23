const map = L.map('map').setView([21.012, 105.824], 15);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

let startMarker = null;
let endMarker = null;
let routePolyline = null;

// Lưu danh sách tọa độ ngập/tắc
let jammedPoints = [];
let floodedPoints = [];
let obstacleMarkers = []; // Lưu marker để xóa sau

const startText = document.getElementById('start-coords');
const endText = document.getElementById('end-coords');
const statusText = document.getElementById('status-text');

map.on('click', function(e) {
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;
    const mode = document.getElementById('clickMode').value;

    if (mode === 'route') {
        if (!startMarker) {
            startMarker = L.marker([lat, lng]).addTo(map).bindPopup("Điểm xuất phát").openPopup();
            startText.innerText = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
            updateStatus("Đã chọn điểm đi...", "idle");
        } else if (!endMarker) {
            endMarker = L.marker([lat, lng]).addTo(map).bindPopup("Điểm đến").openPopup();
            endText.innerText = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
            findShortestPath();
        }
    } else if (mode === 'jammed') {
        jammedPoints.push([lat, lng]);
        const m = L.circleMarker([lat, lng], {color: 'red', radius: 10}).addTo(map).bindPopup("Tắc đường");
        obstacleMarkers.push(m);
        if(startMarker && endMarker) findShortestPath(); // Có chướng ngại vật thì vẽ lại đường luôn
    } else if (mode === 'flooded') {
        floodedPoints.push([lat, lng]);
        const m = L.circleMarker([lat, lng], {color: 'blue', radius: 10}).addTo(map).bindPopup("Ngập lụt");
        obstacleMarkers.push(m);
        if(startMarker && endMarker) findShortestPath();
    }
});

function triggerRouteRecalc() {
    if (startMarker && endMarker) findShortestPath();
}

function findShortestPath() {
    if (!startMarker || !endMarker) return;
    updateStatus("Đang tính toán A*...", "loading");

    const requestData = {
        start: [startMarker.getLatLng().lat, startMarker.getLatLng().lng],
        end: [endMarker.getLatLng().lat, endMarker.getLatLng().lng],
        vehicle: document.getElementById('vehicleType').value,
        jammed: jammedPoints,
        flooded: floodedPoints
    };

    fetch('http://localhost:5000/api/find-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            drawPath(data.path);
            updateStatus("Tìm đường thành công!", "success");
            document.getElementById('distance-info').innerText = (data.distance / 1000).toFixed(2) + " km";
            document.getElementById('time-info').innerText = data.time_minutes.toFixed(1) + " phút";
        } else {
            updateStatus(`Lỗi: ${data.message}`, "error");
        }
    })
    .catch(err => {
        updateStatus("Lỗi kết nối Backend", "error");
    });
}

function drawPath(pathCoords) {
    if (routePolyline) map.removeLayer(routePolyline);
    routePolyline = L.polyline(pathCoords, { color: 'red', weight: 5, opacity: 0.7 }).addTo(map);
}

function resetMap() {
    if (startMarker) map.removeLayer(startMarker);
    if (endMarker) map.removeLayer(endMarker);
    if (routePolyline) map.removeLayer(routePolyline);
    obstacleMarkers.forEach(m => map.removeLayer(m));
    
    startMarker = null; endMarker = null; routePolyline = null;
    jammedPoints = []; floodedPoints = []; obstacleMarkers = [];

    startText.innerText = "Chưa chọn";
    endText.innerText = "Chưa chọn";
    document.getElementById('distance-info').innerText = "0 km";
    document.getElementById('time-info').innerText = "0 phút";
    updateStatus("Đang chờ...", "idle");
}

function updateStatus(message, className) {
    statusText.innerText = message;
    statusText.className = className;
}

function drawDistrictBoundary() {
    fetch("https://nominatim.openstreetmap.org/search?q=Quận+Đống+Đa,+Hà+Nội,+Việt+Nam&polygon_geojson=1&format=json")
        .then(res => res.json())
        .then(data => {
            if (data.length > 0) {
                L.geoJSON(data[0].geojson, {
                    style: { color: "#007bff", weight: 3, opacity: 0.6, fillColor: "#007bff", fillOpacity: 0.05, interactive: false}
                }).addTo(map);
            }
        });
}
drawDistrictBoundary();