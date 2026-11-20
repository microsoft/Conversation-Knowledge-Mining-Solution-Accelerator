const token = (oid = "user", nonce = "initial") => `header.${btoa(JSON.stringify({
  ver: "2.0", exp: Math.floor(Date.now() / 1000) + 3600, tid: "tenant",
  oid, aud: "backend-api", scp: "access_as_user", roles: ["Reader"], nonce,
})).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_")}.signature`;
const me = (oid, nonce) => ({ ok: true, json: async () => [{ provider_name: "aad", access_token: token(oid, nonce) }] });
const failed = (config, status) => Promise.reject({ config, response: { status } });
let api, client, auth;

beforeEach(() => {
  jest.resetModules();
  global.fetch = jest.fn().mockImplementation(async () => me());
  api = require("./client");
  client = api.default;
  auth = require("../auth/session");
  client.defaults.adapter = jest.fn(async (config) => ({ config, status: 200, data: {} }));
});
afterEach(() => { delete global.fetch; });

test("all data requests attach bearer access tokens without spoofed identity headers", async () => {
  localStorage.setItem("userId", "spoof");
  await api.getUploadedFiles();
  await api.getProcessingStatus();
  await api.uploadDocument(new File(["test"], "test.txt"));
  for (const [config] of client.defaults.adapter.mock.calls) {
    expect(config.headers.Authorization).toBe(`Bearer ${token()}`);
    expect(config.headers["X-Ms-Client-Principal-Id"]).toBeUndefined();
  }
});

test("missing EasyAuth cannot reach data APIs", async () => {
  fetch.mockResolvedValue({ ok: true, json: async () => [] });
  await expect(api.getUploadedFiles()).rejects.toThrow("Sign-in session expired");
  expect(client.defaults.adapter).not.toHaveBeenCalled();
});

test("401 refreshes and retries at most once", async () => {
  client.defaults.adapter.mockImplementation((config) => failed(config, 401));
  await expect(api.getUploadedFiles()).rejects.toThrow("Sign-in session expired");
  expect(client.defaults.adapter).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls.filter(([url]) => url === "/.auth/refresh")).toHaveLength(1);
  expect(auth.isCurrentSession("tenant:user")).toBe(false);
});

test("successful retry uses the refreshed access token", async () => {
  fetch.mockResolvedValueOnce(me()).mockResolvedValueOnce({ ok: true }).mockResolvedValueOnce(me("user", "refreshed"));
  client.defaults.adapter.mockImplementationOnce((config) => failed(config, 401));
  await expect(api.getUploadedFiles()).resolves.toHaveProperty("status", 200);
  expect(client.defaults.adapter).toHaveBeenCalledTimes(2);
  expect(client.defaults.adapter.mock.calls[1][0].headers.Authorization).toBe(`Bearer ${token("user", "refreshed")}`);
});

test("failed refresh cannot retry the data request", async () => {
  fetch.mockImplementation(async (url) => url === "/.auth/refresh" ? { ok: false } : me());
  client.defaults.adapter.mockImplementation((config) => failed(config, 401));
  await expect(api.getUploadedFiles()).rejects.toThrow("Sign-in session expired");
  expect(client.defaults.adapter).toHaveBeenCalledTimes(1);
});

test("403 surfaces a role error without refreshing or retrying", async () => {
  client.defaults.adapter.mockImplementation((config) => failed(config, 403));
  await expect(api.getUploadedFiles()).rejects.toThrow("Access denied");
  expect(client.defaults.adapter).toHaveBeenCalledTimes(1);
  expect(fetch).toHaveBeenCalledTimes(1);
});

test("rejects in-flight responses from a previous account", async () => {
  let resolve;
  client.defaults.adapter.mockImplementationOnce((config) => new Promise((done) => {
    resolve = () => done({ config, status: 200, data: { private: true } });
  }));
  const request = api.getUploadedFiles();
  while (!resolve) await Promise.resolve();
  fetch.mockResolvedValueOnce(me("other"));
  await auth.getTokenSession();
  resolve();
  await expect(request).rejects.toThrow("Account changed");
});

test("an old account's 401 cannot invalidate the new account or trigger refresh", async () => {
  let reject;
  client.defaults.adapter.mockImplementationOnce((config) => new Promise((resolve, fail) => {
    reject = () => fail({ config, response: { status: 401 } });
  }));
  const request = api.getUploadedFiles();
  while (!reject) await Promise.resolve();
  fetch.mockResolvedValueOnce(me("other"));
  await auth.getTokenSession();
  reject();
  await expect(request).rejects.toThrow("Account changed");
  expect(auth.isCurrentSession("tenant:other")).toBe(true);
  expect(fetch.mock.calls.filter(([url]) => url === "/.auth/refresh")).toHaveLength(0);
});

test("a session switch during refresh cannot replay a write under a different account", async () => {
  fetch.mockResolvedValueOnce(me()).mockResolvedValueOnce({ ok: true }).mockResolvedValueOnce(me("other"));
  client.defaults.adapter.mockImplementationOnce((config) => failed(config, 401));
  await expect(api.loadDefaultDataset()).rejects.toThrow("Account changed");
  expect(client.defaults.adapter).toHaveBeenCalledTimes(1);
});

test("chat identity is derived only by the backend", async () => {
  await api.saveChatHistory("chat", [], "title");
  await api.listChatSessions();
  await api.deleteChatSession("chat");
  const configs = client.defaults.adapter.mock.calls.map(([config]) => config);
  expect(JSON.parse(configs[0].data)).toEqual({ session_id: "chat", messages: [], title: "title" });
  expect(configs[1].params).toBeUndefined();
  expect(configs[2].params).toBeUndefined();
});
