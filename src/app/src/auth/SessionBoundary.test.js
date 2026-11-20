import React, { act } from "react";
import { createRoot } from "react-dom/client";
import SessionBoundary from "./SessionBoundary";
import { getTokenSession, subscribeSession } from "./session";

jest.mock("./session", () => ({
  getTokenSession: jest.fn(), subscribeSession: jest.fn(),
  invalidateSession: jest.fn(),
}));
jest.mock("@fluentui/react-components", () => ({
  Button: ({ children, ...props }) => <button {...props}>{children}</button>,
  Spinner: ({ label }) => <span>{label}</span>,
}));

let container, root, listener;
const session = { identity: "tenant:user", name: "User", roles: ["Reader"] };
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  subscribeSession.mockImplementation((fn) => { listener = fn; return () => {}; });
  getTokenSession.mockResolvedValue(session);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  jest.clearAllMocks();
});
const render = async () => {
  await act(async () => { root.render(<SessionBoundary><div>Private application</div></SessionBoundary>); });
};

test("mounts private content only after a valid token session", async () => {
  let resolve;
  getTokenSession.mockReturnValue(new Promise((done) => { resolve = done; }));
  await render();
  expect(container.textContent).not.toContain("Private application");
  await act(async () => { resolve(session); });
  expect(container.textContent).toContain("Private application");
});

test("missing roles hide private content even when a session exists", async () => {
  getTokenSession.mockResolvedValue({ ...session, roles: [] });
  await render();
  expect(container.textContent).toContain("Access denied");
  expect(container.textContent).not.toContain("Private application");
});

test("auth errors unmount private content and show sign-in/configuration guidance", async () => {
  await render();
  act(() => { listener(null, new Error("Sign-in session expired")); });
  expect(container.textContent).not.toContain("Private application");
  expect(container.textContent).toContain("Sign-in session expired");
  expect(container.textContent).toContain("EasyAuth");
});

test("forbidden errors remain visible even if a page swallows its API error", async () => {
  await render();
  act(() => { listener(session, new Error("Access denied")); });
  expect(container.textContent).toContain("Access denied");
  expect(container.textContent).toContain("Private application");
});
