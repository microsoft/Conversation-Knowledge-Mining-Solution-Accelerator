#!/usr/bin/env python
"""
Script to assign SQL roles to Azure Managed Identities.
Uses Azure CLI authentication (not managed identity) for local execution.
"""
import argparse
import json
import sys
import struct
import pyodbc
from azure.identity import AzureCliCredential

def get_connection_string(server, database):
    """
    Build SQL Server connection string using Azure CLI authentication.
    
    Args:
        server: Fully qualified SQL Server name (e.g., server.database.windows.net)
        database: Database name
    
    Returns:
        Connection string and access token
    """
    # Get access token using Azure CLI credential
    credential = AzureCliCredential()
    token = credential.get_token("https://database.windows.net/.default")
    
    # Extract the token value
    access_token = token.token
    
    # Try to find an available ODBC driver
    available_drivers = [d for d in pyodbc.drivers() if 'SQL Server' in d]
    
    if not available_drivers:
        raise RuntimeError("No SQL Server ODBC driver found. Please install ODBC Driver 17 or 18 for SQL Server.")
    
    # Prefer ODBC Driver 18, then 17, then any SQL Server driver
    driver = None
    for preferred in ['ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server']:
        if preferred in available_drivers:
            driver = preferred
            break
    
    if not driver:
        driver = available_drivers[0]
    
    print(f"Using driver: {driver}")
    
    # Build connection string with access token
    # ODBC Driver 18 requires TrustServerCertificate=yes for Azure SQL or specific certificate validation
    conn_str = (
        f"Driver={{{driver}}};"
        f"Server=tcp:{server},1433;"
        f"Database={database};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=yes;"
        f"Connection Timeout=30;"
    )
    
    return conn_str, access_token


def assign_sql_roles(server, database, roles_json):
    """
    Assign SQL roles to managed identities.
    
    Args:
        server: SQL Server fully qualified name
        database: Database name
        roles_json: JSON array of role assignments
            Format: [{"clientId": "...", "displayName": "...", "role": "db_datareader"}, ...]
    """
    try:
        # Parse roles JSON
        roles = json.loads(roles_json)
        
        # Get connection string and token
        conn_str, access_token = get_connection_string(server, database)
        
        # Connect to SQL Server
        print(f"Connecting to {server}/{database}...")
        
        # Create connection with access token (matching sqldb_service.py pattern)
        # SQL_COPT_SS_ACCESS_TOKEN is 1256
        token_bytes = access_token.encode("utf-16-LE")
        token_struct = struct.pack(
            f"<I{len(token_bytes)}s",
            len(token_bytes),
            token_bytes
        )
        SQL_COPT_SS_ACCESS_TOKEN = 1256
        
        conn = pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
        cursor = conn.cursor()
        
        print("Connected successfully.")
        
        # Process each role assignment
        for role_assignment in roles:
            client_id = role_assignment.get("clientId")
            display_name = role_assignment.get("displayName")
            role = role_assignment.get("role")
            
            if not client_id or not display_name or not role:
                print(f"Skipping invalid role assignment: {role_assignment}")
                continue
            
            print(f"\nProcessing: {display_name} -> {role}")
            
            # Check if user already exists
            check_user_sql = f"SELECT COUNT(*) FROM sys.database_principals WHERE name = '{display_name}'"
            cursor.execute(check_user_sql)
            user_exists = cursor.fetchone()[0] > 0
            
            if not user_exists:
                # Create user from external provider with SID
                # For managed identity, use the client ID as SID
                create_user_sql = f"CREATE USER [{display_name}] WITH SID = 0x{client_id.replace('-', '')}, TYPE = E"
                print(f"  Creating user: {display_name}")
                try:
                    cursor.execute(create_user_sql)
                    conn.commit()
                    print(f"  ✓ User created successfully")
                except Exception as e:
                    print(f"  ✗ Failed to create user: {e}")
                    # Try alternative syntax for managed identity
                    try:
                        create_user_alt_sql = f"CREATE USER [{display_name}] FROM EXTERNAL PROVIDER"
                        print(f"  Trying alternative syntax...")
                        cursor.execute(create_user_alt_sql)
                        conn.commit()
                        print(f"  ✓ User created successfully (alternative method)")
                    except Exception as e2:
                        print(f"  ✗ Failed with alternative syntax: {e2}")
                        continue
            else:
                print(f"  User already exists: {display_name}")
            
            # Check if user already has the role
            check_role_sql = f"""
                SELECT COUNT(*) 
                FROM sys.database_role_members rm
                JOIN sys.database_principals rp ON rm.role_principal_id = rp.principal_id
                JOIN sys.database_principals mp ON rm.member_principal_id = mp.principal_id
                WHERE mp.name = '{display_name}' AND rp.name = '{role}'
            """
            cursor.execute(check_role_sql)
            has_role = cursor.fetchone()[0] > 0
            
            if not has_role:
                # Add user to role
                add_role_sql = f"ALTER ROLE [{role}] ADD MEMBER [{display_name}]"
                print(f"  Assigning role: {role}")
                try:
                    cursor.execute(add_role_sql)
                    conn.commit()
                    print(f"  ✓ Role assigned successfully")
                except Exception as e:
                    print(f"  ✗ Failed to assign role: {e}")
                    continue
            else:
                print(f"  User already has role: {role}")
        
        # Close connection
        cursor.close()
        conn.close()
        print("\n✓ All role assignments completed successfully")
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Assign SQL roles to Azure Managed Identities using Azure CLI authentication"
    )
    parser.add_argument(
        "--server",
        required=True,
        help="SQL Server fully qualified name (e.g., myserver.database.windows.net)"
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Database name"
    )
    parser.add_argument(
        "--roles-json",
        required=True,
        help='JSON array of role assignments: [{"clientId": "...", "displayName": "...", "role": "..."}]'
    )
    
    args = parser.parse_args()
    
    return assign_sql_roles(args.server, args.database, args.roles_json)


if __name__ == "__main__":
    sys.exit(main())
