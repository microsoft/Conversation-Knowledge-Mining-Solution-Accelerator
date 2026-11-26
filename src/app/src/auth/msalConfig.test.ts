import { beforeEach, expect, it, jest } from "@jest/globals";
import type { AccountInfo, AuthenticationResult } from "@azure/msal-browser";

jest.mock("@azure/msal-browser", () => {
  const mock = require("@jest/globals").jest;
  return {
    PublicClientApplication: mock.fn().mockImplementation(() => ({
      initialize: mock.fn(),
      handleRedirectPromise: mock.fn(),
      setActiveAccount: mock.fn(),
      getActiveAccount: mock.fn(),
      getAllAccounts: mock.fn().mockReturnValue([]),
      acquireTokenSilent: mock.fn(),
      acquireTokenRedirect: mock.fn(),
    })),
    InteractionRequiredAuthError: class extends Error {},
  };
});

let auth: typeof import("./msalConfig");
const account: AccountInfo = {
  homeAccountId: "home", localAccountId: "local", environment: "login.microsoftonline.com",
  tenantId: "tenant", username: "user@example.test", name: "Test User",
};
const result: AuthenticationResult = {
  authority: "https://login.microsoftonline.com/tenant",
  uniqueId: "local", tenantId: "tenant", scopes: ["api://runtime-client/access_as_user"],
  account, idToken: "id-token", idTokenClaims: {}, accessToken: "api-access-token",
  fromCache: true, expiresOn: new Date(Date.now() + 300000),
  tokenType: "Bearer", correlationId: "test",
};

beforeEach(() => {
  jest.resetModules();
  window._env_ = {
    APP_AZURE_AD_TENANT_ID: "runtime-tenant",
    APP_AZURE_AD_CLIENT_ID: "runtime-client",
  };
  auth = require("./msalConfig");
});

it("uses runtime configuration and restores the account returned after sign-in", async () => {
  jest.spyOn(auth.msalInstance, "handleRedirectPromise").mockResolvedValue(result);
  await auth.initializeAuthentication();
  expect(auth.msalConfig.auth.authority).toBe("https://login.microsoftonline.com/runtime-tenant");
  expect(auth.msalInstance.setActiveAccount).toHaveBeenCalledWith(account);
});

it("reports missing configuration rather than enabling anonymous mode", async () => {
  jest.resetModules();
  window._env_ = {};
  auth = require("./msalConfig");
  await expect(auth.initializeAuthentication()).rejects.toThrow("Configure the Microsoft Entra");
  expect(auth.msalInstance.initialize).not.toHaveBeenCalled();
});

it("does not acquire tokens without a signed-in account", async () => {
  await expect(auth.getAccessToken()).rejects.toThrow("Sign in");
  expect(auth.msalInstance.acquireTokenSilent).not.toHaveBeenCalled();
});

it("requests the API scope for the active account and returns its access token", async () => {
  jest.spyOn(auth.msalInstance, "getActiveAccount").mockReturnValue(account);
  jest.spyOn(auth.msalInstance, "acquireTokenSilent").mockResolvedValue(result);
  expect(await auth.getAccessToken()).toBe("api-access-token");
  expect(auth.msalInstance.acquireTokenSilent).toHaveBeenCalledWith({
    account, scopes: ["api://runtime-client/access_as_user"],
  });
});

it("requires interactive authentication when silent acquisition needs consent", async () => {
  const { InteractionRequiredAuthError } = require("@azure/msal-browser");
  jest.spyOn(auth.msalInstance, "getActiveAccount").mockReturnValue(account);
  jest.spyOn(auth.msalInstance, "acquireTokenSilent").mockRejectedValue(
    new InteractionRequiredAuthError("consent_required")
  );
  await expect(auth.getAccessToken()).rejects.toThrow("Sign-in is required");
  expect(auth.msalInstance.acquireTokenRedirect).toHaveBeenCalledWith({
    ...auth.loginRequest, account,
  });
});

it("surfaces token acquisition failures without substituting an identity", async () => {
  jest.spyOn(auth.msalInstance, "getActiveAccount").mockReturnValue(account);
  jest.spyOn(auth.msalInstance, "acquireTokenSilent").mockRejectedValue(new Error("Token service unavailable"));
  await expect(auth.getAccessToken()).rejects.toThrow("Token service unavailable");
  expect(auth.msalInstance.acquireTokenRedirect).not.toHaveBeenCalled();
});
