# Configure Microsoft Entra Authentication

All application APIs require authentication, including local deployments. Only
`GET /` and `GET /api/health` are anonymous health checks. Missing credentials
return HTTP 401; missing token-validation configuration never enables anonymous
access. Client-supplied `x-ms-client-principal-*` headers are not credentials.

## Automated deployment setup

`azd up` configures authentication automatically by running
`infra/scripts/post-provision/configure_auth.ps1` in two phases:

- **PreProvision:** selects the subscription configured in azd (or uses the current
  Azure CLI subscription), validates the tenant, creates or reuses a single-tenant
  registration, and saves `AZURE_SUBSCRIPTION_ID`, `AZURE_AD_TENANT_ID`, and
  `AZURE_AD_CLIENT_ID`. It configures v2 access tokens, the `access_as_user` scope,
  app roles, and Azure CLI scope preauthorization.
- **PostProvision:** adds the deployed frontend's **SPA** redirect URI and synchronizes
  the API's `AZURE_AD_*` settings and frontend's `APP_AZURE_AD_*` settings, then
  restarts both App Services. Existing redirects, roles, and permissions are preserved.

Azure CLI and azd must both be signed in to the deployment tenant. The caller needs
permission to create/manage Entra app registrations and service principals, plus
App Service configuration permissions. A tenant mismatch or permission failure
stops deployment. No client secret or automatic user role assignment is created.
Assign users/groups to `Reader`, `Contributor`, or `Admin` explicitly through the
enterprise application after setup; roleless users remain read-only.

To reuse an existing registration, set `AZURE_AD_CLIENT_ID` in the selected azd
environment before provisioning. You can also run either phase manually:

```powershell
.\infra\scripts\post-provision\configure_auth.ps1 -Phase PreProvision
.\infra\scripts\post-provision\configure_auth.ps1 -Phase PostProvision
```

For an already provisioned deployment missing its IDs, run **PostProvision** from
its selected azd environment. It creates/reuses the registration and updates the
deployed apps without provisioning infrastructure or loading/clearing data.
Optional parameters include `-ClientId`, `-TenantId`, `-SubscriptionId`,
`-ResourceGroupName`, `-FrontendAppName`, and `-BackendAppName`.

## Manual app registration

Use these steps as an alternative to automatic registration creation, for example
when an administrator must create the registration in advance. They are not a
separate requirement for the normal `azd up` flow. The deployment hooks still
configure the supplied registration and require permission to manage it.

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

The deployment hooks populate both IDs automatically. To use a manually created
registration instead, configure both IDs before provisioning:

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
Both `setup-data.ps1` and `seed-data.ps1` prefer a configured admin key and request
an Entra token only when no key is available.

For app-only access, assign an application app role and configure the `idtyp`
optional **access-token** claim on the API registration. App-only tokens must
identify themselves as `idtyp=app` and contain a recognized app role. ID tokens
are not accepted as API credentials.

App Service EasyAuth may be added as defense in depth, but it does not replace
backend access-token validation or allow unsigned identity headers.
