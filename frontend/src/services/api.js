import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 120000,
  withCredentials: true
});

api.interceptors.request.use((config) => {
  const csrf = document.cookie.split("; ").find((item) => item.startsWith("csrftoken="))?.split("=")[1];
  if (csrf) config.headers["X-CSRFToken"] = decodeURIComponent(csrf);
  return config;
});

export async function getCurrentUser() {
  const response = await api.get("/auth/me/");
  return response.data;
}

export async function initializeSession() {
  await api.get("/auth/csrf/");
  return getCurrentUser();
}

export async function signOut() {
  const response = await api.post("/auth/logout/");
  return response.data;
}

export async function submitVideo(video, query = "") {
  const form = new FormData();
  form.append("video", video);
  if (query?.trim()) form.append("query", query.trim());
  const response = await api.post("/search/", form);
  return response.data;
}
