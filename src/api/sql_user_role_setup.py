"""
Create SQL user (Azure AD) and assign database roles using Managed Identity.

This replaces the Bicep deployment script block that ran an Azure PowerShell
script to create the user and grant roles.

Callable function:
    create_sql_user_and_roles(server, database, client_id, display_name, roles)

Notes:
- Requires the Managed Identity used by this process to have Azure AD admin
  privileges on the SQL Server (set in your Bicep as administrators).
- Uses token-based auth to connect (no username/password).
"""

from __future__ import annotations

import struct
from typing import Iterable

import pyodbc
from azure.identity import DefaultAzureCredential


def _get_access_token_bytes(credential: DefaultAzureCredential) -> bytes:
    token = credential.get_token("https://database.windows.net/.default").token
    return token.encode("utf-16-LE")


def create_sql_user_and_roles(
    server: str,
    database: str,
    client_id: str,
    display_name: str,
    roles: Iterable[str],
) -> None:
    """Create an AAD contained user for the given client_id and assign roles.

    Parameters
    - server: SQL Server DNS name (e.g., 'sql-xxxxx.database.windows.net')
    - database: Target database name
    - client_id: Azure AD application (Managed Identity) client ID
    - display_name: Friendly display name to use for the contained user
    - roles: Iterable of role names like ['db_datareader','db_datawriter']
    """
    credential = DefaultAzureCredential()
    token_bytes = _get_access_token_bytes(credential)
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    SQL_COPT_SS_ACCESS_TOKEN = 1256
    driver = "{ODBC Driver 17 for SQL Server}"
    conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};"

    print(f"Connecting to SQL server '{server}', database '{database}'...")
    with pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}) as conn:
        cur = conn.cursor()

        # Ensure AAD authentication is enabled at server level (configured in Bicep)
        # Create or alter AAD user mapped to the MI client_id
        # Syntax for AAD user creation varies; for application MI, use FROM EXTERNAL PROVIDER
        created = False
        try:
            # Try simple external provider first (most common)
            cur.execute(
                f"CREATE USER [{display_name}] FROM EXTERNAL PROVIDER"
            )
            conn.commit()
            created = True
            print(f"Created AAD user '{display_name}'.")
        except Exception as e:
            conn.rollback()
            # Fallback: attempt explicit SID mapping if supported
            try:
                cur.execute(
                    f"CREATE USER [{display_name}] FROM EXTERNAL PROVIDER WITH SID = 0x{client_id.replace('-', '')}"
                )
                conn.commit()
                created = True
                print(f"Created AAD user '{display_name}' with explicit SID.")
            except Exception as e2:
                conn.rollback()
                print(f"User creation skipped or already exists: {e2}")

        # Assign roles
        for role in roles:
            try:
                cur.execute(
                    f"EXEC sp_addrolemember '{role}', '{display_name}'"
                )
                print(f"Assigned role '{role}' to '{display_name}' via sp_addrolemember.")
            except Exception:
                # sp_addrolemember may be deprecated; try ALTER ROLE ADD MEMBER
                try:
                    cur.execute(
                        f"ALTER ROLE [{role}] ADD MEMBER [{display_name}]"
                    )
                    print(f"Assigned role '{role}' to '{display_name}' via ALTER ROLE.")
                except Exception:
                    print(f"Role assignment '{role}' for '{display_name}' skipped: {e3}")
        conn.commit()
    print("SQL user/role setup complete.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 6:
        print(
            "Usage: python sql_user_role_setup.py <server> <database> <client_id> <display_name> <roles_csv>"
        )
        sys.exit(2)
    _server, _db, _client_id, _display, _roles_csv = sys.argv[1:6]
    _roles = [r.strip() for r in _roles_csv.split(",") if r.strip()]
    create_sql_user_and_roles(_server, _db, _client_id, _display, _roles)