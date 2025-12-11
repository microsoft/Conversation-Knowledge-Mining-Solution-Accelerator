"""
Upload demo data to Azure Storage Account.

This replaces the Bicep deployment script block that ran a bash script
(copy_kb_files.sh) to download and upload demo data files to Azure Storage.

Callable function:
    upload_demo_data(storage_account, managed_identity_client_id, base_url)

Notes:
- Downloads call_transcripts.zip and audio_data.zip from the GitHub repository
- Extracts and uploads files to the storage account's 'data' container
- Creates custom_audiodata and custom_transcripts directories
- Uses Managed Identity authentication for Azure Storage operations
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import requests
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.storage.filedatalake import DataLakeServiceClient


def upload_demo_data(
    storage_account: str,
    managed_identity_client_id: str,
    base_url: str = "https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/",
) -> None:
    """Download and upload demo data files to Azure Storage.

    Parameters:
    - storage_account: Storage account name (e.g., 'stxxxxx')
    - managed_identity_client_id: Client ID of the managed identity for authentication
    - base_url: Base URL for downloading files (defaults to GitHub main branch)
    """
    print(f"Starting upload demo data process for storage account: {storage_account}")

    # File definitions
    files_to_process = [
        {
            "zip_file": "call_transcripts.zip",
            "extracted_folder": "call_transcripts",
            "zip_url": f"{base_url}infra/data/call_transcripts.zip",
        },
        {
            "zip_file": "audio_data.zip",
            "extracted_folder": "audiodata",
            "zip_url": f"{base_url}infra/data/audio_data.zip",
        },
    ]

    # Determine if running in Azure or local dev environment
    is_azure_environment = os.getenv("WEBSITE_INSTANCE_ID") or os.getenv("AZURE_CLIENT_ID")
    
    if is_azure_environment:
        print(f"Azure environment detected. Using ManagedIdentityCredential (Client ID: {managed_identity_client_id})")
        credential = ManagedIdentityCredential(client_id=managed_identity_client_id)
    else:
        print("Local development environment detected. Using DefaultAzureCredential")
        credential = DefaultAzureCredential()

    # Create DataLakeServiceClient
    account_url = f"https://{storage_account}.dfs.core.windows.net"
    service_client = DataLakeServiceClient(account_url=account_url, credential=credential)

    # Get or create the file system (container)
    file_system_client = service_client.get_file_system_client(file_system="data")

    try:
        # Check if file system exists, if not create it
        if not file_system_client.exists():
            print("Creating 'data' file system...")
            file_system_client.create_file_system()
    except Exception as e:
        print(f"File system may already exist or error checking: {e}")

    # Process each zip file
    for file_info in files_to_process:
        zip_file = file_info["zip_file"]
        extracted_folder = file_info["extracted_folder"]
        zip_url = file_info["zip_url"]

        print(f"\n{'='*60}")
        print(f"Processing: {zip_file}")
        print(f"URL: {zip_url}")
        print(f"{'='*60}")

        # Download the zip file
        print(f"Downloading {zip_file}...")
        try:
            response = requests.get(zip_url, timeout=300)
            response.raise_for_status()
            print(f"Successfully downloaded {zip_file} ({len(response.content)} bytes)")
        except requests.RequestException as e:
            print(f"Error downloading {zip_file}: {e}")
            continue

        # Extract the zip file in memory
        print(f"Extracting {zip_file}...")
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                file_list = zip_ref.namelist()
                print(f"Found {len(file_list)} files in archive")

                # Upload each file to Azure Storage
                for file_name in file_list:
                    if file_name.endswith("/"):
                        # Skip directories
                        continue

                    print(f"  Uploading: {file_name}")
                    file_data = zip_ref.read(file_name)

                    # Construct the destination path
                    # Remove any leading directory from the file name if present
                    file_basename = os.path.basename(file_name)
                    destination_path = f"{extracted_folder}/{file_basename}"

                    # Get directory client and create if needed
                    directory_client = file_system_client.get_directory_client(extracted_folder)
                    try:
                        directory_client.create_directory()
                    except Exception:
                        pass  # Directory might already exist

                    # Upload the file
                    file_client = directory_client.get_file_client(file_basename)
                    file_client.upload_data(file_data, overwrite=True)
                    print(f"    ✓ Uploaded: {destination_path}")

        except zipfile.BadZipFile as e:
            print(f"Error extracting {zip_file}: {e}")
            continue
        except Exception as e:
            print(f"Error processing {zip_file}: {e}")
            continue

    # Create custom directories
    print(f"\n{'='*60}")
    print("Creating custom directories...")
    print(f"{'='*60}")

    custom_directories = ["custom_audiodata", "custom_transcripts"]
    for dir_name in custom_directories:
        try:
            directory_client = file_system_client.get_directory_client(dir_name)
            directory_client.create_directory()
            print(f"✓ Created directory: {dir_name}")
        except Exception as e:
            print(f"Directory '{dir_name}' may already exist or error: {e}")

    print("\n" + "="*60)
    print("Upload demo data process completed successfully!")
    print("="*60)


def main() -> int:
    """CLI entry point for running upload_demo_data standalone."""
    if len(sys.argv) < 3:
        print("Usage: python test_upload_demo_data.py <storage_account> <managed_identity_client_id> [base_url]")
        print("Example: python test_upload_demo_data.py stxxxxx abc-123-def https://raw.githubusercontent.com/...")
        return 1

    storage_account = sys.argv[1]
    managed_identity_client_id = sys.argv[2]
    base_url = sys.argv[3] if len(sys.argv) > 3 else "https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/"

    try:
        upload_demo_data(storage_account, managed_identity_client_id, base_url)
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
