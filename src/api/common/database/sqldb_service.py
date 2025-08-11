from datetime import datetime
import struct

import pandas as pd
from api.models.input_models import ChartFilters
from common.config.config import Config
import logging
from helpers.azure_credential_utils import get_azure_credential_async
import pyodbc


async def get_db_connection():
    """Get a connection to the SQL database"""
    config = Config()

    server = config.sqldb_server
    database = config.sqldb_database
    username = config.sqldb_username
    password = config.sqldb_database
    driver = config.driver
    mid_id = config.mid_id

    credential = None
    try:
        credential = await get_azure_credential_async(client_id=mid_id)
        token = await credential.get_token("https://database.windows.net/.default")
        token_bytes = token.token.encode("utf-16-LE")
        token_struct = struct.pack(
            f"<I{len(token_bytes)}s",
            len(token_bytes),
            token_bytes
        )
        SQL_COPT_SS_ACCESS_TOKEN = 1256

        # Set up the connection
        connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};"
        conn = pyodbc.connect(
            connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}
        )

        logging.info("Connected using Azure Credential")
        return conn
    except pyodbc.Error as e:
        logging.error("Failed with Azure Credential: %s", str(e))
        conn = pyodbc.connect(
            f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}",
            timeout=5)

        logging.info("Connected using Username & Password")
        return conn
    finally:
        if credential and hasattr(credential, "close"):
            await credential.close()


async def adjust_processed_data_dates():
    """
    Adjusts the dates in the processed_data, km_processed_data, and processed_data_key_phrases tables
    to align with the current date.
    """
    conn = await get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        # Adjust the dates to the current date
        today = datetime.today()
        cursor.execute(
            "SELECT MAX(CAST(StartTime AS DATETIME)) FROM [dbo].[processed_data]"
        )
        max_start_time = (cursor.fetchone())[0]

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
                    "'yyyy-MM-dd HH:mm:ss')", (days_difference,)
                )
                # Commit the changes
                conn.commit()
    finally:
        if cursor:
            cursor.close()
        conn.close()


async def fetch_filters_data():
    """
    Fetches filter data from the database and organizes it into a nested JSON structure.
    """
    conn = await get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        sql_stmt = '''select 'Topic' as filter_name, mined_topic as displayValue, mined_topic as key1 from
            (SELECT distinct mined_topic from processed_data) t
            union all
            select 'Sentiment' as filter_name, sentiment as displayValue, sentiment as key1 from
            (SELECT distinct sentiment from processed_data
            union all select 'all' as sentiment) t
            union all
            select 'Satisfaction' as filter_name, satisfied as displayValue, satisfied as key1 from
            (SELECT distinct satisfied from processed_data) t
            union all
            select 'DateRange' as filter_name, date_range as displayValue, date_range as key1 from
            (SELECT 'Last 7 days' as date_range
            union all SELECT 'Last 14 days' as date_range
            union all SELECT 'Last 90 days' as date_range
            union all SELECT 'Year to Date' as date_range
            ) t'''

        cursor.execute(sql_stmt)

        rows = [tuple(row) for row in cursor.fetchall()]

        # Define column names
        column_names = [i[0] for i in cursor.description]
        df = pd.DataFrame(rows, columns=column_names)
        df.rename(columns={'key1': 'key'}, inplace=True)

        nested_json = (
            df.groupby("filter_name")
            .apply(lambda x: {
                "filter_name": x.name,
                "filter_values": x.to_dict(orient="records")
            }, include_groups=False).to_list()
        )

        filters_data = nested_json

        return filters_data
    finally:
        if cursor:
            cursor.close()
        conn.close()


async def fetch_chart_data(chart_filters: ChartFilters = ''):
    """
    Fetches chart data from the database based on the provided filters and organizes it into a nested JSON structure.
    """
    conn = await get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        where_clause = ''
        req_body = ''
        try:
            req_body = chart_filters.model_dump()
        except BaseException:
            pass
        if req_body != '':
            where_clause = ''
            for key, value in req_body.items():
                if key == 'selected_filters':
                    for k, v in value.items():
                        if k == 'Topic':
                            topics = ''
                            for topic in v:
                                topics += f''' '{topic}', '''
                            if where_clause:
                                where_clause += " and "
                            if topics:
                                where_clause += f" mined_topic  in ({topics})"
                                where_clause = where_clause.replace(', )', ')')
                        elif k == 'Sentiment':
                            for sentiment in v:
                                if sentiment != 'all':
                                    if where_clause:
                                        where_clause += " and "
                                    where_clause += f"sentiment = '{sentiment}'"

                        elif k == 'Satisfaction':
                            for satisfaction in v:
                                if where_clause:
                                    where_clause += " and "
                                where_clause += f"satisfied = '{satisfaction}'"
                        elif k == 'DateRange':
                            for date_range in v:
                                if where_clause:
                                    where_clause += " and "
                                if date_range == 'Last 7 days':
                                    where_clause += "StartTime >= DATEADD(day, -7, GETDATE())"
                                elif date_range == 'Last 14 days':
                                    where_clause += "StartTime >= DATEADD(day, -14, GETDATE())"
                                elif date_range == 'Last 90 days':
                                    where_clause += "StartTime >= DATEADD(day, -90, GETDATE())"
                                elif date_range == 'Year to Date':
                                    where_clause += "StartTime >= DATEADD(year, -1, GETDATE())"
        if where_clause:
            where_clause = f"where {where_clause} "

        sql_stmt = (
            f'''select 'TOTAL_CALLS' as id, 'Total Calls' as chart_name, 'card' as chart_type,
                'Total Calls' as name, count(*) as value, '' as unit_of_measurement from [dbo].[processed_data] {where_clause}
                union all
                select 'AVG_HANDLING_TIME' as id, 'Average Handling Time' as chart_name, 'card' as chart_type,
                'Average Handling Time' as name,
                AVG(DATEDIFF(MINUTE, StartTime, EndTime))  as value, 'mins' as unit_of_measurement from [dbo].[processed_data] {where_clause}
                union all
                select 'SATISFIED' as id, 'Satisfied' as chart_name, 'card' as chart_type, 'Satisfied' as name,
                round((CAST(SUM(CASE WHEN satisfied = 'yes' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100), 2) as value, '%' as unit_of_measurement from [dbo].[processed_data]
                {where_clause}
                union all
                select 'SENTIMENT' as id, 'Topics Overview' as chart_name, 'donutchart' as chart_type,
                sentiment as name,
                (count(sentiment) * 100 / sum(count(sentiment)) over ()) as value,
                '' as unit_of_measurement from [dbo].[processed_data]  {where_clause}
                group by sentiment
                union all
                select 'AVG_HANDLING_TIME_BY_TOPIC' as id, 'Average Handling Time By Topic' as chart_name, 'bar' as chart_type,
                mined_topic as name,
                AVG(DATEDIFF(MINUTE, StartTime, EndTime)) as value, '' as unit_of_measurement from [dbo].[processed_data] {where_clause}
                group by mined_topic
                ''')

        # charts pt1
        cursor.execute(sql_stmt)

        # rows = cursor.fetchall()
        rows = [tuple(row) for row in cursor.fetchall()]

        column_names = [i[0] for i in cursor.description]
        df = pd.DataFrame(rows, columns=column_names)

        # charts pt1
        nested_json1 = (
            df.groupby(['id', 'chart_name', 'chart_type']).apply(
                lambda x: x[['name', 'value', 'unit_of_measurement']].to_dict(orient='records'), include_groups=False).reset_index()
        )
        nested_json1.columns = ['id', 'chart_name', 'chart_type', 'chart_value']
        result1 = nested_json1.to_dict(orient='records')
        sql_stmt = f'''SELECT TOP 1 WITH TIES
                        mined_topic as name, 'TOPICS' as id, 'Trending Topics' as chart_name, 'table' as chart_type,
                        lower(sentiment) as average_sentiment,
                        COUNT(*) AS call_frequency
                    FROM [dbo].[processed_data]
                    {where_clause}
                    GROUP BY mined_topic, sentiment
                    ORDER BY ROW_NUMBER() OVER (PARTITION BY mined_topic ORDER BY COUNT(*) DESC)
                    '''

        cursor.execute(sql_stmt)

        rows = [tuple(row) for row in cursor.fetchall()]

        column_names = [i[0] for i in cursor.description]
        df = pd.DataFrame(rows, columns=column_names)

        # charts pt2
        if not df.empty:
            nested_json2 = (
                df.groupby(['id', 'chart_name', 'chart_type']).apply(
                    lambda x: x[['name', 'call_frequency', 'average_sentiment']].to_dict(orient='records'),
                    include_groups=False
                ).reset_index()
            )
            nested_json2.columns = ['id', 'chart_name', 'chart_type', 'chart_value']
            result2 = nested_json2.to_dict(orient='records')
        else:
            result2 = []

        where_clause = where_clause.replace('mined_topic', 'topic')
        sql_stmt = f'''select top 15 key_phrase as text,
            'KEY_PHRASES' as id, 'Key Phrases' as chart_name, 'wordcloud' as chart_type,
            call_frequency as size, lower(average_sentiment) as average_sentiment from
            (
                SELECT TOP 1 WITH TIES
                key_phrase,
                sentiment as average_sentiment,
                COUNT(*) AS call_frequency from
                (
                    select key_phrase, sentiment from [dbo].[processed_data_key_phrases]
                    {where_clause}
                ) t
                GROUP BY key_phrase, sentiment
                ORDER BY ROW_NUMBER() OVER (PARTITION BY key_phrase ORDER BY COUNT(*) DESC)
            ) t2
            order by call_frequency desc
            '''

        cursor.execute(sql_stmt)

        rows = [tuple(row) for row in cursor.fetchall()]

        column_names = [i[0] for i in cursor.description]
        df = pd.DataFrame(rows, columns=column_names)

        df = df.head(15)

        if not df.empty:
            nested_json3 = (
                df.groupby(['id', 'chart_name', 'chart_type']).apply(
                    lambda x: x[['text', 'size', 'average_sentiment']].to_dict(orient='records'),
                    include_groups=False
                ).reset_index()
            )
            nested_json3.columns = ['id', 'chart_name', 'chart_type', 'chart_value']
            result3 = nested_json3.to_dict(orient='records')
        else:
            result3 = []

        final_result = result1 + result2 + result3
        return final_result

    finally:
        if cursor:
            cursor.close()
        conn.close()


async def execute_sql_query(sql_query):
    """
    Executes a given SQL query and returns the result as a concatenated string.
    """
    conn = await get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql_query)
        result = ''.join(str(row) for row in cursor.fetchall())
        return result
    except Exception as e:
        logging.error("Error executing SQL query: %s", e)
        return None
    finally:
        if cursor:
            cursor.close()
        conn.close()
