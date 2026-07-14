import axios from "axios";

const api = axios.create({ baseURL: "/api" });

export const getRoutes = () => api.get("/data/routes").then((r) => r.data.routes);
export const getSummary = () => api.get("/data/summary").then((r) => r.data);
export const getHistory = (route_id, limit = 500) =>
  api.get("/data/history", { params: { route_id, limit } }).then((r) => r.data);
export const generateSynthetic = (days = 30) =>
  api.post("/data/generate-synthetic", null, { params: { days } }).then((r) => r.data);
export const uploadCsv = (file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/data/upload", form, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
};
export const getForecast = (route_id, horizon = "24h") =>
  api.get("/forecast", { params: { route_id, horizon } }).then((r) => r.data);
export const getAnomalies = (route_id) =>
  api.get("/anomalies", { params: { route_id } }).then((r) => r.data);
export const getRecommendations = (route_id) =>
  api.get("/optimize/recommendations", { params: { route_id } }).then((r) => r.data);
export const runSimulation = (payload) => api.post("/simulate", payload).then((r) => r.data);
export const getScenarios = () => api.get("/simulate/scenarios").then((r) => r.data.scenarios);

export default api;
