@description('Existing frontend App Service name.')
param frontendAppName string

param tenantId string
param backendClientId string
param frontendClientId string

@description('Frontend web registration secret; kept secure across all module boundaries.')
@secure()
@minLength(1)
param frontendClientSecret string

resource frontend 'Microsoft.Web/sites@2025-03-01' existing = {
  name: frontendAppName
}

// Configure the secret here rather than passing it through AVM's non-secure configs parameter.
// The frontend deployment has completed; preserve its generated application settings.
resource frontendSettings 'Microsoft.Web/sites/config@2025-03-01' = {
  parent: frontend
  name: 'appsettings'
  properties: union(list('${frontend.id}/config/appsettings', '2025-03-01').properties, {
    FRONTEND_AUTH_CLIENT_SECRET: frontendClientSecret
  })
}

resource authentication 'Microsoft.Web/sites/config@2025-03-01' = {
  parent: frontend
  name: 'authsettingsV2'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      requireAuthentication: true
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          openIdIssuer: uri(environment().authentication.loginEndpoint, '${tenantId}/v2.0')
          clientId: frontendClientId
          clientSecretSettingName: 'FRONTEND_AUTH_CLIENT_SECRET'
        }
        login: {
          loginParameters: [
            'scope=openid profile email offline_access api://${backendClientId}/access_as_user'
          ]
        }
      }
    }
    login: {
      tokenStore: {
        enabled: true
      }
    }
    httpSettings: {
      requireHttps: true
    }
  }
  dependsOn: [
    frontendSettings
  ]
}
