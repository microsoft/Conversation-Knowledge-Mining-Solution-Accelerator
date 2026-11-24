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


def client_id_to_sid(client_id: str) -> str:
    """
    Convert a managed identity's client/application ID to a SQL Server SID.
    This allows creating users without requiring MS Graph permissions.

    Args:
        client_id: The client/application ID (GUID), not the Entra object ID

    Returns:
        str: Hexadecimal SID string for use in CREATE USER statement
    """
    guid_bytes = uuid.UUID(client_id).bytes_le
    return "0x" + guid_bytes.hex().upper()


def connect_with_token(server: str, database: str, credential: AzureCliCredential):
    """
    Connect to SQL Server using Azure CLI credential token.
    """
    token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    for driver in ["{ODBC Driver 18 for SQL Server}", "{ODBC Driver 17 for SQL Server}"]:
        try:
            conn_str = (
                f"DRIVER={driver};SERVER={server};DATABASE={database};"
                "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
            )
            return pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
        except pyodbc.Error as error:
            if error.args[0] not in ("IM002", "IM003"):
                raise
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
    conn = None
    cursor = None
    try:
        if not roles:
            raise ValueError("No SQL role assignments supplied")
        credential = AzureCliCredential()
        conn = connect_with_token(server, database, credential)
        cursor = conn.cursor()

        for role_assignment in roles:
            principal_id = role_assignment.get("principalId")
            display_name = role_assignment.get("displayName")
            role = role_assignment.get("role")
            is_service_principal = role_assignment.get("isServicePrincipal", False)

            if not principal_id or not display_name or not role:
                raise ValueError("Each SQL assignment requires principalId, displayName and role")

            cursor.execute(
                "SELECT sid, type FROM sys.database_principals WHERE name = ?", display_name
            )
            existing_user = cursor.fetchone()
            sid = client_id_to_sid(principal_id) if is_service_principal else None
            if existing_user and is_service_principal:
                if bytes(existing_user[0]) != bytes.fromhex(sid[2:]) or existing_user[1] != "E":
                    raise ValueError(
                        f"SQL user '{display_name}' has the wrong SID/type for managed identity "
                        f"client ID {principal_id}. Repair the contained user mapping before retrying; "
                        "adding roles does not correct the SID."
                    )

            quoted_user = "[" + display_name.replace("]", "]]") + "]"
            quoted_role = "[" + role.replace("]", "]]") + "]"
            if not existing_user:
                if is_service_principal:
                    create_user_sql = f"CREATE USER {quoted_user} WITH SID = {sid}, TYPE = E"
                else:
                    create_user_sql = f"CREATE USER {quoted_user} FROM EXTERNAL PROVIDER"
                cursor.execute(create_user_sql)

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
                cursor.execute(f"ALTER ROLE {quoted_role} ADD MEMBER {quoted_user}")

        conn.commit()
        print("SQL identity mappings and role assignments verified.")
        return 0

    except Exception as e:
        if conn is not None:
            conn.rollback()
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


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
