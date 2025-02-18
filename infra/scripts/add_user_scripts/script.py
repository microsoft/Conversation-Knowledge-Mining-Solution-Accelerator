import pyodbc
import struct
import logging
from azure.identity import DefaultAzureCredential
import sys
import argparse

def main():

    # Create an ArgumentParser object
    parser = argparse.ArgumentParser()

    parser.add_argument('--server', type=str, required=True, help='SQL Server name')
    parser.add_argument('--database', type=str, required=True, help='Database name')
    parser.add_argument('--chartJsFuncAppName', type=str, required=True, help='Chart JS function name')
    parser.add_argument('--ragFuncAppName', type=str, required=True, help='RAG function name')

    # Parse the arguments
    args = parser.parse_args()

    # Access the arguments & Set up the connection string
    server = f"{args.server}.database.windows.net"
    database = args.database
    driver = "{ODBC Driver 17 for SQL Server}"
    chartJsFuncAppName = args.chartJsFuncAppName
    ragFuncAppName = args.ragFuncAppName

    # Get the token using DefaultAzureCredential
    # Managed Identity for mid-AzureCloud
    credential = DefaultAzureCredential()

    token_bytes = credential.get_token(
        "https://database.windows.net/.default"
    ).token.encode("utf-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    SQL_COPT_SS_ACCESS_TOKEN = (
        1256  # This connection option is defined by microsoft in msodbcsql.h
    )
    # Set up the connection
    connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};"
    conn = pyodbc.connect(
        connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}
    )

    # Create a cursor and execute SQL commands
    cursor = conn.cursor()

    sql_query_chartjs_func = f"""
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '{chartJsFuncAppName}')
BEGIN
    CREATE USER [{chartJsFuncAppName}] FROM EXTERNAL PROVIDER;
    ALTER ROLE db_datareader ADD MEMBER [{chartJsFuncAppName}]; -- Grant SELECT on all user tables and views.
    ALTER ROLE db_datawriter ADD MEMBER [{chartJsFuncAppName}]; -- Grant INSERT, UPDATE, and DELETE on all user tables and views.
END
"""
    
    sql_query_rag_func = f"""
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '{ragFuncAppName}')
BEGIN
    CREATE USER [{ragFuncAppName}] FROM EXTERNAL PROVIDER;
    ALTER ROLE db_datareader ADD MEMBER [{ragFuncAppName}]; -- Grant SELECT on all user tables and views.
    ALTER ROLE db_datawriter ADD MEMBER [{ragFuncAppName}]; -- Grant INSERT, UPDATE, and DELETE on all user tables and views.
END
"""
    # Execute SQL commands to create the user and assign the db_datareader role
    cursor.execute(sql_query_chartjs_func)
    cursor.execute(sql_query_rag_func)
    
    conn.commit()

    # Close the connection
    cursor.close()
    conn.close()


if __name__ == "__main__":
    logger = logging.getLogger("azure.identity")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    logger.addHandler(handler)

    main()
