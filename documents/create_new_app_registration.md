# Creating a new App Registration

1. Click on `Home` and select `Microsoft Entra ID`.

![Microsoft Entra ID](Images/MicrosoftEntraID.png)

2. Click on `App registrations`.

![App registrations](Images/Appregistrations.png)

3. Click on `+ New registration`.

![New Registrations](Images/NewRegistration.png)

4. Provide the `Name`, select supported account types as `Accounts in this organizational directory only(Contoso only - Single tenant)`, select platform as `Web`, enter/select the `URL` and register.

![Add Details](Images/AddDetails.png)

5. After application is created successfully, then click on `Add a Redirect URL`.

![Redirect URL](Images/AddRedirectURL.png)

6. Click on `+ Add a platform`.

![+ Add platform](Images/AddPlatform.png)

7. Click on `Web`.

![Web](Images/Web.png)

8. Enter the `web app URL` (Provide the app service name in place of XXXX) and Save. Then go back to [Set Up Authentication in Azure App Service](/documents/AppAuthentication.md) Step 1 page and follow from _Point 4_ choose `Pick an existing app registration in this directory` from the Add an Identity Provider page and provide the newly registered App Name.

E.g. <<https://<< appservicename >>.azurewebsites.net/.auth/login/aad/callback>>

![Add Details](Images/WebAppURL.png)
