"""
Deployment Orchestration Service

This service orchestrates all three deployment operations:
1. Upload demo data files to Azure Storage
2. Create search indexes and process data
3. Create SQL users and assign roles

It replaces the three separate Bicep deployment scripts with a unified API-based approach.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient
from azure.storage.filedatalake import DataLakeServiceClient
from fastapi import HTTPException, status
import requests

# Import our deployment modules
from test_upload_demo_data import upload_demo_data
from index_pipeline import run_index_pipeline
from sql_user_role_setup import create_sql_user_and_roles

logger = logging.getLogger(__name__)


class DeploymentOrchestrationService:
    """Service for orchestrating all deployment operations."""

    def __init__(self):
        """Initialize the deployment orchestration service."""
        self.base_url = os.getenv(
            "DATA_SCRIPT_BASE_URL",
            "https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/"
        )
        self.keyvault_name = os.getenv("AZURE_KEYVAULT_NAME")
        self.managed_identity_client_id = os.getenv("AZURE_MANAGED_IDENTITY_CLIENT_ID")
        self.storage_account_name = os.getenv("ADLS_ACCOUNT_NAME")
        self.sql_server_name = os.getenv("SQLDB_SERVER")
        self.sql_database_name = os.getenv("SQLDB_DATABASE")
        
    def _get_credential(self, client_id: Optional[str] = None):
        """Get Azure credential for authentication."""
        if client_id:
            return ManagedIdentityCredential(client_id=client_id)
        return DefaultAzureCredential()
    
    async def run_full_deployment(
        self,
        base_url: Optional[str] = None,
        keyvault_name: Optional[str] = None,
        managed_identity_client_id: Optional[str] = None,
        storage_account_name: Optional[str] = None,
        sql_server_name: Optional[str] = None,
        sql_database_name: Optional[str] = None,
        backend_identity_client_id: Optional[str] = None,
        backend_identity_name: Optional[str] = None
    ) -> Dict:
        """
        Execute all three deployment operations in sequence.
        
        Args:
            base_url: Base URL for downloading files
            keyvault_name: Azure Key Vault name
            managed_identity_client_id: Managed Identity Client ID for data operations
            storage_account_name: Azure Storage Account name
            sql_server_name: SQL Server name
            sql_database_name: SQL Database name
            backend_identity_client_id: Backend Managed Identity Client ID
            backend_identity_name: Backend Managed Identity Display Name
            
        Returns:
            Dict containing the execution status and outputs from all operations
        """
        # Use provided values or fall back to environment variables
        base_url = base_url or self.base_url
        keyvault_name = keyvault_name or self.keyvault_name
        managed_identity_client_id = managed_identity_client_id or self.managed_identity_client_id
        storage_account_name = storage_account_name or self.storage_account_name
        sql_server_name = sql_server_name or self.sql_server_name
        sql_database_name = sql_database_name or self.sql_database_name
        
        # Validate required parameters
        missing_params = []
        if not keyvault_name:
            missing_params.append("keyvault_name")
        if not managed_identity_client_id:
            missing_params.append("managed_identity_client_id")
        if not storage_account_name:
            missing_params.append("storage_account_name")
            
        if missing_params:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required parameters: {', '.join(missing_params)}"
            )
        
        logger.info("Starting full deployment orchestration")
        
        results = {
            "status": "success",
            "message": "All deployment operations completed successfully",
            "operations": {}
        }
        
        try:
            # Operation 1: Upload demo data files
            logger.info("Step 1/3: Uploading demo data files...")
            upload_result = await self._upload_demo_data(
                base_url, storage_account_name, managed_identity_client_id
            )
            results["operations"]["upload_data"] = upload_result
            
            # Operation 2: Create search indexes and process data
            logger.info("Step 2/3: Creating search indexes and processing data...")
            index_result = await self._create_indexes_and_process(
                base_url, keyvault_name, managed_identity_client_id
            )
            results["operations"]["create_indexes"] = index_result
            
            # Operation 3: Create SQL user and assign roles
            if sql_server_name and sql_database_name and backend_identity_client_id:
                logger.info("Step 3/3: Creating SQL user and assigning roles...")
                sql_result = await self._create_sql_user_and_roles(
                    sql_server_name,
                    sql_database_name,
                    backend_identity_client_id,
                    backend_identity_name or "backend-identity"
                )
                results["operations"]["sql_user_creation"] = sql_result
            else:
                logger.warning("Skipping SQL user creation - missing SQL parameters")
                results["operations"]["sql_user_creation"] = {
                    "status": "skipped",
                    "message": "SQL parameters not provided"
                }
            
            logger.info("Full deployment orchestration completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Deployment orchestration failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Deployment orchestration failed: {str(e)}"
            )
    
    async def _upload_demo_data(
        self,
        base_url: str,
        storage_account_name: str,
        managed_identity_client_id: str
    ) -> Dict:
        """
        Upload demo data files to Azure Storage (Operation 1).
        Uses the test_upload_demo_data module.
        """
        try:
            logger.info("Uploading demo data using test_upload_demo_data module...")
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                upload_demo_data,
                storage_account_name,
                managed_identity_client_id,
                base_url
            )
            
            return {
                "status": "success",
                "message": "Demo data uploaded successfully",
                "files_uploaded": ["call_transcripts", "audiodata"],
                "directories_created": ["custom_audiodata", "custom_transcripts"]
            }
            
        except Exception as e:
            logger.error(f"Failed to upload demo data: {str(e)}")
            raise Exception(f"Demo data upload failed: {str(e)}")
    
    async def _create_indexes_and_process(
        self,
        base_url: str,
        keyvault_name: str,
        managed_identity_client_id: str
    ) -> Dict:
        """
        Create search indexes and process data (Operation 2).
        Uses the index_pipeline module.
        """
        try:
            logger.info("Creating indexes using index_pipeline module...")
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                run_index_pipeline,
                keyvault_name,
                managed_identity_client_id
            )
            
            return {
                "status": "success",
                "message": "Search indexes created and data processed successfully",
                "pipeline_result": result
            }
                
        except Exception as e:
            logger.error(f"Failed to create indexes and process data: {str(e)}")
            raise Exception(f"Index creation and data processing failed: {str(e)}")
    
    async def _create_sql_user_and_roles(
        self,
        sql_server_name: str,
        sql_database_name: str,
        backend_identity_client_id: str,
        backend_identity_name: str
    ) -> Dict:
        """
        Create SQL user and assign roles (Operation 3).
        Uses the sql_user_role_setup module.
        """
        try:
            logger.info("Creating SQL user using sql_user_role_setup module...")
            
            # Ensure server has FQDN
            server_fqdn = sql_server_name if ".database.windows.net" in sql_server_name else f"{sql_server_name}.database.windows.net"
            
            # Define database roles
            database_roles = ["db_datareader", "db_datawriter"]
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                create_sql_user_and_roles,
                server_fqdn,
                sql_database_name,
                backend_identity_client_id,
                backend_identity_name,
                database_roles
            )
            
            return {
                "status": "success",
                "message": f"SQL user '{backend_identity_name}' created and roles assigned successfully",
                "user": backend_identity_name,
                "roles": database_roles
            }
            
        except Exception as e:
            logger.error(f"Failed to create SQL user and assign roles: {str(e)}")
            raise Exception(f"SQL user creation failed: {str(e)}")
    
    async def _download_file(self, url: str, destination: Path):
        """Download a file from URL to destination."""
        response = requests.get(url)
        response.raise_for_status()
        destination.write_bytes(response.content)
        logger.debug(f"Downloaded {destination.name}")
    
    async def _run_command(self, cmd: List[str], cwd: str) -> str:
        """Run a shell command and return output."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise subprocess.CalledProcessError(
                process.returncode,
                cmd,
                stdout,
                error_msg
            )
        
        return stdout.decode()
    
    async def get_deployment_status(self) -> Dict:
        """Get the current status of the deployment service."""
        return {
            "status": "ready",
            "message": "Deployment orchestration service is ready",
            "configured": {
                "keyvault_name": bool(self.keyvault_name),
                "managed_identity_client_id": bool(self.managed_identity_client_id),
                "storage_account_name": bool(self.storage_account_name),
                "sql_server_name": bool(self.sql_server_name),
                "sql_database_name": bool(self.sql_database_name)
            }
        }
