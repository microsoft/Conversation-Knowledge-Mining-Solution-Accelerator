# Create the required app registrations

Create **two single-tenant registrations**, not one shared registration:

1. A **backend API** registration issuing v2 access tokens, exposing
   `api://<backend-client-guid>/access_as_user`, and defining the enabled
   `Reader`, `Contributor`, and `Admin` application roles for users and applications.
2. A **frontend web** registration with redirect URI
   `https://<frontend-app>.azurewebsites.net/.auth/login/aad/callback`,
   consented delegated permission to the backend scope, and a securely stored client secret.

Follow [Authentication and role assignments](./AppAuthentication.md) for the complete
manifest settings (`api.requestedAccessTokenVersion=2` and access-token `idtyp`),
user/service-principal role assignments, EasyAuth token store and login scopes,
deployment parameters, and local/workload token commands. Graph `User.Read` alone
does not authorize backend access. App registration permissions may require a tenant
administrator; do not skip authentication when registration creation is restricted.

Return to [Verify Authentication](./DeploymentGuide.md#54-verify-authentication-required).
