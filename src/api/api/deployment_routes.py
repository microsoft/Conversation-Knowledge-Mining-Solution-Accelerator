"""
Deployment API Routes

This module provides REST API endpoints for orchestrating all deployment operations.
It replaces the three Bicep deployment scripts with a unified API approach:
1. Upload demo data (copy_kb_files.sh)
2. Create indexes and process data (run_create_index_scripts.sh)
3. Create SQL users and roles (create-sql-user-and-role.ps1)
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from services.deployment_orchestration_service import DeploymentOrchestrationService

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize the deployment orchestration service
deployment_service = DeploymentOrchestrationService()


class DeploymentRequest(BaseModel):
    """Request model for full deployment."""
    base_url: Optional[str] = Field(
        None,
        description="Base URL for downloading files (optional, uses env var if not provided)"
    )
    keyvault_name: Optional[str] = Field(
        None,
        description="Azure Key Vault name (optional, uses env var if not provided)"
    )
    managed_identity_client_id: Optional[str] = Field(
        None,
        description="Managed Identity Client ID for data operations (optional, uses env var if not provided)"
    )
    storage_account_name: Optional[str] = Field(
        None,
        description="Azure Storage Account name (optional, uses env var if not provided)"
    )
    sql_server_name: Optional[str] = Field(
        None,
        description="SQL Server name (optional, uses env var if not provided)"
    )
    sql_database_name: Optional[str] = Field(
        None,
        description="SQL Database name (optional, uses env var if not provided)"
    )
    backend_identity_client_id: Optional[str] = Field(
        None,
        description="Backend Managed Identity Client ID for SQL operations (optional)"
    )
    backend_identity_name: Optional[str] = Field(
        None,
        description="Backend Managed Identity Display Name (optional)"
    )


class DeploymentResponse(BaseModel):
    """Response model for deployment operations."""
    status: str
    message: str
    operations: Optional[dict] = None


class StatusResponse(BaseModel):
    """Response model for status check."""
    status: str
    message: str
    configured: Optional[dict] = None


@router.post("/deploy-all", response_model=DeploymentResponse, status_code=status.HTTP_200_OK)
async def deploy_all_operations(request: DeploymentRequest = None):
    """
    Execute all deployment operations in sequence.
    
    This single endpoint replaces three Bicep deployment scripts:
    1. **Upload Demo Data** - Downloads and uploads call transcripts and audio data to Azure Storage
    2. **Create Search Indexes** - Creates Azure AI Search indexes and processes data
    3. **Create SQL User** - Creates SQL database user and assigns roles
    
    The operations run sequentially to ensure proper dependencies are met.
    
    **What it does:**
    
    **Operation 1: Upload Demo Data**
    - Downloads call_transcripts.zip and audio_data.zip from GitHub
    - Extracts and uploads to Azure Data Lake Storage (data container)
    - Creates custom_audiodata and custom_transcripts directories
    
    **Operation 2: Create Search Indexes & Process Data**
    - Downloads and executes 4 Python scripts:
      - 01_create_search_index.py - Creates Azure AI Search index
      - 02_create_cu_template_text.py - Creates Content Understanding template for text
      - 02_create_cu_template_audio.py - Creates Content Understanding template for audio
      - 03_cu_process_data_text.py - Processes text data with Content Understanding
    
    **Operation 3: Create SQL User & Roles**
    - Creates a SQL database user for the backend managed identity
    - Assigns db_datareader and db_datawriter roles
    
    **Request Body** (all fields optional, will use environment variables if not provided):
    ```json
    {
        "keyvault_name": "my-keyvault",
        "managed_identity_client_id": "12345678-1234-1234-1234-123456789abc",
        "storage_account_name": "mystorageaccount",
        "sql_server_name": "mysqlserver",
        "sql_database_name": "mydb",
        "backend_identity_client_id": "87654321-4321-4321-4321-cba987654321",
        "backend_identity_name": "backend-identity"
    }
    ```
    
    **Response**:
    ```json
    {
        "status": "success",
        "message": "All deployment operations completed successfully",
        "operations": {
            "upload_data": {
                "status": "success",
                "message": "Demo data uploaded successfully",
                "files_uploaded": ["call_transcripts", "audiodata"],
                "directories_created": ["custom_audiodata", "custom_transcripts"]
            },
            "create_indexes": {
                "status": "success",
                "message": "Search indexes created and data processed successfully",
                "scripts_executed": [...]
            },
            "sql_user_creation": {
                "status": "success",
                "message": "SQL user created and roles assigned successfully",
                "user": "backend-identity",
                "roles": ["db_datareader", "db_datawriter"]
            }
        }
    }
    ```
    
    **Required Environment Variables** (if not provided in request):
    - AZURE_KEYVAULT_NAME
    - AZURE_MANAGED_IDENTITY_CLIENT_ID
    - ADLS_ACCOUNT_NAME (Storage Account)
    - SQLDB_SERVER (optional for SQL operations)
    - SQLDB_DATABASE (optional for SQL operations)
    
    **Note**: This operation can take several minutes to complete as it performs:
    - File downloads and uploads
    - Index creation
    - Data processing
    - SQL user provisioning
    """
    try:
        logger.info("Received full deployment request")
        
        # Extract parameters from request if provided
        params = {}
        if request:
            if request.base_url:
                params['base_url'] = request.base_url
            if request.keyvault_name:
                params['keyvault_name'] = request.keyvault_name
            if request.managed_identity_client_id:
                params['managed_identity_client_id'] = request.managed_identity_client_id
            if request.storage_account_name:
                params['storage_account_name'] = request.storage_account_name
            if request.sql_server_name:
                params['sql_server_name'] = request.sql_server_name
            if request.sql_database_name:
                params['sql_database_name'] = request.sql_database_name
            if request.backend_identity_client_id:
                params['backend_identity_client_id'] = request.backend_identity_client_id
            if request.backend_identity_name:
                params['backend_identity_name'] = request.backend_identity_name
        
        # Execute full deployment
        result = await deployment_service.run_full_deployment(**params)
        
        logger.info("Full deployment completed successfully")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in deployment endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/status", response_model=StatusResponse, status_code=status.HTTP_200_OK)
async def get_deployment_status():
    """
    Get the current status of the deployment orchestration service.
    
    This endpoint checks if the service is ready and shows which configuration
    parameters are set (via environment variables).
    
    **Response**:
    ```json
    {
        "status": "ready",
        "message": "Deployment orchestration service is ready",
        "configured": {
            "keyvault_name": true,
            "managed_identity_client_id": true,
            "storage_account_name": true,
            "sql_server_name": true,
            "sql_database_name": true
        }
    }
    ```
    """
    try:
        result = await deployment_service.get_deployment_status()
        return result
    except Exception as e:
        logger.error(f"Error checking deployment status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve status: {str(e)}"
        )


# Individual operation endpoints for granular control

@router.post("/upload-data", response_model=DeploymentResponse, status_code=status.HTTP_200_OK)
async def upload_demo_data_only(
    storage_account_name: Optional[str] = None,
    managed_identity_client_id: Optional[str] = None,
    base_url: Optional[str] = None
):
    """
    Upload demo data files only (Operation 1).
    
    This endpoint runs only the data upload operation without creating indexes or SQL users.
    
    **What it does:**
    - Downloads call_transcripts.zip and audio_data.zip
    - Extracts and uploads to Azure Storage
    - Creates custom directories
    
    **Query Parameters:**
    - storage_account_name (optional)
    - managed_identity_client_id (optional)
    - base_url (optional)
    """
    try:
        logger.info("Uploading demo data only...")
        
        from services.deployment_orchestration_service import DeploymentOrchestrationService
        service = DeploymentOrchestrationService()
        
        # Hardcoded values for testing
        storage_account = "stckmpocdsapi15xyh6"
        client_id = "f6a5c843-6e09-4a87-a9f8-d12c9691ccfd"
        url = "https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/"
        
        result = await service._upload_demo_data(url, storage_account, client_id)
        
        return {
            "status": "success",
            "message": "Demo data uploaded successfully",
            "operations": {"upload_data": result}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload demo data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Demo data upload failed: {str(e)}"
        )


@router.post("/create-indexes", response_model=DeploymentResponse, status_code=status.HTTP_200_OK)
async def create_indexes_only(
    keyvault_name: Optional[str] = None,
    managed_identity_client_id: Optional[str] = None,
    base_url: Optional[str] = None
):
    """
    Create search indexes and process data only (Operation 2).
    
    This endpoint runs only the index creation and data processing without uploading data or creating SQL users.
    
    **What it does:**
    - Creates Azure AI Search index
    - Creates Content Understanding templates
    - Processes text and audio data
    
    **Query Parameters:**
    - keyvault_name (optional)
    - managed_identity_client_id (optional)
    - base_url (optional)
    """
    try:
        logger.info("Creating indexes and processing data only...")
        
        from services.deployment_orchestration_service import DeploymentOrchestrationService
        service = DeploymentOrchestrationService()
        
        kv_name = keyvault_name or service.keyvault_name
        client_id = managed_identity_client_id or service.managed_identity_client_id
        url = base_url or service.base_url
        
        if not kv_name or not client_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="keyvault_name and managed_identity_client_id are required"
            )
        
        result = await service._create_indexes_and_process(url, kv_name, client_id)
        
        return {
            "status": "success",
            "message": "Indexes created and data processed successfully",
            "operations": {"create_indexes": result}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create indexes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Index creation failed: {str(e)}"
        )


@router.post("/create-sql-user", response_model=DeploymentResponse, status_code=status.HTTP_200_OK)
async def create_sql_user_only(
    sql_server_name: Optional[str] = None,
    sql_database_name: Optional[str] = None,
    backend_identity_client_id: Optional[str] = None,
    backend_identity_name: Optional[str] = None
):
    """
    Create SQL user and assign roles only (Operation 3).
    
    This endpoint runs only the SQL user creation without uploading data or creating indexes.
    
    **What it does:**
    - Creates SQL database user for backend managed identity
    - Assigns db_datareader and db_datawriter roles
    
    **Query Parameters:**
    - sql_server_name (optional)
    - sql_database_name (optional)
    - backend_identity_client_id (optional)
    - backend_identity_name (optional)
    """
    try:
        logger.info("Creating SQL user and assigning roles only...")
        
        from services.deployment_orchestration_service import DeploymentOrchestrationService
        service = DeploymentOrchestrationService()
        
        server = sql_server_name or service.sql_server_name
        database = sql_database_name or service.sql_database_name
        identity_name = backend_identity_name or "backend-identity"
        
        if not server or not database or not backend_identity_client_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="sql_server_name, sql_database_name, and backend_identity_client_id are required"
            )
        
        result = await service._create_sql_user_and_roles(
            server, database, backend_identity_client_id, identity_name
        )
        
        return {
            "status": "success",
            "message": "SQL user created and roles assigned successfully",
            "operations": {"sql_user_creation": result}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create SQL user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SQL user creation failed: {str(e)}"
        )
