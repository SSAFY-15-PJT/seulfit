const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json();
}

export function getMapSummary(params = {}) {
  const query = new URLSearchParams();
  if (params.lat) query.set("lat", params.lat);
  if (params.lng) query.set("lng", params.lng);
  if (params.radius) query.set("radius", params.radius);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/hyperlocal/map-summary/${suffix}`);
}

export function getWeatherCuration() {
  return request("/hyperlocal/weather-curation/");
}

export function parseReceiptImage(file) {
  const formData = new FormData();
  if (file) formData.append("image", file);
  return request("/hyperlocal/parse-image/", {
    method: "POST",
    body: formData,
  });
}

export function simulateCards(payload) {
  return request("/hyperlocal/simulate/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getPosts() {
  return request("/community/posts/");
}

export function getProfile() {
  return request("/users/profile/");
}
