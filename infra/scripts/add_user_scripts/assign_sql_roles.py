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

SQL_COPT_SS_ACCESS_TOKEN = 1256

def connect_with_token(server: str, database: str, credential: AzureCliCredential):
    """
    Connect to SQL Server using Azure CLI credential token.
    
    Args:
        server: SQL Server fully qualified name
        database: Database name
        credential: Azure CLI credential for authentication
        
    Returns:
        pyodbc.Connection: Database connection object
        
    Raises:
        RuntimeError: If unable to connect with available ODBC drivers
    """
    token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    for driver in ["{ODBC Driver 18 for SQL Server}", "{ODBC Driver 17 for SQL Server}"]:
        try:
            conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};"
            return pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
        except pyodbc.Error:
            continue
    raise RuntimeError("Unable to connect using ODBC Driver 18 or 17. Install driver msodbcsql17/18.")


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

        credential = AzureCliCredential()
        
        # Connect to SQL Server
        conn = connect_with_token(server, database, credential)
        cursor = conn.cursor()
        
        # Process each role assignment
        for role_assignment in roles:
            client_id = role_assignment.get("clientId")
            display_name = role_assignment.get("displayName")
            role = role_assignment.get("role")
            
            if not client_id or not display_name or not role:
                continue
            
            # Check if user already exists
            check_user_sql = f"SELECT COUNT(*) FROM sys.database_principals WHERE name = '{display_name}'"
            cursor.execute(check_user_sql)
            user_exists = cursor.fetchone()[0] > 0
            
            if not user_exists:
                # Create user from external provider
                create_user_sql = f"CREATE USER [{display_name}] FROM EXTERNAL PROVIDER"
                try:
                    cursor.execute(create_user_sql)
                    conn.commit()
                    print(f"✓ Created user: {display_name}")
                except Exception as e:
                    print(f"✗ Failed to create user: {e}")
                    continue
            
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
                try:
                    cursor.execute(add_role_sql)
                    conn.commit()
                    print(f"✓ Assigned {role} to {display_name}")
                except Exception as e:
                    print(f"✗ Failed to assign {role}: {e}")
                    continue
        
        # Close connection
        cursor.close()
        conn.close()
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
