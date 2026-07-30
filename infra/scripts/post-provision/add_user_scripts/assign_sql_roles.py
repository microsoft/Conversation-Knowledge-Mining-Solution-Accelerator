#!/usr/bin/env python
"""
Script to assign SQL roles to Azure Managed Identities.
Uses Azure CLI authentication (the deployer, who is the SQL AAD admin) for local execution.
"""
import argparse
import json
import sys
import struct
import uuid
import pyodbc
from azure.identity import AzureCliCredential

SQL_COPT_SS_ACCESS_TOKEN = 1256


def client_id_to_sid(principal_id: str) -> str:
    """
    Convert a principal ID (GUID) to a SQL Server SID format.
    This allows creating users without requiring MS Graph permissions.

    Args:
        principal_id: The principal ID (GUID) of the managed identity

    Returns:
        str: Hexadecimal SID string for use in CREATE USER statement
    """
    guid_bytes = uuid.UUID(principal_id).bytes_le
    return "0x" + guid_bytes.hex().upper()


def connect_with_token(server: str, database: str, credential: AzureCliCredential):
    """
    Connect to SQL Server using Azure CLI credential token.
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


def assign_sql_roles(server, database, roles):
    """
    Assign SQL roles to managed identities.

    Args:
        server: SQL Server fully qualified name
        database: Database name
        roles: list of role assignments
            Format: [{"principalId": "...", "displayName": "...", "role": "db_datareader",
                      "isServicePrincipal": true}, ...]
    """
    try:
        credential = AzureCliCredential()
        conn = connect_with_token(server, database, credential)
        cursor = conn.cursor()

        for role_assignment in roles:
            principal_id = role_assignment.get("principalId")
            display_name = role_assignment.get("displayName")
            role = role_assignment.get("role")
            is_service_principal = role_assignment.get("isServicePrincipal", False)

            if not principal_id or not display_name or not role:
                continue

            # Check if user already exists
            cursor.execute(
                "SELECT COUNT(*) FROM sys.database_principals WHERE name = ?", display_name
            )
            user_exists = cursor.fetchone()[0] > 0

            if not user_exists:
                try:
                    if is_service_principal:
                        # SID-based create avoids needing MS Graph permissions on SQL Server
                        sid = client_id_to_sid(principal_id)
                        create_user_sql = f"CREATE USER [{display_name}] WITH SID = {sid}, TYPE = E"
                    else:
                        create_user_sql = f"CREATE USER [{display_name}] FROM EXTERNAL PROVIDER"
                    cursor.execute(create_user_sql)
                    conn.commit()
                    print(f"Created user: {display_name}")
                except Exception as e:
                    print(f"Failed to create user {display_name}: {e}")
                    continue

            # Check if user already has the role
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM sys.database_role_members rm
                JOIN sys.database_principals rp ON rm.role_principal_id = rp.principal_id
                JOIN sys.database_principals mp ON rm.member_principal_id = mp.principal_id
                WHERE mp.name = ? AND rp.name = ?
                """,
                display_name,
                role,
            )
            has_role = cursor.fetchone()[0] > 0

            if not has_role:
                try:
                    cursor.execute(f"ALTER ROLE [{role}] ADD MEMBER [{display_name}]")
                    conn.commit()
                    print(f"Assigned {role} to {display_name}")
                except Exception as e:
                    print(f"Failed to assign {role} to {display_name}: {e}")
                    continue

        cursor.close()
        conn.close()
        return 0

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Assign SQL roles to Azure Managed Identities using Azure CLI authentication"
    )
    parser.add_argument("--server", required=True, help="SQL Server FQDN (e.g. myserver.database.windows.net)")
    parser.add_argument("--database", required=True, help="Database name")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--roles-json", help='JSON array of role assignments')
    group.add_argument("--roles-file", help="Path to a file containing the JSON array of role assignments")

    args = parser.parse_args()

    if args.roles_file:
        with open(args.roles_file, "r", encoding="utf-8") as f:
            roles = json.load(f)
    else:
        roles = json.loads(args.roles_json)

    return assign_sql_roles(args.server, args.database, roles)


if __name__ == "__main__":
    sys.exit(main())
