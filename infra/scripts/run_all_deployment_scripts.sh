#!/bin/sh

storageAccountName="${1}"
containerName="${2}"
baseUrl="${3}"
managedIdentityClientId="${4}"
setupCopyKbFiles="${5}"
setupCreateIndexScriptsUrl="${6}"
createSqlUserAndRoleScriptsUrl="${7}"
keyVaultName="${8}"
sqlServerName="${9}"
sqlDbName="${10}"
sqlUsers="${11}"

set -e  # Exit script on any error

mkdir -p /scripts
apk add --no-cache curl bash jq py3-pip gcc musl-dev libffi-dev openssl-dev python3-dev
pip install --upgrade azure-cli

# Install ODBC Drivers
apk add --no-cache --virtual .build-deps build-base unixodbc-dev
curl -s -o msodbcsql18.apk https://download.microsoft.com/download/7/6/d/76de322a-d860-4894-9945-f0cc5d6a45f8/msodbcsql18_18.4.1.1-1_amd64.apk
curl -s -o mssql-tools18.apk https://download.microsoft.com/download/7/6/d/76de322a-d860-4894-9945-f0cc5d6a45f8/mssql-tools18_18.4.1.1-1_amd64.apk
apk add --allow-untrusted msodbcsql18.apk
apk add --allow-untrusted mssql-tools18.apk

# Install PowerShell
apk add --no-cache ca-certificates less ncurses-terminfo-base krb5-libs libgcc libintl libssl3 libstdc++ tzdata userspace-rcu zlib icu-libs curl
apk -X https://dl-cdn.alpinelinux.org/alpine/edge/main add --no-cache lttng-ust openssh-client
curl -L https://github.com/PowerShell/PowerShell/releases/download/v7.5.0/powershell-7.5.0-linux-musl-x64.tar.gz -o /tmp/powershell.tar.gz
mkdir -p /opt/microsoft/powershell/7
tar zxf /tmp/powershell.tar.gz -C /opt/microsoft/powershell/7
chmod +x /opt/microsoft/powershell/7/pwsh
ln -s /opt/microsoft/powershell/7/pwsh /usr/bin/pwsh

# Copy KB files
curl -s -o /scripts/copy_kb_files.sh ${setupCopyKbFiles}
chmod +x /scripts/copy_kb_files.sh
sh -x /scripts/copy_kb_files.sh ${storageAccountName} ${containerName} ${baseUrl} ${managedIdentityClientId}

# Create Index Scripts
curl -s -o /scripts/run_create_index_scripts.sh ${setupCreateIndexScriptsUrl}
chmod +x /scripts/run_create_index_scripts.sh
sh -x /scripts/run_create_index_scripts.sh ${baseUrl} ${keyVaultName} ${managedIdentityClientId}

# Download SQL script once
curl -s -o /scripts/create-sql-user-and-role.ps1 ${createSqlUserAndRoleScriptsUrl}
chmod +x /scripts/create-sql-user-and-role.ps1

# Execute SQL scripts for users and roles
for user in $(echo ${sqlUsers} | jq -c '.[]'); do
    principalId=$(echo ${user} | jq -r '.principalId')
    principalName=$(echo ${user} | jq -r '.principalName')
    
    for role in $(echo ${user} | jq -c '.databaseRoles[]'); do
        pwsh -File /scripts/create-sql-user-and-role.ps1 \
            -SqlServerName ${sqlServerName} \
            -SqlDatabaseName ${sqlDbName} \
            -ClientId ${principalId} \
            -DisplayName ${principalName} \
            -ManagedIdentityClientId ${managedIdentityClientId} \
            -DatabaseRole ${role}
    done
done
