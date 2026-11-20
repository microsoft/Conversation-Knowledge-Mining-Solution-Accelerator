# Authentication and role assignments (required)

The backend validates **Microsoft Entra v2 JWT access tokens**, including signature,
tenant issuer, lifetime and audience. This applies equally to direct backend calls
and calls through the frontend `/api` reverse proxy. EasyAuth protects the frontend
sign-in experience; it does not replace backend JWT validation. Identity/role headers
such as `X-User-*` and `X-MS-CLIENT-PRINCIPAL` are not credentials.

All business APIs require an explicitly assigned `Reader`, `Contributor`, or `Admin`
application role. There is no anonymous/sample user fallback. Only minimal `GET /`
and `GET /api/health` probes are public; `/api/health/details` requires Reader access.

## 1. Register the backend API

Use **two separate single-tenant app registrations** in the same Entra tenant:
one for the backend API (resource/audience), another for frontend EasyAuth (web client).
An administrator with app-registration and enterprise-app assignment permissions is
required. Azure subscription RBAC does **not** grant application roles.

For the **backend API registration**:

1. Copy its **Application (client) ID** to `AZURE_AD_CLIENT_ID` and the directory
   **Tenant ID** to `AZURE_AD_TENANT_ID`. Both are GUIDs, not an object ID, URL,
   frontend client ID, or managed identity client ID.
2. In the manifest set `api.requestedAccessTokenVersion` to `2`. For example:
   ```json
   { "api": { "requestedAccessTokenVersion": 2 } }
   ```
   Merge with the existing manifest; do not overwrite existing scopes.
3. Under **Expose an API**, set Application ID URI to `api://<backend-client-id>`.
   Add an enabled delegated scope named **`access_as_user`** (admin consent is
   recommended). Its full name is `api://<backend-client-id>/access_as_user`.
4. Under **App roles**, create enabled roles with the exact **values**
   `Reader`, `Contributor`, and `Admin` (case-sensitive), each with a unique GUID
   and **Allowed member types: Users/Groups and Applications**. Use least privilege:
   Reader for reads, Contributor for permitted writes, Admin for administrative
   operations such as deployment data setup. Display names alone are not role values.
5. Under **Token configuration → Add optional claim → Access**, add **`idtyp`**.
   The manifest equivalent (merge with any existing optional claims) is:
   ```json
   {
     "optionalClaims": {
       "accessToken": [
         { "name": "idtyp", "source": null, "essential": false, "additionalProperties": [] }
       ]
     }
   }
   ```
   This is required for workload/app-only tokens: the backend requires `idtyp=app`.
6. Under **Enterprise applications → backend API → Users and groups**, assign
   each authorized user/group an appropriate application role. Assign the deployment
   operator **Admin** before post-provision data setup. Consent to a delegated scope
   alone is insufficient: delegated users also need an app-role assignment.

The API requires `ver=2.0`, matching `tid`, `oid`, `exp`, `nbf`, and `iat`.
Delegated tokens require `scp` containing `access_as_user` **and** a recognized
`roles` value. App-only tokens require `idtyp=app` **and** an assigned role.
For v2 tokens, `aud` is the backend **client GUID**, not `api://<guid>`.
An ID token (whose audience is the frontend client) or Graph access token is not a
backend credential. Do not copy tokens to public JWT-decoding websites.

## 2. Register and configure frontend EasyAuth

For the **frontend registration**:

1. Add a **Web** redirect URI:
   `https://<frontend-app>.azurewebsites.net/.auth/login/aad/callback`.
2. Add **delegated API permission** to the backend's `access_as_user` scope.
   Grant tenant administrator consent. Microsoft Graph `User.Read` alone is not enough.
3. Create a client secret; keep its **value**, not its secret ID, in protected
   deployment input. Never commit it, display it in logs, or put it in browser config.
4. Configure the frontend App Service's Microsoft identity provider with:
   - frontend registration client ID (not the backend ID);
   - issuer `https://login.microsoftonline.com/<tenant-id>/v2.0`;
   - frontend client secret in app setting `FRONTEND_AUTH_CLIENT_SECRET`, referenced
     by `registration.clientSecretSettingName`;
   - `platform.enabled=true`, `globalValidation.requireAuthentication=true`,
     `unauthenticatedClientAction=RedirectToLoginPage`, provider `azureactivedirectory`;
   - **token store enabled**: `login.tokenStore.enabled=true`;
   - `identityProviders.azureActiveDirectory.login.loginParameters`:
     ```json
     ["scope=openid profile email offline_access api://<backend-client-id>/access_as_user"]
     ```

The optional IaC inputs `frontendClientId` and secure `frontendClientSecret` configure
these settings in **both Bicep and AVM/WAF**. Provide both inputs together. If omitted,
configure EasyAuth manually using the exact contract above **before using the UI**;
the backend remains protected, but a working UI login is not provisioned automatically.
Keep that choice consistent on redeploy: app settings are replaced by IaC. Reapply
manual provider secrets after redeploy, or supply both optional inputs to let IaC
manage the complete provider configuration. Rotate expiring secrets.

After changing scopes or role assignments, sign out and sign in again to obtain a new
token (old cookies/tokens retain old claims). In an authenticated browser, `/.auth/me`
must contain the Entra provider's **`access_token` for the backend**, not only
`id_token` or user claims. The frontend keeps the access token in memory and sends
`Authorization: Bearer <access_token>` to the API. It calls `/.auth/refresh` near expiry
or once after a 401, then reloads `/.auth/me`; if refresh fails it requires sign-in.
`offline_access`, token storage, valid consent, and tenant session policies govern
refresh availability. The UI does not accept a browser admin key or fabricated identity.

For direct backend routing, allow only the deployed frontend origin in backend CORS
(the deployment supplies `APP_FRONTEND_HOSTNAME`) and permit `Authorization`.
For private/WAF routing, nginx forwards `/api` to the backend with the same bearer
header. Network isolation, CORS, or EasyAuth headers never bypass JWT validation.

## 3. Required deployment inputs

Before **any** deployment flavor:

```powershell
azd env set AZURE_AD_TENANT_ID <tenant-guid>
azd env set AZURE_AD_CLIENT_ID <backend-api-client-guid>
# Optional IaC-managed frontend EasyAuth:
azd env set FRONTEND_AUTH_CLIENT_ID <frontend-web-client-guid>
# Set FRONTEND_AUTH_CLIENT_SECRET using protected deployment input, not a literal
# secret in checked-in scripts or shared shell history.
azd up
```

The default and WAF parameter files map these inputs through the root template to
both infrastructure flavors. Direct ARM/Bicep deployments must supply
`azureAdTenantId` and `azureAdClientId`; neither has a default and both reject empty
values. The azd pre-provision hook also validates GUID syntax. CI/integration
deployments must set the same real tenant/backend API IDs and assign their calling
identity application roles; empty/dummy pipeline defaults are not an authentication
configuration. If the pipeline uses frontend automation, supply its frontend ID and
secret through protected pipeline inputs as well.

Production authentication configuration is mandatory independently of
`STARTUP_STRICT_IN_PROD`. An `ADMIN_API_KEY` in production is a startup error.
No key is generated or passed to Azure App Services by this deployment.

## 4. Local API and post-provision commands

### Delegated user

Authorize the Azure CLI public client application
`04b07795-8ddb-461a-bbee-02f9e1bf7b46` for the backend scope (Expose an API →
Authorized client applications), subject to your tenant's consent policy.
The signed-in user still needs a backend app role. Run locally in PowerShell:

```powershell
$env:AZURE_AD_TENANT_ID = "<tenant-guid>"
$env:AZURE_AD_CLIENT_ID = "<backend-api-client-guid>"
az login --tenant $env:AZURE_AD_TENANT_ID --scope "api://$($env:AZURE_AD_CLIENT_ID)/access_as_user"
$env:BACKEND_API_ACCESS_TOKEN = az account get-access-token --tenant $env:AZURE_AD_TENANT_ID --scope "api://$($env:AZURE_AD_CLIENT_ID)/access_as_user" --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $env:BACKEND_API_ACCESS_TOKEN" }
Invoke-RestMethod http://127.0.0.1:8000/api/ingestion/stats -Headers $headers
# Admin role required for deployment data operations:
.\infra\scripts\post-provision\setup-data.ps1 -BackendUrl "https://<backend-app>.azurewebsites.net" -Scenario contact-center
Remove-Item Env:BACKEND_API_ACCESS_TOKEN
```

`setup-data.ps1` uses `BACKEND_API_ACCESS_TOKEN` when explicitly supplied, otherwise
requests a delegated backend-scoped token from the Azure CLI. It fails instead of
sending unauthenticated production requests. Acquire a fresh token before retrying
if a long-running setup outlives token validity.

### Workload / managed identity

Assign the chosen **application role on the backend enterprise application** to the
calling service principal (including managed identities). For example, with Graph
app-role-assignment permissions, the following assigns the selected role; these are
**service principal object IDs**, unlike the client GUID used for audience:

```powershell
$callerSpObjectId = "<calling-service-principal-object-guid>"
$apiSpObjectId = "<backend-enterprise-application-object-guid>"
$roleId = "<Reader-Contributor-or-Admin-app-role-guid-from-backend-manifest>"
$body = @{ principalId = $callerSpObjectId; resourceId = $apiSpObjectId; appRoleId = $roleId } | ConvertTo-Json -Compress
az rest --method POST --url "https://graph.microsoft.com/v1.0/servicePrincipals/$callerSpObjectId/appRoleAssignments" --headers "Content-Type=application/json" --body $body
```

From an Azure host with the assigned managed identity:

```powershell
az login --identity
# For a user-assigned managed identity, use: az login --identity --client-id <identity-client-guid>
$env:BACKEND_API_ACCESS_TOKEN = az account get-access-token --resource "api://<backend-api-client-guid>" --query accessToken -o tsv
Invoke-RestMethod "https://<backend-app>.azurewebsites.net/api/ingestion/stats" -Headers @{ Authorization = "Bearer $env:BACKEND_API_ACCESS_TOKEN" }
Remove-Item Env:BACKEND_API_ACCESS_TOKEN
```

Other workloads can use `ManagedIdentityCredential` or `WorkloadIdentityCredential`
with scope `api://<backend-api-client-guid>/.default`. The backend registration must
issue v2 tokens with `idtyp=app`; Azure resource RBAC alone is not an app-role assignment.
Federated service principals can use client credentials with the same `.default`
scope and assigned application role; never substitute an ID token.

### Explicit local-development key (API tools only)

Only when **both** `APP_ENV=development` (or `local`) and an explicitly configured
`ADMIN_API_KEY` are set does the backend accept `X-Admin-Api-Key`. There is no default
key, sample user, or production bypass. `setup-data.ps1` uses this option only for
loopback URLs. Never put this key in browser code.

Docker Compose binds both services to `127.0.0.1`, passes auth settings explicitly,
and defaults `APP_ENV` to `development`; create a local `.env` with the backend
tenant/client GUIDs and/or an explicit development key, then run `docker compose up --build`.
The backend API is at `http://127.0.0.1:8000`. Set `APP_ENV=production` to exercise
mandatory production JWT configuration and leave `ADMIN_API_KEY` empty.
Compose does **not** emulate App Service EasyAuth: its frontend requires an actual
EasyAuth-capable hosting/sign-in setup; use bearer-authenticated API tools locally.
