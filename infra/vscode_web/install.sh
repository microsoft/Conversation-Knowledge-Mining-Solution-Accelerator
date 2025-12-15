#!/bin/bash

# Install ODBC Driver 17 for SQL Server
echo "Installing ODBC Driver 17 for SQL Server..."

# Check if running on Debian/Ubuntu
if [ -f /etc/debian_version ]; then
    # Add Microsoft repository
    curl https://packages.microsoft.com/keys/microsoft.asc | sudo tee /etc/apt/trusted.gpg.d/microsoft.asc
    
    # Detect Ubuntu version
    if command -v lsb_release &> /dev/null; then
        DISTRO_VERSION=$(lsb_release -rs)
        curl https://packages.microsoft.com/config/ubuntu/${DISTRO_VERSION}/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
    else
        # Default to Ubuntu 22.04 if unable to detect
        curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
    fi
    
    # Update package list
    sudo apt-get update
    
    # Install ODBC Driver 17 for SQL Server
    sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
    
    # Install unixODBC development headers
    sudo apt-get install -y unixodbc-dev
    
    echo "ODBC Driver 17 for SQL Server installed successfully."
else
    echo "Warning: Unsupported distribution. ODBC Driver installation skipped."
fi

# Install Python requirements
echo "Installing Python requirements..."
pip install -r requirements.txt --user -q

# Initialize Azure Developer CLI template
echo "Initializing Azure Developer CLI template..."
azd init -t microsoft/Conversation-Knowledge-Mining-Solution-Accelerator -b pk-km-sampledata-manual