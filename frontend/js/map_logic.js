const map = L.map("map").setView([21.012, 105.824], 15);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

let startMarker = null;
let endMarker = null;
let routePolyline = null;
let jammedPoints = [];
let floodedPoints = [];
let obstacleMarkers = [];

const startText = document.getElementById("start-coords");
const endText = document.getElementById("end-coords");
const statusText = document.getElementById("status-text");
const distanceText = document.getElementById("distance-info");
const timeText = document.getElementById("time-info");

function toPoint(latlng) {
    return { lat: latlng.lat, lng: latlng.lng };
}

function pointToLatLng(point) {
    if (Array.isArray(point) && point.length >= 2) return [point[0], point[1]];
    if (point && typeof point === "object") return [point.lat, point.lng ?? point.lon];
    return null;
}

function updateStatus(message, className) {
    statusText.innerText = message;
    statusText.className = className;
}

function drawPath(pathData) {
    const latLngs = (pathData || [])
        .map(pointToLatLng)
        .filter((coord) => Array.isArray(coord) && Number.isFinite(coord[0]) && Number.isFinite(coord[1]));

    if (routePolyline) {
        map.removeLayer(routePolyline);
        routePolyline = null;
    }

    if (!latLngs.length) {
        updateStatus("Không có dữ liệu đường đi hợp lệ.", "error");
        return;
    }

    routePolyline = L.polyline(latLngs, { color: "red", weight: 5, opacity: 0.75 }).addTo(map);
    map.fitBounds(routePolyline.getBounds(), { padding: [20, 20] });
}

function buildRequestPayload() {
    const start = toPoint(startMarker.getLatLng());
    const end = toPoint(endMarker.getLatLng());

    return {
        start,
        end,
        vehicle: document.getElementById("vehicleType").value,
        obstacles: {
            jammed: jammedPoints,
            flooded: floodedPoints,
        },
        // Backward compatibility for old backend parser.
        jammed: jammedPoints,
        flooded: floodedPoints,
    };
}

function parseResponsePayload(response) {
    const data = response?.data || {};
    return {
        path: data.path || response.path || [],
        distanceM: data.distance_m ?? response.distance ?? 0,
        durationMin: data.duration_min ?? response.time_minutes ?? 0,
    };
}

async function findShortestPath() {
    if (!startMarker || !endMarker) return;

    updateStatus("Đang tính toán tuyến đường...", "loading");

    try {
        const response = await fetch("http://localhost:5000/api/find-path", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(buildRequestPayload()),
        });

        const data = await response.json();
        if (!response.ok || data.status !== "success") {
            const errorMessage = data?.message || "Không thể tìm đường.";
            updateStatus(`Lỗi: ${errorMessage}`, "error");
            return;
        }

        const parsed = parseResponsePayload(data);
        drawPath(parsed.path);
        distanceText.innerText = `${(parsed.distanceM / 1000).toFixed(2)} km`;
        timeText.innerText = `${parsed.durationMin.toFixed(1)} phút`;
        updateStatus("Tìm đường thành công.", "success");
    } catch (_error) {
        updateStatus("Lỗi kết nối backend.", "error");
    }
}

function triggerRouteRecalc() {
    if (startMarker && endMarker) {
        findShortestPath();
    }
}

function addObstaclePoint(type, latlng) {
    const point = toPoint(latlng);
    const markerColor = type === "jammed" ? "red" : "blue";
    const label = type === "jammed" ? "Tắc đường" : "Ngập lụt";

    if (type === "jammed") jammedPoints.push(point);
    else floodedPoints.push(point);

    const marker = L.circleMarker([point.lat, point.lng], {
        color: markerColor,
        radius: 8,
        weight: 2,
        fillOpacity: 0.6,
    })
        .addTo(map)
        .bindPopup(label);
    obstacleMarkers.push(marker);

    if (startMarker && endMarker) {
        findShortestPath();
    }
}

map.on("click", (event) => {
    const mode = document.getElementById("clickMode").value;
    const { lat, lng } = event.latlng;

    if (mode === "route") {
        if (!startMarker) {
            startMarker = L.marker([lat, lng]).addTo(map).bindPopup("Điểm xuất phát").openPopup();
            startText.innerText = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
            updateStatus("Đã chọn điểm đi.", "idle");
            return;
        }

        if (!endMarker) {
            endMarker = L.marker([lat, lng]).addTo(map).bindPopup("Điểm đến").openPopup();
            endText.innerText = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
            findShortestPath();
        }
        return;
    }

    if (mode === "jammed" || mode === "flooded") {
        addObstaclePoint(mode, event.latlng);
    }
});

function resetMap() {
    if (startMarker) map.removeLayer(startMarker);
    if (endMarker) map.removeLayer(endMarker);
    if (routePolyline) map.removeLayer(routePolyline);
    obstacleMarkers.forEach((marker) => map.removeLayer(marker));

    startMarker = null;
    endMarker = null;
    routePolyline = null;
    jammedPoints = [];
    floodedPoints = [];
    obstacleMarkers = [];

    startText.innerText = "Chưa chọn";
    endText.innerText = "Chưa chọn";
    distanceText.innerText = "0 km";
    timeText.innerText = "0 phút";
    updateStatus("Đang chờ...", "idle");
}

function drawDistrictBoundary() {
    fetch("https://nominatim.openstreetmap.org/search?q=Qu%E1%BA%ADn+%C4%90%E1%BB%91ng+%C4%90a,+H%C3%A0+N%E1%BB%99i,+Vi%E1%BB%87t+Nam&polygon_geojson=1&format=json")
        .then((res) => res.json())
        .then((data) => {
            if (!Array.isArray(data) || !data.length) return;
            L.geoJSON(data[0].geojson, {
                style: {
                    color: "#007bff",
                    weight: 3,
                    opacity: 0.6,
                    fillColor: "#007bff",
                    fillOpacity: 0.05,
                    interactive: false,
                },
            }).addTo(map);
        })
        .catch(() => {
            // Boundary overlay is optional; ignore fetch errors silently.
        });
}

drawDistrictBoundary();