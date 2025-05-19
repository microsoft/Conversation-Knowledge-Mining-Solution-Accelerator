#!/bin/bash

# Parameters
SqlServerName="$1"
SqlDatabaseName="$2"
ClientId="$3"
DisplayName="$4"
UserManagedIdentityClientId="$5"
DatabaseRole="$6"

# Authenticate with Azure
echo "Authenticating with Managed Identity..."
az login --identity --client-id ${UserManagedIdentityClientId}

# Construct the SQL query
SQL_QUERY="
DECLARE @username nvarchar(max) = N'$DisplayName';
DECLARE @clientId uniqueidentifier = '$ClientId';
DECLARE @sid NVARCHAR(max) = CONVERT(VARCHAR(max), CONVERT(VARBINARY(16), @clientId), 1);
DECLARE @cmd NVARCHAR(max) = N'CREATE USER [' + @username + '] WITH SID = ' + @sid + ', TYPE = E;';
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = @username)
BEGIN
    EXEC(@cmd)
END
EXEC sp_addrolemember '$DatabaseRole', @username;
"

# Create heredoc for the SQL query
SQL_QUERY_FINAL=$(cat <<EOF
$SQL_QUERY
EOF
)

echo "Running on Linux or macOS, will use access token"
mkdir -p usersql
# Get an access token for the Azure SQL Database
echo "Retrieving access token..."
az account get-access-token --resource https://database.windows.net --output tsv | cut -f 1 | tr -d '\n' | iconv -f ascii -t UTF-16LE > usersql/tokenFile
if [ $? -ne 0 ]; then
    echo "Failed to retrieve access token."
    exit 1
fi
errorFlag=false
# Execute the SQL query
echo "Executing SQL query..."
sqlcmd -S "$SqlServerName.database.windows.net" -d "$SqlDatabaseName" -G -P usersql/tokenFile -Q "$SQL_QUERY_FINAL" || {
    echo "Failed to execute SQL query."
    errorFlag=true
}
#delete the usersql directory
rm -rf usersql
if [ "$errorFlag" = true ]; then
    exit 1
fi

echo "SQL user and role assignment completed successfully."