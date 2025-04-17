from datetime import datetime
import struct
from common.config.config import Config
import logging
from azure.identity import DefaultAzureCredential
import pyodbc


def get_db_connection():
    """Get a connection to the SQL database"""
    config = Config()

    server = config.sqldb_server
    database = config.sqldb_database
    username = config.sqldb_username
    password = config.sqldb_database
    driver = config.driver
    mid_id = config.mid_id

    try:
        credential = DefaultAzureCredential(managed_identity_client_id=mid_id)

        token_bytes = credential.get_token(
            "https://database.windows.net/.default"
        ).token.encode("utf-16-LE")
        token_struct = struct.pack(
            f"<I{len(token_bytes)}s",
            len(token_bytes),
            token_bytes)
        SQL_COPT_SS_ACCESS_TOKEN = (
            1256  # This connection option is defined by microsoft in msodbcsql.h
        )

        # Set up the connection
        connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};"
        conn = pyodbc.connect(
            connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}
        )

        logging.info("Connected using Default Azure Credential")

        return conn
    except pyodbc.Error as e:
        logging.error(f"Failed with Default Credential: {str(e)}")
        conn = pyodbc.connect(
            f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}",
            timeout=5)

        logging.info("Connected using Username & Password")
        return conn


def adjust_processed_data_dates():
    with get_db_connection() as conn, conn.cursor() as cursor:
        # Adjust the dates to the current date
        today = datetime.today()
        cursor.execute(
            "SELECT MAX(CAST(StartTime AS DATETIME)) FROM [dbo].[processed_data]")
        max_start_time = cursor.fetchone()[0]

        if max_start_time:
            days_difference = (today - max_start_time).days - 1
            if days_difference != 0:
                # Update processed_data table
                cursor.execute(
                    "UPDATE [dbo].[processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd "
                    "HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')",
                    (days_difference, days_difference)
                )
                # Update km_processed_data table
                cursor.execute(
                    "UPDATE [dbo].[km_processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd "
                    "HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')",
                    (days_difference, days_difference)
                )
                # Update processed_data_key_phrases table
                cursor.execute(
                    "UPDATE [dbo].[processed_data_key_phrases] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), "
                    "'yyyy-MM-dd HH:mm:ss')", (days_difference,))
                # Commit the changes
                conn.commit()


def execute_sql_query(sql_query):
    """
    Executes a given SQL query and returns the result as a concatenated string.
    """
    with get_db_connection() as conn, conn.cursor() as cursor:
        cursor.execute(sql_query)
        return ''.join(str(row) for row in cursor.fetchall())
