#!/bin/bash
set -e

echo "Starting the application setup..."

# Set root and config paths
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AZURE_FOLDER="$ROOT_DIR/.azure"
CONFIG_FILE="$AZURE_FOLDER/config.json"

# Validate config.json
if [ ! -f "$CONFIG_FILE" ]; then
    echo "config.json not found at $CONFIG_FILE"
    exit 1
fi

# Ensure jq is installed
which jq || { echo "jq is not installed."; exit 1; }
# Extract default environment name using jq
DEFAULT_ENV=$(jq -r '.defaultEnvironment' "$CONFIG_FILE")
echo "Extracted default environment: $DEFAULT_ENV"

if [ -z "$DEFAULT_ENV" ] || [ "$DEFAULT_ENV" == "null" ]; then
    echo "Failed to extract defaultEnvironment from config.json"
    exit 1
fi

# Load .env file
ENV_FILE="$AZURE_FOLDER/$DEFAULT_ENV/.env"
API_ENV_FILE="$ROOT_DIR/src/api/.env"
WORKSHOP_ENV_FILE="$ROOT_DIR/docs/workshop/docs/workshop/.env"

# Check if .env file exists in .azure folder
if [ -f "$ENV_FILE" ]; then
    echo "Found .env file in Azure deployment folder: $ENV_FILE"
    
    # Check if API .env also exists and ask for overwrite
    if [ -f "$API_ENV_FILE" ]; then
        echo "Found existing .env file in src/api"
        read -p "Do you want to overwrite it with the Azure deployment .env? (y/N): " OVERWRITE_ENV
        # Convert to lowercase in a more portable way
        OVERWRITE_ENV=$(echo "$OVERWRITE_ENV" | tr '[:upper:]' '[:lower:]')
        if [[ "$OVERWRITE_ENV" == "y" ]]; then
            echo "Overwriting existing .env file with Azure deployment configuration..."
            cp "$ENV_FILE" "$API_ENV_FILE" || { echo "Failed to copy .env to src/api"; exit 1; }
            echo "Azure deployment .env copied to src/api"
            ENV_FILE_FOR_ROLES="$ENV_FILE"
        else
            echo "Preserving existing .env file in src/api"
            echo "Reading environment variables from src/api/.env for role assignments..."
            ENV_FILE_FOR_ROLES="$API_ENV_FILE"
        fi
    else
        echo "No .env file found in src/api, copying from Azure deployment..."
        cp "$ENV_FILE" "$API_ENV_FILE" || { echo "Failed to copy .env to src/api"; exit 1; }
        echo "Copied .env to src/api"
        ENV_FILE_FOR_ROLES="$ENV_FILE"
    fi
    
    # Copy to workshop directory
    mkdir -p "$(dirname "$WORKSHOP_ENV_FILE")"
    cp "$ENV_FILE" "$WORKSHOP_ENV_FILE" || { echo "Failed to copy .env to workshop directory"; exit 1; }
    echo "Azure deployment .env copied to workshop/docs/workshop"
    
else
    echo ".env file not found in Azure deployment folder: $ENV_FILE"
    
    # Try to use src/api .env file as fallback
    if [ -f "$API_ENV_FILE" ]; then
        echo "Using existing .env file from src/api for configuration..."
        ENV_FILE_FOR_ROLES="$API_ENV_FILE"
        echo "Warning: No Azure deployment .env found, using local src/api/.env"
    else
        echo "ERROR: No .env files found in either location:"
        echo "  - Azure deployment: $ENV_FILE"
        echo "  - API folder: $API_ENV_FILE"
        echo ""
        echo "Please choose one of the following options:"
        echo "  1. Run 'azd up' to deploy Azure resources and generate .env files"
        echo "  2. Manually create $API_ENV_FILE with required environment variables"
        echo "  3. Copy an existing .env file to one of the above locations"
        echo ""
        echo "For more information, see: documents/LocalDebuggingSetup.md"
        exit 1
    fi
fi

# Parse required variables for role assignments from the appropriate env file
echo "Reading environment variables for role assignments from: $ENV_FILE_FOR_ROLES"

# Parse environment variables manually to match batch script behavior
# Handle both Unix (LF) and Windows (CRLF) line endings
while IFS= read -r line || [ -n "$line" ]; do
    # Remove any carriage return characters (for Windows line endings)
    line=$(echo "$line" | tr -d '\r')
    
    # Skip empty lines and comments
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    
    # Split on first equals sign
    if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
        key="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[2]}"
        
        # Trim whitespace from key
        key=$(echo "$key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        
        # Remove quotes from value if present and trim whitespace
        value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | sed 's/^"\(.*\)"$/\1/')
        
        case "$key" in
            AZURE_RESOURCE_GROUP) AZURE_RESOURCE_GROUP="$value" ;;
            AZURE_COSMOSDB_ACCOUNT) AZURE_COSMOSDB_ACCOUNT="$value" ;;
            AZURE_AI_FOUNDRY_NAME) AI_FOUNDRY_NAME="$value" ;;
            AZURE_AI_SEARCH_NAME) SEARCH_SERVICE_NAME="$value" ;;
            AZURE_EXISTING_AI_PROJECT_RESOURCE_ID) EXISTING_AI_PROJECT_RESOURCE_ID="$value" ;;
            SQLDB_SERVER) 
                SQLDB_SERVER="$value"
                SQLDB_SERVER_NAME="${value%%.*}"
                ;;
        esac
    fi
done < "$ENV_FILE_FOR_ROLES"

# Write API base URL to frontend .env
APP_ENV_FILE="$ROOT_DIR/src/App/.env"
echo "REACT_APP_API_BASE_URL=http://127.0.0.1:8000" > "$APP_ENV_FILE"
echo "Updated src/App/.env with APP_API_BASE_URL"

# Add or update APP_ENV="dev" in API .env file
echo "Checking for existing APP_ENV in src/api/.env..."
if grep -q "^APP_ENV=" "$API_ENV_FILE" 2>/dev/null; then
    echo "APP_ENV already exists, updating to \"dev\"..."
    sed -i 's/^APP_ENV=.*/APP_ENV="dev"/' "$API_ENV_FILE"
else
    echo "APP_ENV not found, adding APP_ENV=\"dev\"..."
    echo 'APP_ENV="dev"' >> "$API_ENV_FILE"
fi
echo "APP_ENV=\"dev\" configured in src/api/.env"

# Authenticate with Azure
echo "Checking Azure login status..."
if az account show --query id --output tsv >/dev/null 2>&1; then
    echo "Already authenticated with Azure."
else
    echo "Not authenticated. Attempting Azure login..."
    az login --use-device-code --output none
    az account show --query "[name, id]" --output tsv
    echo "Logged in successfully."
fi

# Get signed-in user ID and subscription ID
signed_user_id=$(az ad signed-in-user show --query id -o tsv)
subscription_id=$(az account show --query id -o tsv)

# Set environment variables to prevent Git Bash path conversion issues
# Only set these on Windows/Git Bash environments
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    export MSYS_NO_PATHCONV=1
    export MSYS2_ARG_CONV_EXCL="*"
fi

# Check if user has Cosmos DB role
roleExists=$(az cosmosdb sql role assignment list \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --account-name "$AZURE_COSMOSDB_ACCOUNT" \
    --query "[?roleDefinitionId.ends_with(@, '00000000-0000-0000-0000-000000000002') && principalId == '$signed_user_id']" \
    -o tsv)

if [ -n "$roleExists" ]; then
    echo "User already has the Cosmos DB Built-in Data Contributor role."
else
    echo "Assigning Cosmos DB Built-in Data Contributor role..."
    az cosmosdb sql role assignment create \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --account-name "$AZURE_COSMOSDB_ACCOUNT" \
        --role-definition-id 00000000-0000-0000-0000-000000000002 \
        --principal-id "$signed_user_id" \
        --scope "/" \
        --output none
    echo "Cosmos DB Built-in Data Contributor role assigned successfully."
fi

# Assign Azure SQL Server AAD admin
SQLADMIN_USERNAME=$(az account show --query user.name --output tsv)
echo "Assigning Azure SQL Server AAD admin role to $SQLADMIN_USERNAME..."
az sql server ad-admin create \
    --display-name "$SQLADMIN_USERNAME" \
    --object-id "$signed_user_id" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --server "$SQLDB_SERVER_NAME" \
    --output tsv >/dev/null 2>&1
echo "Azure SQL Server AAD admin role assigned successfully."

# Assign Azure AI User role
echo "Checking Azure AI User role assignment..."
if [ -z "$EXISTING_AI_PROJECT_RESOURCE_ID" ]; then
    echo "Using AI Foundry account scope..."
    echo "AI Foundry Name: $AI_FOUNDRY_NAME"
    echo "Subscription ID: $subscription_id"
    echo "Resource Group: $AZURE_RESOURCE_GROUP"
    
    # First, verify the AI Foundry resource exists
    echo "Verifying AI Foundry resource exists..."
    foundryExists=$(az cognitiveservices account show \
        --name "$AI_FOUNDRY_NAME" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --query "id" -o tsv 2>/dev/null || echo "")
    
    if [ -z "$foundryExists" ]; then
        echo "ERROR: AI Foundry resource '$AI_FOUNDRY_NAME' not found in resource group '$AZURE_RESOURCE_GROUP'"
        echo "Please verify the AZURE_AI_FOUNDRY_NAME in your .env file"
        exit 1
    else
        echo "AI Foundry resource verified: $foundryExists"
    fi
    
    # Use the actual resource ID as scope instead of constructing it
    echo "Checking role assignment with scope: $foundryExists"
    aiUserRoleExists=$(az role assignment list \
        --assignee "$signed_user_id" \
        --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
        --scope "$foundryExists" \
        --query "[0].id" -o tsv)
    
    if [ -n "$aiUserRoleExists" ]; then
        echo "User already has the Azure AI User role."
    else
        echo "Assigning Azure AI User role to AI Foundry account..."
        az role assignment create \
            --assignee "$signed_user_id" \
            --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
            --scope "$foundryExists" \
            --output none
        echo "Azure AI User role assigned successfully."
    fi
else
    echo "Extracting foundry scope from existing AI project resource ID..."
    # Parse the resource ID to extract the foundry scope (similar to batch script logic)
    IFS='/' read -ra ADDR <<< "$EXISTING_AI_PROJECT_RESOURCE_ID"
    if [ ${#ADDR[@]} -ge 8 ]; then
        FOUNDRY_SCOPE="/${ADDR[1]}/${ADDR[2]}/${ADDR[3]}/${ADDR[4]}/${ADDR[5]}/${ADDR[6]}/${ADDR[7]}/${ADDR[8]}"
    else
        FOUNDRY_SCOPE="$EXISTING_AI_PROJECT_RESOURCE_ID"
    fi
    echo "Using foundry scope from existing project: $FOUNDRY_SCOPE"
    
    aiUserRoleExists=$(az role assignment list \
        --assignee "$signed_user_id" \
        --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
        --scope "$FOUNDRY_SCOPE" \
        --query "[0].id" -o tsv)
    
    if [ -n "$aiUserRoleExists" ]; then
        echo "User already has the Azure AI User role."
    else
        echo "Assigning Azure AI User role to foundry account..."
        az role assignment create \
            --assignee "$signed_user_id" \
            --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
            --scope "$FOUNDRY_SCOPE" \
            --output none
        echo "Azure AI User role assigned successfully."
    fi
fi

# Assign Search Index Data Reader role
echo "Checking Search Index Data Reader role assignment..."
searchReaderRoleExists=$(az role assignment list \
    --assignee "$signed_user_id" \
    --role "1407120a-92aa-4202-b7e9-c0e197c71c8f" \
    --scope "/subscriptions/$subscription_id/resourceGroups/$AZURE_RESOURCE_GROUP/providers/Microsoft.Search/searchServices/$SEARCH_SERVICE_NAME" \
    --query "[0].id" -o tsv)

if [ -n "$searchReaderRoleExists" ]; then
    echo "User already has the Search Index Data Reader role."
else
    echo "Assigning Search Index Data Reader role to AI Search service..."
    az role assignment create \
        --assignee "$signed_user_id" \
        --role "1407120a-92aa-4202-b7e9-c0e197c71c8f" \
        --scope "/subscriptions/$subscription_id/resourceGroups/$AZURE_RESOURCE_GROUP/providers/Microsoft.Search/searchServices/$SEARCH_SERVICE_NAME" \
        --output none
    echo "Search Index Data Reader role assigned successfully."
fi

echo "Proceeding to create virtual environment and restore backend Python packages..."
# Create and activate virtual environment in root folder
cd "$ROOT_DIR"

# Check if virtual environment already exists
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment in root folder..."
    python -m venv .venv || { echo "Failed to create virtual environment"; exit 1; }
    echo "Virtual environment created successfully."
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment and install backend packages
echo "Activating virtual environment and installing backend packages..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

python -m pip install --upgrade pip

cd src/api

python -m pip install -r requirements.txt || { echo "Failed to restore backend Python packages"; deactivate; exit 1; }

echo "Backend Python packages installed successfully in virtual environment."
deactivate
cd "$ROOT_DIR"

# Restore frontend packages
cd "$ROOT_DIR/src/App"
npm install --force || { echo "Failed to restore frontend npm packages"; exit 1; }
cd "$ROOT_DIR"

# Start backend and frontend
echo "Starting backend server..."
cd "$ROOT_DIR"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi
cd src/api

python app.py --port=8000 &

echo "Backend started at http://127.0.0.1:8000"

echo "Waiting for backend to initialize..."
sleep 30

echo "Starting frontend server..."
cd "$ROOT_DIR/src/App"
npm start

echo "Both servers have been started."
echo "Backend running at http://127.0.0.1:8000"
echo "Frontend running at http://localhost:3000"