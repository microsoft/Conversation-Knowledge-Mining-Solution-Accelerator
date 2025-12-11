"""
FastAPI application for post-deployment setup tasks.

This API provides endpoints to run the three main deployment scripts:
1. Upload demo data to Azure Storage
2. Create search indexes and process data
3. Create SQL user and assign roles

All endpoints support both local development (DefaultAzureCredential) and
Azure-hosted environments (ManagedIdentityCredential).
"""

from __future__ import annotations

import os
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

# Import our existing modules
from test_upload_demo_data import upload_demo_data
from index_pipeline import run_index_pipeline
from sql_user_role_setup import create_sql_user_and_roles


app = FastAPI(
    title="Deployment Setup API",
    description="API for running post-deployment setup tasks",
    version="1.0.0"
)


# ============================================================================
# Request/Response Models
# ============================================================================

class UploadDemoDataRequest(BaseModel):
    storage_account: str = Field(..., description="Storage account name (e.g., 'stxxxxx')")
    managed_identity_client_id: str = Field(..., description="Managed Identity Client ID")
    base_url: str = Field(
        default="https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/",
        description="Base URL for downloading demo data files"
    )


class IndexPipelineRequest(BaseModel):
    keyvault_name: str = Field(..., description="Azure Key Vault name")
    managed_identity_client_id: str = Field(..., description="Managed Identity Client ID")


class SqlUserRoleRequest(BaseModel):
    server: str = Field(..., description="SQL Server DNS name (e.g., 'sql-xxxxx.database.windows.net')")
    database: str = Field(..., description="Database name")
    client_id: str = Field(..., description="Managed Identity Client ID for the backend")
    display_name: str = Field(..., description="Display name for the SQL user")
    roles: List[str] = Field(..., description="List of database roles (e.g., ['db_datareader', 'db_datawriter'])")


class DeploymentRequest(BaseModel):
    """Combined request for all deployment tasks"""
    storage_account: str = Field(..., description="Storage account name")
    keyvault_name: str = Field(..., description="Azure Key Vault name")
    sql_server: str = Field(..., description="SQL Server DNS name")
    sql_database: str = Field(..., description="SQL Database name")
    managed_identity_client_id: str = Field(..., description="Main Managed Identity Client ID")
    backend_identity_client_id: str = Field(..., description="Backend Managed Identity Client ID for SQL")
    backend_identity_display_name: str = Field(..., description="Backend Identity display name")
    sql_roles: List[str] = Field(
        default=["db_datareader", "db_datawriter"],
        description="SQL database roles to assign"
    )
    base_url: str = Field(
        default="https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/",
        description="Base URL for downloading demo data files"
    )


class TaskResponse(BaseModel):
    status: str
    message: str
    details: Dict[str, Any] = {}


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", response_model=Dict[str, str])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "deployment-api"}


# ============================================================================
# Individual Task Endpoints
# ============================================================================

@app.post("/upload-demo-data", response_model=TaskResponse, status_code=status.HTTP_200_OK)
async def upload_demo_data_endpoint(request: UploadDemoDataRequest):
    """
    Upload demo data files to Azure Storage.
    
    Downloads call_transcripts.zip and audio_data.zip from GitHub,
    extracts them, and uploads to the specified storage account.
    """
    try:
        upload_demo_data(
            storage_account=request.storage_account,
            managed_identity_client_id=request.managed_identity_client_id,
            base_url=request.base_url
        )
        return TaskResponse(
            status="success",
            message="Demo data uploaded successfully",
            details={
                "storage_account": request.storage_account,
                "files_uploaded": ["call_transcripts", "audiodata"]
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload demo data: {str(e)}"
        )


@app.post("/create-search-indexes", response_model=TaskResponse, status_code=status.HTTP_200_OK)
async def create_search_indexes_endpoint(request: IndexPipelineRequest):
    """
    Run the index creation and data processing pipeline.
    
    Executes all index scripts:
    - Create search index
    - Create content understanding templates (text and audio)
    - Process data
    """
    try:
        result = run_index_pipeline(
            keyvault_name=request.keyvault_name,
            managed_identity_client_id=request.managed_identity_client_id
        )
        
        # Check if any step failed
        failed_steps = [step for step in result.get("steps", []) if step.get("status") == "error"]
        if failed_steps:
            return TaskResponse(
                status="partial_success",
                message="Some pipeline steps failed",
                details=result
            )
        
        return TaskResponse(
            status="success",
            message="Search indexes created and data processed successfully",
            details=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create search indexes: {str(e)}"
        )


@app.post("/create-sql-user", response_model=TaskResponse, status_code=status.HTTP_200_OK)
async def create_sql_user_endpoint(request: SqlUserRoleRequest):
    """
    Create SQL user and assign database roles.
    
    Creates an Azure AD user in the SQL database and assigns the specified roles.
    """
    try:
        create_sql_user_and_roles(
            server=request.server,
            database=request.database,
            client_id=request.client_id,
            display_name=request.display_name,
            roles=request.roles
        )
        return TaskResponse(
            status="success",
            message="SQL user created and roles assigned successfully",
            details={
                "server": request.server,
                "database": request.database,
                "user": request.display_name,
                "roles": request.roles
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create SQL user: {str(e)}"
        )


# ============================================================================
# Combined Deployment Endpoint
# ============================================================================

@app.post("/run-all-deployment-tasks", response_model=TaskResponse, status_code=status.HTTP_200_OK)
async def run_all_deployment_tasks(request: DeploymentRequest):
    """
    Run all post-deployment tasks in sequence:
    1. Upload demo data to Storage
    2. Create search indexes and process data
    3. Create SQL user and assign roles
    
    This is a convenience endpoint that runs all three tasks sequentially.
    If any task fails, the process stops and returns the error.
    """
    results = {
        "upload_demo_data": None,
        "create_indexes": None,
        "create_sql_user": None
    }
    
    try:
        # Task 1: Upload demo data
        print("Starting Task 1: Upload demo data...")
        upload_demo_data(
            storage_account=request.storage_account,
            managed_identity_client_id=request.managed_identity_client_id,
            base_url=request.base_url
        )
        results["upload_demo_data"] = "success"
        print("✓ Task 1 completed")
        
        # Task 2: Create search indexes
        print("Starting Task 2: Create search indexes...")
        index_result = run_index_pipeline(
            keyvault_name=request.keyvault_name,
            managed_identity_client_id=request.managed_identity_client_id
        )
        
        failed_steps = [step for step in index_result.get("steps", []) if step.get("status") == "error"]
        if failed_steps:
            results["create_indexes"] = {"status": "failed", "details": failed_steps}
            raise Exception(f"Index creation failed: {failed_steps[0].get('error')}")
        
        results["create_indexes"] = "success"
        print("✓ Task 2 completed")
        
        # Task 3: Create SQL user
        print("Starting Task 3: Create SQL user...")
        create_sql_user_and_roles(
            server=request.sql_server,
            database=request.sql_database,
            client_id=request.backend_identity_client_id,
            display_name=request.backend_identity_display_name,
            roles=request.sql_roles
        )
        results["create_sql_user"] = "success"
        print("✓ Task 3 completed")
        
        return TaskResponse(
            status="success",
            message="All deployment tasks completed successfully",
            details=results
        )
        
    except Exception as e:
        return TaskResponse(
            status="failed",
            message=f"Deployment tasks failed: {str(e)}",
            details=results
        )


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or default to 8000
    port = int(os.getenv("PORT", "8000"))
    
    print(f"Starting Deployment API on port {port}...")
    print(f"Docs available at: http://localhost:{port}/docs")
    
    uvicorn.run(
        "deployment_api:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
