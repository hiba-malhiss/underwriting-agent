import axios, { AxiosError } from "axios";

export const http = axios.create();

// FastAPI errors are {"detail": "..."}: reject with the detail so callers can show it as is
http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: unknown }>) => {
    const detail = error.response?.data?.detail;
    return Promise.reject(new Error(typeof detail === "string" ? detail : error.message));
  },
);
