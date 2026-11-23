import {
  Configuration,
  InteractionRequiredAuthError,
  PublicClientApplication,
} from "@azure/msal-browser";

declare global {
  interface Window {
    _env_?: {
      APP_API_BASE_URL?: string;
      APP_AZURE_AD_TENANT_ID?: string;
      APP_AZURE_AD_CLIENT_ID?: string;
    };
  }
}

function configuredValue(runtime: string | undefined, buildTime: string | undefined): string {
  return runtime && !runtime.startsWith("$") ? runtime : buildTime || "";
}

const TENANT_ID = configuredValue(
  window._env_?.APP_AZURE_AD_TENANT_ID, process.env.REACT_APP_AZURE_AD_TENANT_ID
);
const CLIENT_ID = configuredValue(
  window._env_?.APP_AZURE_AD_CLIENT_ID, process.env.REACT_APP_AZURE_AD_CLIENT_ID
);

export const msalConfig: Configuration = {
  auth: {
    clientId: CLIENT_ID,
    authority: `https://login.microsoftonline.com/${TENANT_ID}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
};

export const loginRequest = {
  scopes: [`api://${CLIENT_ID}/access_as_user`],
};

export const msalInstance = new PublicClientApplication(msalConfig);

export async function initializeAuthentication(): Promise<void> {
  if (!TENANT_ID || !CLIENT_ID) {
    throw new Error("Configure the Microsoft Entra tenant and client IDs before signing in.");
  }
  await msalInstance.initialize();
  const result = await msalInstance.handleRedirectPromise();
  msalInstance.setActiveAccount(
    result?.account || msalInstance.getActiveAccount() || msalInstance.getAllAccounts()[0] || null
  );
}

export async function getAccessToken(): Promise<string> {
  const account = msalInstance.getActiveAccount();
  if (!account) {
    throw new Error("Sign in to access the knowledge base.");
  }
  try {
    const result = await msalInstance.acquireTokenSilent({ ...loginRequest, account });
    return result.accessToken;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      await msalInstance.acquireTokenRedirect({ ...loginRequest, account });
      throw new Error("Sign-in is required to continue.");
    }
    throw error;
  }
}
