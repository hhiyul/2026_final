import axios from "axios";
export const baseURL = (import.meta.env.VITE_API_BASE_URL || "").replace(
  /\/$/,
  "",
);
export const api = axios.create({ baseURL, withCredentials: true });
