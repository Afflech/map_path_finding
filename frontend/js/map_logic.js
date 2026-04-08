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
const TOP_K_ROUTES = 3;
const ANIMATION_SPEED_PRESETS = {
    fast: { intervalMs: 8, batchSize: 5 },
    normal: { intervalMs: 15, batchSize: 3 },
    slow: { intervalMs: 24, batchSize: 2 },
};
let currentRoutes = [];
let exploredNodeMarkers = [];
let exploredAnimationTimer = null;
let animationEnabled = true;
let animationSpeed = "normal";

const startText = document.getElementById("start-coords");
const endText = document.getElementById("end-coords");
const statusText = document.getElementById("status-text");
const distanceText = document.getElementById("distance-info");
const timeText = document.getElementById("time-info");
const routeSelector = document.getElementById("routeSelector");
const navigationStepsEl = document.getElementById("navigation-steps");
const animationToggleBtn = document.getElementById("animation-toggle-btn");
const animationSpeedSelect = document.getElementById("animationSpeed");

function toPoint(latlng) {
    return { lat: latlng.lat, lng: latlng.lng };
}

function pointToLatLng(point) {
    if (Array.isArray(point) && point.length >= 2) return [point[0], point[1]];
    if (point && typeof point === "object") return [point.lat, point.lng ?? point.lon];
    return null;
}

function formatDistanceMeters(distanceMeters) {
    if (!Number.isFinite(distanceMeters)) return "0m";
    if (distanceMeters >= 1000) return `${(distanceMeters / 1000).toFixed(1)}km`;
    return `${Math.round(distanceMeters)}m`;
}

function instructionToText(step) {
    const action = (step?.action || "straight").toLowerCase();
    const street = step?.street || "đường không tên";
    const distanceLabel = formatDistanceMeters(step?.distance_m || 0);
    if (action === "left") return `Rẽ trái vào ${street} - ${distanceLabel}`;
    if (action === "right") return `Rẽ phải vào ${street} - ${distanceLabel}`;
    return `Đi thẳng theo ${street} - ${distanceLabel}`;
}

function instructionIcon(action) {
    if (action === "left") return "⬅️";
    if (action === "right") return "➡️";
    return "⬆️";
}

function renderNavigationSteps(instructions) {
    if (!navigationStepsEl) return;
    if (!Array.isArray(instructions) || !instructions.length) {
        navigationStepsEl.innerHTML = '<p class="nav-placeholder">Chưa có chỉ dẫn điều hướng.</p>';
        return;
    }

    navigationStepsEl.innerHTML = instructions
        .map((step) => {
            const icon = instructionIcon(step.action);
            const text = instructionToText(step);
            return `<div class="navigation-step"><span class="navigation-icon">${icon}</span><span class="navigation-text">${text}</span></div>`;
        })
        .join("");
}

function updateStatus(message, className) {
    statusText.innerText = message;
    statusText.className = className;
}

function stopExplorationAnimation() {
    if (exploredAnimationTimer) {
        clearInterval(exploredAnimationTimer);
        exploredAnimationTimer = null;
    }
}

function clearExploredMarkers() {
    exploredNodeMarkers.forEach((marker) => map.removeLayer(marker));
    exploredNodeMarkers = [];
}

function animateExploredNodes(exploredNodes, onComplete) {
    stopExplorationAnimation();
    clearExploredMarkers();

    if (!animationEnabled || !Array.isArray(exploredNodes) || !exploredNodes.length) {
        onComplete();
        return;
    }

    let cursor = 0;
    const speed = ANIMATION_SPEED_PRESETS[animationSpeed] || ANIMATION_SPEED_PRESETS.normal;
    exploredAnimationTimer = setInterval(() => {
        for (let step = 0; step < speed.batchSize && cursor < exploredNodes.length; step += 1) {
            const point = pointToLatLng(exploredNodes[cursor]);
            cursor += 1;
            if (!point || !Number.isFinite(point[0]) || !Number.isFinite(point[1])) continue;

            const marker = L.circleMarker(point, {
                radius: 4,
                color: "#4c6c91",
                fillColor: "#7aa2d8",
                fillOpacity: 0.5,
                opacity: 0.7,
                weight: 1.5,
                interactive: false,
            }).addTo(map);
            exploredNodeMarkers.push(marker);
        }

        if (cursor >= exploredNodes.length) {
            stopExplorationAnimation();
            onComplete();
        }
    }, speed.intervalMs);
}

function renderRouteWithAnimation(route, fitBounds = true) {
    if (routePolyline) {
        map.removeLayer(routePolyline);
        routePolyline = null;
    }
    animateExploredNodes(route.explored_nodes || [], () => drawSelectedRoute(route, fitBounds));
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

function drawSelectedRoute(route, fitBounds = true) {
    if (!route) {
        updateStatus("Tuyến đã chọn không tồn tại.", "error");
        return;
    }

    const color = "#e53935";
    const latLngs = (route.path || [])
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

    routePolyline = L.polyline(latLngs, { color, weight: 7, opacity: 0.95 }).addTo(map);
    if (fitBounds) map.fitBounds(routePolyline.getBounds(), { padding: [20, 20] });
}

function syncRouteSelectorOptions(routeCount) {
    for (let i = 0; i < routeSelector.options.length; i += 1) {
        routeSelector.options[i].disabled = i >= routeCount;
    }
    if (Number(routeSelector.value) >= routeCount) {
        routeSelector.value = "0";
    }
}

function onRouteSelectionChange() {
    if (!currentRoutes.length) return;
    const selectedIndex = Number(routeSelector.value);
    const selectedRoute = currentRoutes[selectedIndex] || currentRoutes[0];
    renderRouteWithAnimation(selectedRoute, false);
    distanceText.innerText = `${(selectedRoute.distance_m / 1000).toFixed(2)} km`;
    timeText.innerText = `${selectedRoute.duration_min.toFixed(1)} phút`;
    renderNavigationSteps(selectedRoute.instructions || []);
    updateStatus(`Đang hiển thị tuyến ${selectedIndex + 1}.`, "success");
}

function toggleAnimation() {
    animationEnabled = !animationEnabled;
    animationToggleBtn.innerText = `Animation: ${animationEnabled ? "Bật" : "Tắt"}`;
    animationToggleBtn.classList.toggle("off", !animationEnabled);

    if (!animationEnabled) {
        stopExplorationAnimation();
        clearExploredMarkers();
        if (currentRoutes.length) {
            const selectedIndex = Number(routeSelector.value);
            const selectedRoute = currentRoutes[selectedIndex] || currentRoutes[0];
            drawSelectedRoute(selectedRoute, false);
        }
    }
}

function updateAnimationSpeed() {
    const selected = animationSpeedSelect?.value || "normal";
    if (!ANIMATION_SPEED_PRESETS[selected]) {
        animationSpeed = "normal";
        if (animationSpeedSelect) animationSpeedSelect.value = "normal";
        return;
    }
    animationSpeed = selected;
}

function buildRequestPayload() {
    const start = toPoint(startMarker.getLatLng());
    const end = toPoint(endMarker.getLatLng());

    return {
        start,
        end,
        vehicle: document.getElementById("vehicleType").value,
        top_k: TOP_K_ROUTES,
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
        exploredNodes: data.explored_nodes || response.explored_nodes || [],
        distanceM: data.distance_m ?? response.distance ?? 0,
        durationMin: data.duration_min ?? response.time_minutes ?? 0,
        routes: data.routes || response.routes || [],
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
        currentRoutes = parsed.routes.length
            ? parsed.routes
            : [
                  {
                      path: parsed.path,
                      explored_nodes: parsed.exploredNodes,
                      distance_m: parsed.distanceM,
                      duration_min: parsed.durationMin,
                      instructions: [],
                      rank: 1,
                  },
              ];

        syncRouteSelectorOptions(currentRoutes.length);
        onRouteSelectionChange();
        updateStatus(`Tìm đường thành công (${currentRoutes.length} tuyến).`, "success");
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
    stopExplorationAnimation();
    clearExploredMarkers();
    obstacleMarkers.forEach((marker) => map.removeLayer(marker));

    startMarker = null;
    endMarker = null;
    routePolyline = null;
    currentRoutes = [];
    jammedPoints = [];
    floodedPoints = [];
    obstacleMarkers = [];
    routeSelector.value = "0";
    syncRouteSelectorOptions(0);

    startText.innerText = "Chưa chọn";
    endText.innerText = "Chưa chọn";
    distanceText.innerText = "0 km";
    timeText.innerText = "0 phút";
    renderNavigationSteps([]);
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