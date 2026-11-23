# Configure Microsoft Entra Authentication

All application APIs require authentication, including local deployments. Only
`GET /` and `GET /api/health` are anonymous health checks. Missing credentials
return HTTP 401; missing token-validation configuration never enables anonymous
access. Client-supplied `x-ms-client-principal-*` headers are not credentials.

## App registration

1. Create a **single-tenant** Microsoft Entra app registration. Record its
   **Directory (tenant) ID** and **Application (client) ID**.
2. Under **Authentication**, add a **Single-page application** platform with the
   frontend origin as its redirect URI, for example
   `https://<frontend>.azurewebsites.net` or `http://localhost:3000`. Do not enable
   implicit grants or put a client secret in the browser.
3. Under **Expose an API**, set the Application ID URI to `api://<client-id>` and
   add the delegated scope `access_as_user`. Grant consent to this API permission
   according to your tenant's policy.
4. In the app manifest, set `api.requestedAccessTokenVersion` to `2`. The backend
   accepts only RS256 access tokens from the configured tenant's v2 issuer,
   addressed to this application's client ID.
5. Define app roles with values `Reader`, `Contributor`, and `Admin`. Assign users
   or groups through the enterprise application. Authenticated users without a
   recognized role have **Reader** access, never Contributor access.

Readers can query the knowledge base and manage their chat history. Contributors
can also ingest documents and manage data sources and pipelines. Admins can
additionally clear all documents or the vector index and reload pipelines.

## Deployment configuration

Before provisioning, configure both IDs:

```shell
azd env set AZURE_AD_TENANT_ID <tenant-id>
azd env set AZURE_AD_CLIENT_ID <client-id>
```

Both deployment flavors pass these settings to the API and the frontend's
runtime configuration. Production startup requires both IDs. The browser uses
MSAL authorization-code flow with PKCE and sends a Bearer access token with each
API request, including requests forwarded through the private-network proxy.
The API validates the signature, issuer, tenant, audience, lifetime, identity,
and delegated API scope before using any role or user ID.

For local API runs, set `AZURE_AD_TENANT_ID` and `AZURE_AD_CLIENT_ID` in the
environment or `.env`. For `npm start`, also set
`REACT_APP_AZURE_AD_TENANT_ID` and `REACT_APP_AZURE_AD_CLIENT_ID`. Docker Compose
passes the IDs to both containers. There is no sample-user authentication mode.

## Scripts and service identities

Provisioning scripts can use an Entra access token for this API, with an
appropriate app role, or the existing optional `ADMIN_API_KEY` credential.
The key grants Admin access: protect it as a secret, rotate it when necessary,
and never include it in frontend settings or source control. An unset key
disables key-based access; an incorrect key returns HTTP 401.

For app-only access, assign an application app role and configure the `idtyp`
optional **access-token** claim on the API registration. App-only tokens must
identify themselves as `idtyp=app` and contain a recognized app role. ID tokens
are not accepted as API credentials.

App Service EasyAuth may be added as defense in depth, but it does not replace
backend access-token validation or allow unsigned identity headers.
