import { beforeEach, expect, it, jest } from "@jest/globals";
import apiClient from "./client";
import { getAccessToken } from "../auth/msalConfig";

jest.mock("../auth/msalConfig", () => ({
  getAccessToken: require("@jest/globals").jest.fn(),
}));

beforeEach(() => {
  jest.mocked(getAccessToken).mockReset();
});

it("sends an access token instead of a client-controlled identity header", async () => {
  localStorage.setItem("userId", "forged-admin");
  jest.mocked(getAccessToken).mockResolvedValue("validated-access-token");
  const response = await apiClient.get("/auth/me", {
    adapter: async (config) => ({
      config, data: config.headers, status: 200, statusText: "OK", headers: {},
    }),
  });
  expect(response.data.Authorization).toBe("Bearer validated-access-token");
  expect(response.data["X-Ms-Client-Principal-Id"]).toBeUndefined();
  localStorage.removeItem("userId");
});

it("does not send an API request when token acquisition fails", async () => {
  jest.mocked(getAccessToken).mockRejectedValue(new Error("Sign in required"));
  const adapter = jest.fn(async () => { throw new Error("Unexpected HTTP request"); });
  await expect(apiClient.get("/auth/me", { adapter })).rejects.toThrow("Sign in required");
  expect(adapter).not.toHaveBeenCalled();
});

it("acquires a fresh token for each request instead of caching an identity", async () => {
  jest.mocked(getAccessToken).mockResolvedValueOnce("first-token").mockResolvedValueOnce("next-token");
  const adapter = async (config: import("axios").InternalAxiosRequestConfig) => ({
    config, data: config.headers.Authorization, status: 200, statusText: "OK", headers: {},
  });
  expect((await apiClient.get("/auth/me", { adapter })).data).toBe("Bearer first-token");
  expect((await apiClient.get("/auth/me", { adapter })).data).toBe("Bearer next-token");
});
