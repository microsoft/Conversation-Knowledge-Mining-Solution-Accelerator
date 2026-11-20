const token = (claims = {}) => [
  btoa(JSON.stringify({ alg: "RS256" })),
  btoa(JSON.stringify({
    ver: "2.0", exp: Math.floor(Date.now() / 1000) + 3600,
    tid: "tenant", oid: "user", aud: "backend-api", scp: "access_as_user",
    roles: ["Reader"], ...claims,
  })),
  "signature",
].map((part) => part.replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_")).join(".");

const me = (accessToken = token(), extra = {}) => [{
  provider_name: "aad", access_token: accessToken,
  user_claims: [{ typ: "name", val: "A User" }], ...extra,
}];
const response = (data, ok = true) => ({ ok, json: async () => data });
let auth;

beforeEach(() => {
  jest.resetModules();
  auth = require("./session");
  sessionStorage.clear();
  localStorage.clear();
  global.fetch = jest.fn();
});

afterEach(() => { delete global.fetch; });

test("uses only the access token and keeps it out of browser storage", async () => {
  const accessToken = token();
  fetch.mockResolvedValue(response(me(accessToken, { id_token: "do-not-use" })));
  const listener = jest.fn();
  auth.subscribeSession(listener);
  const session = await auth.getTokenSession();
  expect(session.token).toBe(accessToken);
  expect(session.identity).toBe("tenant:user");
  expect(listener.mock.calls[0][0]).not.toHaveProperty("token");
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
  expect(fetch).toHaveBeenCalledWith("/.auth/me", expect.objectContaining({ cache: "no-store", redirect: "error" }));
});

test.each([
  [], {}, [{ provider_name: "aad", id_token: token() }],
  me("not-a-token"), me(token({ scp: undefined })),
  me(token({ ver: "1.0" })), me(token({ exp: "later" })),
  me(token({ oid: "" })), me(token({ tid: null })),
  [...me(), ...me()],
])("rejects malformed or missing API access tokens %#", async (data) => {
  fetch.mockResolvedValue(response(data));
  await expect(auth.getTokenSession()).rejects.toThrow("Sign-in session expired");
  expect(fetch).toHaveBeenCalledTimes(1);
});

test("refreshes near expiry once and reads a new access token", async () => {
  const fresh = token();
  fetch.mockResolvedValueOnce(response(me(token({ exp: Math.floor(Date.now() / 1000) + 10 }))))
    .mockResolvedValueOnce(response(null))
    .mockResolvedValueOnce(response(me(fresh)));
  expect((await auth.getTokenSession()).token).toBe(fresh);
  expect(fetch.mock.calls.map(([url]) => url)).toEqual(["/.auth/me", "/.auth/refresh", "/.auth/me"]);
});

test("does not loop when refresh still returns an expired token", async () => {
  const expired = me(token({ exp: Math.floor(Date.now() / 1000) - 10 }));
  fetch.mockResolvedValueOnce(response(expired)).mockResolvedValueOnce(response(null)).mockResolvedValueOnce(response(expired));
  await expect(auth.getTokenSession()).rejects.toThrow("Sign-in session expired");
  expect(fetch).toHaveBeenCalledTimes(3);
});

test("clears every user cache on initial load, account change and invalidation", async () => {
  const seed = () => {
    ["km_home_data", "km_explore_data", "km_insights", "km_headline", "km_chat", "km_explore_chat", "km_explore_session"]
      .forEach((key) => sessionStorage.setItem(key, "old"));
    localStorage.setItem("userId", "spoof");
  };
  seed();
  fetch.mockResolvedValueOnce(response(me())).mockResolvedValueOnce(response(me(token({ oid: "another" }))));
  await auth.getTokenSession();
  expect(sessionStorage.length).toBe(0);
  expect(localStorage.length).toBe(0);
  seed();
  await auth.getTokenSession();
  expect(sessionStorage.length).toBe(0);
  seed();
  auth.invalidateSession();
  expect(sessionStorage.length).toBe(0);
  expect(auth.isCurrentSession("tenant:another")).toBe(false);
});

test("coalesces concurrent session requests and fails closed on network errors", async () => {
  fetch.mockResolvedValueOnce(response(me()));
  await Promise.all([auth.getTokenSession(), auth.getTokenSession()]);
  expect(fetch).toHaveBeenCalledTimes(1);
  fetch.mockRejectedValueOnce(new Error("network"));
  await expect(auth.getTokenSession()).rejects.toThrow("Sign-in session expired");
  expect(auth.isCurrentSession("tenant:user")).toBe(false);
});
