@echo off
setlocal enabledelayedexpansion
echo Starting the application setup...

REM Set root and config paths
set ROOT_DIR=%cd%\..
set AZURE_FOLDER=%ROOT_DIR%\.azure
set CONFIG_FILE=%AZURE_FOLDER%\config.json

REM Validate config.json
if not exist "%CONFIG_FILE%" (
    echo config.json not found at %CONFIG_FILE%
    exit /b 1
)

REM Extract default environment name
for /f "delims=" %%i in ('powershell -command "(Get-Content '%CONFIG_FILE%' | ConvertFrom-Json).defaultEnvironment"') do set DEFAULT_ENV=%%i

if not defined DEFAULT_ENV (
    echo Failed to extract defaultEnvironment from config.json
    exit /b 1
)

REM Load .env file
set ENV_FILE=%AZURE_FOLDER%\%DEFAULT_ENV%\.env
set API_ENV_FILE=%ROOT_DIR%\src\api\.env
set WORKSHOP_ENV_FILE=%ROOT_DIR%\docs\workshop\docs\workshop\.env

REM Check if .env file exists in .azure folder
if exist "%ENV_FILE%" (
    echo Found .env file in Azure deployment folder: %ENV_FILE%
    
    REM Check if API .env also exists and ask for overwrite
    if exist "%API_ENV_FILE%" (
        echo Found existing .env file in src/api
        set /p OVERWRITE_ENV="Do you want to overwrite it with the Azure deployment .env? (y/N): "
        if /i "!OVERWRITE_ENV!"=="y" (
            echo Overwriting existing .env file with Azure deployment configuration...
            copy /Y "%ENV_FILE%" "%API_ENV_FILE%"
            if errorlevel 1 (
                echo Failed to copy .env to src/api
                exit /b 1
            )
            echo Azure deployment .env copied to src/api
            set ENV_FILE_FOR_ROLES=%ENV_FILE%
        ) else (
            echo Preserving existing .env file in src/api
            echo Reading environment variables from src/api/.env for role assignments...
            set ENV_FILE_FOR_ROLES=%API_ENV_FILE%
        )
    ) else (
        echo No .env file found in src/api, copying from Azure deployment...
        copy /Y "%ENV_FILE%" "%API_ENV_FILE%"
        if errorlevel 1 (
            echo Failed to copy .env to src/api
            exit /b 1
        )
        echo Copied .env to src/api
        set ENV_FILE_FOR_ROLES=%ENV_FILE%
    )
    
    REM Copy to workshop directory
    copy /Y "%ENV_FILE%" "%WORKSHOP_ENV_FILE%"
    if errorlevel 1 (
        echo Failed to copy .env to workshop directory
        exit /b 1
    )
    echo Azure deployment .env copied to workshop/docs/workshop
    
) else (
    echo .env file not found in Azure deployment folder: %ENV_FILE%
    
    REM Try to use src/api .env file as fallback
    if exist "%API_ENV_FILE%" (
        echo Using existing .env file from src/api for configuration...
        set ENV_FILE_FOR_ROLES=%API_ENV_FILE%
        echo Warning: No Azure deployment .env found, using local src/api/.env
    ) else (
        echo ERROR: No .env files found in either location:
        echo   - Azure deployment: %ENV_FILE%
        echo   - API folder: %API_ENV_FILE%
        echo.
        echo Please choose one of the following options:
        echo   1. Run 'azd up' to deploy Azure resources and generate .env files
        echo   2. Manually create %API_ENV_FILE% with required environment variables
        echo   3. Copy an existing .env file to one of the above locations
        echo.
        echo For more information, see: documents/LocalSetup.md
        exit /b 1
    )
)

REM Parse required variables for role assignments from the appropriate env file
echo Reading environment variables for role assignments from: %ENV_FILE_FOR_ROLES%
for /f "tokens=1,* delims==" %%A in ('type "%ENV_FILE_FOR_ROLES%"') do (
    if "%%A"=="AZURE_RESOURCE_GROUP" set AZURE_RESOURCE_GROUP=%%~B
    if "%%A"=="AZURE_COSMOSDB_ACCOUNT" set AZURE_COSMOSDB_ACCOUNT=%%~B
    if "%%A"=="AZURE_AI_FOUNDRY_NAME" set "AI_FOUNDRY_NAME=%%~B"
    if "%%A"=="AZURE_AI_SEARCH_NAME" set "SEARCH_SERVICE_NAME=%%~B"
    if "%%A"=="AZURE_EXISTING_AI_PROJECT_RESOURCE_ID" set "EXISTING_AI_PROJECT_RESOURCE_ID=%%~B"
    if "%%A"=="SQLDB_SERVER" (
        set SQLDB_SERVER=%%~B
        for /f "tokens=1 delims=." %%C in ("%%~B") do set SQLDB_SERVER_NAME=%%C
    )
)

REM Write API base URL to frontend .env
set APP_ENV_FILE=%ROOT_DIR%\src\App\.env
(
    echo REACT_APP_API_BASE_URL=http://127.0.0.1:8000
) > "%APP_ENV_FILE%"
echo Updated src/App/.env with APP_API_BASE_URL

REM Add or update APP_ENV="dev" in API .env file
echo Checking for existing APP_ENV in src/api/.env...
findstr /i "^APP_ENV=" "%API_ENV_FILE%" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo APP_ENV already exists, updating to "dev"...
    powershell -command "(Get-Content '%API_ENV_FILE%') -replace '^APP_ENV=.*', 'APP_ENV=\"dev\"' | Set-Content '%API_ENV_FILE%'"
) else (
    echo APP_ENV not found, adding APP_ENV="dev"...
    echo APP_ENV="dev" >> "%API_ENV_FILE%"
)
echo APP_ENV="dev" configured in src/api/.env

REM Authenticate with Azure
echo Checking Azure login status...
call az account show --query id --output tsv >nul 2>&1
if %ERRORLEVEL%==0 (
    echo Already authenticated with Azure.
) else (
    echo Not authenticated. Attempting Azure login...

    call az login --use-device-code --output none

    call az account show --query "[name, id]" --output tsv

    echo Logged in successfully.
)

REM Get signed-in user ID and subscription ID
FOR /F "delims=" %%i IN ('az ad signed-in-user show --query id -o tsv') DO set "signed_user_id=%%i"
FOR /F "delims=" %%s IN ('az account show --query id -o tsv') DO set "subscription_id=%%s"

REM Check if user has Cosmos DB role
FOR /F "delims=" %%i IN ('az cosmosdb sql role assignment list --resource-group %AZURE_RESOURCE_GROUP% --account-name %AZURE_COSMOSDB_ACCOUNT% --query "[?roleDefinitionId.ends_with(@, '00000000-0000-0000-0000-000000000002') && principalId == '%signed_user_id%']" -o tsv') DO set "roleExists=%%i"
if defined roleExists (
    echo User already has the Cosmos DB Built-in Data Contributor role.
) else (
    echo Assigning Cosmos DB Built-in Data Contributor role...
    set MSYS_NO_PATHCONV=1
    call az cosmosdb sql role assignment create ^
        --resource-group %AZURE_RESOURCE_GROUP% ^
        --account-name %AZURE_COSMOSDB_ACCOUNT% ^
        --role-definition-id 00000000-0000-0000-0000-000000000002 ^
        --principal-id %signed_user_id% ^
        --scope "/" ^
        --output none
    echo Cosmos DB Built-in Data Contributor role assigned successfully.
)

REM Assign Azure SQL Server AAD admin
FOR /F "delims=" %%i IN ('az account show --query user.name --output tsv') DO set "SQLADMIN_USERNAME=%%i"
echo Assigning Azure SQL Server AAD admin role to %SQLADMIN_USERNAME%...
call az sql server ad-admin create ^
    --display-name %SQLADMIN_USERNAME% ^
    --object-id "%signed_user_id%" ^
    --resource-group %AZURE_RESOURCE_GROUP% ^
    --server %SQLDB_SERVER_NAME% ^
    --output tsv >nul 2>&1
echo Azure SQL Server AAD admin role assigned successfully.

REM Assign Azure AI User role
echo Checking Azure AI User role assignment...
if not defined EXISTING_AI_PROJECT_RESOURCE_ID (
    echo Using AI Foundry account scope...
    FOR /F "delims=" %%i IN ('az role assignment list --assignee %signed_user_id% --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" --scope "/subscriptions/%subscription_id%/resourceGroups/%AZURE_RESOURCE_GROUP%/providers/Microsoft.CognitiveServices/accounts/%AI_FOUNDRY_NAME%" --query "[0].id" -o tsv') DO set "aiUserRoleExists=%%i"
    if defined aiUserRoleExists (
        echo User already has the Azure AI User role.
    ) else (
        echo Assigning Azure AI User role to AI Foundry account...
        call az role assignment create ^
            --assignee %signed_user_id% ^
            --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" ^
            --scope "/subscriptions/%subscription_id%/resourceGroups/%AZURE_RESOURCE_GROUP%/providers/Microsoft.CognitiveServices/accounts/%AI_FOUNDRY_NAME%" ^
            --output none
        echo Azure AI User role assigned successfully.
    )
) else (
    echo Extracting foundry scope from existing AI project resource ID...
    for /f "tokens=1,2,3,4,5,6,7,8 delims=/" %%a in ("%EXISTING_AI_PROJECT_RESOURCE_ID%") do (
        set "FOUNDRY_SCOPE=/%%a/%%b/%%c/%%d/%%e/%%f/%%g/%%h"
    )
    echo Using foundry scope from existing project: !FOUNDRY_SCOPE!
    FOR /F "delims=" %%i IN ('az role assignment list --assignee %signed_user_id% --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" --scope "!FOUNDRY_SCOPE!" --query "[0].id" -o tsv') DO set "aiUserRoleExists=%%i"
    if defined aiUserRoleExists (
        echo User already has the Azure AI User role.
    ) else (
        echo Assigning Azure AI User role to foundry account...
        call az role assignment create ^
            --assignee %signed_user_id% ^
            --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" ^
            --scope "!FOUNDRY_SCOPE!" ^
            --output none
        echo Azure AI User role assigned successfully.
    )
)

REM Assign Search Index Data Reader role
echo Checking Search Index Data Reader role assignment...
FOR /F "delims=" %%i IN ('az role assignment list --assignee %signed_user_id% --role "1407120a-92aa-4202-b7e9-c0e197c71c8f" --scope "/subscriptions/%subscription_id%/resourceGroups/%AZURE_RESOURCE_GROUP%/providers/Microsoft.Search/searchServices/%SEARCH_SERVICE_NAME%" --query "[0].id" -o tsv') DO set "searchReaderRoleExists=%%i"
if defined searchReaderRoleExists (
    echo User already has the Search Index Data Reader role.
) else (
    echo Assigning Search Index Data Reader role to AI Search service...
    call az role assignment create ^
        --assignee %signed_user_id% ^
        --role "1407120a-92aa-4202-b7e9-c0e197c71c8f" ^
        --scope "/subscriptions/%subscription_id%/resourceGroups/%AZURE_RESOURCE_GROUP%/providers/Microsoft.Search/searchServices/%SEARCH_SERVICE_NAME%" ^
        --output none
    echo Search Index Data Reader role assigned successfully.
)

echo Proceeding to create virtual environment and restore backend Python packages...
REM Create and activate virtual environment in root folder
cd %ROOT_DIR%

REM Check if virtual environment already exists
if not exist ".venv" (
    echo Creating Python virtual environment in root folder...
    call python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment
        exit /b 1
    )
    echo Virtual environment created successfully.
) else (
    echo Virtual environment already exists.
)

REM Activate virtual environment and install backend packages
echo Activating virtual environment and installing backend packages...
call .venv\Scripts\activate.bat
call python -m pip install --upgrade pip
cd src\api
call python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to restore backend Python packages
    call deactivate
    exit /b 1
)
echo Backend Python packages installed successfully in virtual environment.
call deactivate
cd %ROOT_DIR%

REM Restore frontend packages
cd %ROOT_DIR%\src\App
call npm install --force
if errorlevel 1 (
    echo Failed to restore frontend npm packages
    exit /b 1
)
cd %ROOT_DIR%

REM Start backend and frontend
echo Starting backend server...
cd %ROOT_DIR%
call .venv\Scripts\activate.bat
cd src\api
start /b python app.py --port=8000
echo Backend started at http://127.0.0.1:8000

echo Waiting for backend to initialize...
timeout /t 90 /nobreak >nul

echo Starting frontend server...
cd %ROOT_DIR%\src\App
call npm start

echo Both servers have been started.
echo Backend running at http://127.0.0.1:8000
echo Frontend running at http://localhost:3000

endlocal