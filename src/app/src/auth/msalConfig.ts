import { Configuration, LogLevel } from "@azure/msal-browser";

const TENANT_ID = process.env.REACT_APP_AZURE_AD_TENANT_ID || "";
const CLIENT_ID = process.env.REACT_APP_AZURE_AD_CLIENT_ID || "";

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
