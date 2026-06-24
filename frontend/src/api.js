const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

function getCookie(name) {
  return document.cookie
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

function csrfHeaders(method = "GET") {
  if (!["POST", "PUT", "PATCH", "DELETE"].includes(method.toUpperCase())) {
    return {};
  }
  const token = getCookie("csrftoken");
  return token ? { "X-CSRFToken": decodeURIComponent(token) } : {};
}

async function refreshCsrfCookie() {
  await fetch(`${API_BASE}/auth/status/`, {
    credentials: "include",
  }).catch(() => null);
}

function shouldRefreshCsrf(response, data) {
  return response.status === 403 && String(data.detail || data.error || "").includes("CSRF");
}

async function request(path, options = {}, retryOnCsrf = true) {
  const method = options.method || "GET";
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...csrfHeaders(method),
      ...(options.headers || {}),
    },
    ...options,
    method,
  });
  const data = await response.json().catch(() => ({}));

  if (!response.ok && retryOnCsrf && shouldRefreshCsrf(response, data)) {
    await refreshCsrfCookie();
    return request(path, options, false);
  }

  if (!response.ok) {
    throw new Error(data.error || `API request failed: ${response.status}`);
  }

  return data;
}

function post(path, payload = {}) {
  return request(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function upload(path, formData, retryOnCsrf = true) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: csrfHeaders("POST"),
    body: formData,
  });
  const data = await response.json().catch(() => ({}));

  if (!response.ok && retryOnCsrf && shouldRefreshCsrf(response, data)) {
    await refreshCsrfCookie();
    return upload(path, formData, false);
  }

  if (!response.ok) {
    throw new Error(data.error || `API request failed: ${response.status}`);
  }

  return data;
}

function put(path, payload = {}) {
  return request(path, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

function remove(path) {
  return request(path, {
    method: "DELETE",
  });
}

export const api = {
  config: () =>
    Promise.resolve({
      kakaoMapApiKey: import.meta.env.VITE_KAKAO_JAVASCRIPT_KEY || "",
    }),
  health: () => request("/health/"),
  overview: () => request("/overview/"),
  places: (category = "전체") => request(`/places/?category=${encodeURIComponent(category)}`),
  recommendations: (spend) => request(`/recommendations/?spend=${spend}`),
  videos: (query = "", category = "전체") =>
    request(`/videos/?query=${encodeURIComponent(query)}&category=${encodeURIComponent(category)}`),
  community: (tab = "전체", search = "") =>
    request(`/community/?tab=${encodeURIComponent(tab)}&search=${encodeURIComponent(search)}`),
  profile: () => request("/users/profile/"),
  mapSummary: (params = {}) => {
    const query = new URLSearchParams();
    if (params.lat != null) query.set("lat", params.lat);
    if (params.lng != null) query.set("lng", params.lng);
    if (params.radius != null) query.set("radius", params.radius);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request(`/hyperlocal/map-summary/${suffix}`);
  },
  simulateCards: (payload) => post("/hyperlocal/simulate/", payload),
  parseImage: (file) => {
    const formData = new FormData();
    formData.append("image", file);
    return upload("/hyperlocal/parse-image/", formData);
  },
  saveUploadedReport: (payload) => post("/users/reports/", payload),
  cardEvent: (payload) => post("/hyperlocal/card-events/", payload),
  areaCardPopularity: (payload) => post("/hyperlocal/area-card-popularity/", payload),
  analyze: (payload) => post("/ai/analyze/", payload),
  authStatus: () => request("/auth/status/"),
  login: (payload) => post("/auth/login/", payload),
  register: (payload) => post("/auth/register/", payload),
  logout: () => post("/auth/logout/"),
  updateProfile: (payload) => post("/profile/update/", payload),
  communityPosts: () => request("/community/posts/"),
  createPost: (payload) => post("/community/posts/", payload),
  updatePost: (postId, payload) => put(`/community/posts/${postId}/`, payload),
  deletePost: (postId) => remove(`/community/posts/${postId}/`),
  createComment: (postId, payload) => post(`/community/posts/${postId}/comments/`, payload),
};
