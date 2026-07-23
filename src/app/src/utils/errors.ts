import axios from "axios";

export function getApiErrorMessage(error: unknown, fallback = "Request failed"): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    const detail = data?.detail;

    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }

    if (typeof data?.error === "string" && data.error.trim()) {
      return data.error;
    }

    if (typeof error.message === "string" && error.message.trim()) {
      return error.message;
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallback;
}
