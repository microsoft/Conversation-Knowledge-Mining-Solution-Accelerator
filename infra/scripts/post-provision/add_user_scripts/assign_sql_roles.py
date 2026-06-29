#!/usr/bin/env python
"""
Script to assign SQL roles to Azure Managed Identities.
Uses Azure CLI authentication (not managed identity) for local execution.
"""
import argparse
import json
import sys
import struct
import uuid
import pyodbc
from azure.identity import AzureCliCredential

# Ensure status output (✓/✗) never raises on consoles with a non-UTF-8 codepage
# (e.g. Windows cp1252). A print encoding error must never abort role assignment.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

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
    # Convert the principal ID to bytes using UUID
    guid_bytes = uuid.UUID(principal_id).bytes_le
    # Convert to hexadecimal string
    return "0x" + guid_bytes.hex().upper()

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
            Format: [{"principalId": "...", "clientId": "...", "displayName": "...", "role": "db_datareader"}, ...]
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
            principal_id = role_assignment.get("principalId")
            client_id = role_assignment.get("clientId")
            display_name = role_assignment.get("displayName")
            role = role_assignment.get("role")
            is_service_principal = role_assignment.get("isServicePrincipal", False)
            
            if not principal_id or not display_name or not role:
                continue
            
            # Check if user already exists and capture its current SID.
            cursor.execute(
                f"SELECT CONVERT(varchar(200), sid, 1) FROM sys.database_principals "
                f"WHERE name = '{display_name}'"
            )
            row = cursor.fetchone()
            user_exists = row is not None
            existing_sid = row[0] if row else None

            # Self-heal broken managed-identity users. A user created from the object
            # (principal) id has SID = client_id_to_sid(principal_id); but SQL maps MI
            # tokens by the application (client) id, so that user can never authenticate
            # and every DB call returns 500. Detect that exact bad SID (no Graph needed,
            # since principal_id is known) and recreate the user correctly. This is
            # independent of the *deploying* identity, so it heals on both service-
            # principal and user reruns. A correctly-created MI user has the app-id SID
            # and never matches, so this never touches a healthy user.
            bad_sid = client_id_to_sid(principal_id) if principal_id else None
            if (user_exists and bad_sid and existing_sid
                    and existing_sid.upper() == bad_sid.upper()):
                # DROP + CREATE run in one transaction (autocommit is off): if the
                # recreate fails, the rollback restores the original user and its roles,
                # so we never leave the database without a usable user.
                repaired = False
                try:
                    cursor.execute(f"DROP USER [{display_name}]")
                    cursor.execute(f"CREATE USER [{display_name}] FROM EXTERNAL PROVIDER")
                    conn.commit()
                    repaired = True
                    print(f"✓ Repaired {display_name}: recreated from EXTERNAL PROVIDER "
                          f"(was object-id SID {existing_sid})")
                except Exception as ext_err:
                    conn.rollback()
                    # EXTERNAL PROVIDER unavailable (no Graph access for SQL): recreate
                    # with the correct client-id SID if the client id was supplied.
                    if client_id:
                        try:
                            cursor.execute(f"DROP USER [{display_name}]")
                            cursor.execute(
                                f"CREATE USER [{display_name}] WITH SID = "
                                f"{client_id_to_sid(client_id)}, TYPE = E"
                            )
                            conn.commit()
                            repaired = True
                            print(f"✓ Repaired {display_name}: recreated with client-id SID")
                        except Exception as e:
                            conn.rollback()
                            print(f"✗ Failed to repair {display_name}: {e}")
                    else:
                        print(f"✗ Cannot repair {display_name}: EXTERNAL PROVIDER failed "
                              f"and no clientId available. {ext_err}")
                # After a successful recreate the user has no roles yet; the role
                # assignment block below re-adds them. Either way the user now exists.
                user_exists = True if repaired else user_exists

            if not user_exists:
                created = False
                # Prefer EXTERNAL PROVIDER: SQL resolves the correct SID via MS Graph,
                # which avoids object-id vs application-id mismatches for managed identities.
                try:
                    cursor.execute(f"CREATE USER [{display_name}] FROM EXTERNAL PROVIDER")
                    conn.commit()
                    created = True
                    print(f"✓ Created user: {display_name}")
                except Exception as ext_err:
                    conn.rollback()
                    if is_service_principal:
                        # Fall back to SID-based creation when MS Graph is unavailable.
                        # Build the SID from clientId when provided (objectId only as last resort).
                        sid = client_id_to_sid(client_id) if client_id else client_id_to_sid(principal_id)
                        try:
                            cursor.execute(f"CREATE USER [{display_name}] WITH SID = {sid}, TYPE = E")
                            conn.commit()
                            created = True
                            print(f"✓ Created user: {display_name}")
                        except Exception as e:
                            print(f"✗ Failed to create user: {e}")
                    else:
                        print(f"✗ Failed to create user: {ext_err}")
                if not created:
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
        help='JSON array of role assignments: [{"principalId": "...", "displayName": "...", "role": "..."}]'
    )
    
    args = parser.parse_args()
    
    return assign_sql_roles(args.server, args.database, args.roles_json)


if __name__ == "__main__":
    sys.exit(main())
