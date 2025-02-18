from datetime import datetime
import azure.functions as func
from azure.identity import DefaultAzureCredential
import logging
import json
import os
import pyodbc
import pandas as pd
import struct
# from dotenv import load_dotenv
# load_dotenv()

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# get database connection
def get_db_connection():
    driver = "{ODBC Driver 17 for SQL Server}"
    server = os.environ.get("SQLDB_SERVER")
    database = os.environ.get("SQLDB_DATABASE")
    username = os.environ.get("SQLDB_USERNAME")
    password = os.environ.get("SQLDB_PASSWORD")

    # Attempt connection using Username & Password
    try:
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

        logging.info("Connected using Default Azure Credential")

        return conn
    except pyodbc.Error as e:
        logging.error(f"Failed with Default Credential: {str(e)}")
        conn = pyodbc.connect(
            f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}",
            timeout=5
        )
        logging.info("Connected using Username & Password")
        return conn

# add post methods - filters will come in the body (request.body), if body is not empty, update the where clause in the query
@app.route(route="get_metrics", methods=["GET","POST"], auth_level=func.AuthLevel.ANONYMOUS)
def get_metrics(req: func.HttpRequest) -> func.HttpResponse:
# select distinct mined_topic from processed_data
    # distinct sentiment from processed_data... union all the results
    data_type = req.params.get('data_type')
    if not data_type:
        data_type = 'filters'

    conn = get_db_connection()
    cursor = conn.cursor()

    # Adjust the dates to the current date
    today = datetime.today()
    cursor.execute("SELECT MAX(CAST(StartTime AS DATETIME)) FROM [dbo].[processed_data]")
    max_start_time = cursor.fetchone()[0]
    
    if max_start_time:
        days_difference = (today - max_start_time).days - 1
        if days_difference != 0:
            # Update processed_data table
            cursor.execute(
                "UPDATE [dbo].[processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')",
                (days_difference, days_difference)
            )
            # Update km_processed_data table
            cursor.execute(
                "UPDATE [dbo].[km_processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')",
                (days_difference, days_difference)
            )
            # Update processed_data_key_phrases table
            cursor.execute(
                "UPDATE [dbo].[processed_data_key_phrases] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss')",
                (days_difference,)
            )
            # Commit the changes
            conn.commit()
            
    if data_type == 'filters':
 
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
        #rows = cursor.fetchall()

        # Convert pyodbc.Row objects to tuples
        rows = [tuple(row) for row in cursor.fetchall()]

        # Define column names
        column_names = [i[0] for i in cursor.description]
        df = pd.DataFrame(rows, columns=column_names)
        df.rename(columns={'key1':'key'}, inplace=True)

        nested_json = (
        df.groupby("filter_name")
        .apply(lambda x: {
            "filter_name": x.name,
            "filter_values": x.drop(columns="filter_name").to_dict(orient="records")
        }).to_list()
        )

        # print(nested_json)
        filters_data = nested_json
        
        json_response = json.dumps(filters_data)
        return func.HttpResponse(json_response, mimetype="application/json", status_code=200)
    # where clauses for the charts data 
    elif data_type == 'charts': 
        where_clause = ''
        req_body = ''
        try:
            req_body = req.get_json()
        except:
            pass
        if req_body != '': 
            where_clause = ''
            for key, value in req_body.items():
                if key == 'selected_filters':
                    for k, v in value.items():
                        if k == 'Topic':
                            topics = ''
                            for topic in v:
                                topics += (f''' '{topic}', ''')
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
            where_clause = (f"where {where_clause} ")

        sql_stmt = (f'''select 'TOTAL_CALLS' as id, 'Total Calls' as chart_name, 'card' as chart_type,
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

        #charts pt1
        cursor.execute(sql_stmt)

        # rows = cursor.fetchall()
        rows = [tuple(row) for row in cursor.fetchall()]

        column_names = [i[0] for i in cursor.description]
        df = pd.DataFrame(rows, columns=column_names)

        # charts pt1
        nested_json1 = (
            df.groupby(['id', 'chart_name', 'chart_type']).apply(lambda x: x[['name', 'value', 'unit_of_measurement']].to_dict(orient='records')).reset_index(name='chart_value')
            
        )
        result1 = nested_json1.to_dict(orient='records')
        # json_data1 = json.dumps(result, indent=4)
        # print(json_data)

        # sql_stmt = (f'''select mined_topic as name, 'TOPICS' as id, 'Trending Topics' as chart_name, 'table' as chart_type, call_frequency,
        # case when avg_sentiment < 1 THEN 'negative' when avg_sentiment between 1 and 2 THEN 'neutral' 
        # when avg_sentiment >= 2 THEN 'positive' end as average_sentiment
        # from
        # (
        #     select mined_topic, AVG(sentiment_int) as avg_sentiment, sum(n) as call_frequency
        #     from 
        #     (
        #         select TRIM(mined_topic) as mined_topic, 1 as n,
        #         CASE sentiment WHEN 'positive' THEN 3 WHEN 'neutral' THEN 2 WHEN 'negative' THEN 1 end as sentiment_int
        #         from [dbo].[processed_data] {where_clause} 
        #     ) t        
        #     group by mined_topic
        # ) t1''')

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

        # rows = cursor.fetchall()
        rows = [tuple(row) for row in cursor.fetchall()]

        column_names = [i[0] for i in cursor.description]
        df = pd.DataFrame(rows, columns=column_names)

        # charts pt2
        nested_json2 = (
            df.groupby(['id', 'chart_name', 'chart_type']).apply(lambda x: x[['name', 'call_frequency', 'average_sentiment']].to_dict(orient='records')).reset_index(name='chart_value')
            
        )
        result2 = nested_json2.to_dict(orient='records')

        # where_clause = ''
        
        # sql_stmt = (f'''select key_phrase as text, 'KEY_PHRASES' as id, 'Key Phrases' as chart_name, 'wordcloud' as chart_type, call_frequency as size,
        # case when avg_sentiment < 1 THEN 'negative' when avg_sentiment between 1 and 2 THEN 'neutral' 
        # when avg_sentiment >= 2 THEN 'positive' end as average_sentiment
        # from
        # (
        #     select top(100) key_phrase, AVG(sentiment_int) as avg_sentiment, sum(n) as call_frequency 
        #     from 
        #     (
        #         select TRIM(key_phrase) as key_phrase, 1 as n,
        #         CASE sentiment WHEN 'positive' THEN 3 WHEN 'neutral' THEN 2 WHEN 'negative' THEN 1 end as sentiment_int
        #         from 
		# 		( select key_phrase, k.sentiment, mined_topic from [dbo].[processed_data_key_phrases] as k
		# 		   inner join [dbo].[processed_data] as p on k.ConversationId = p.ConversationId 
		# 		   {where_clause}
		# 		) t2
        #     ) t
    
        #     group by key_phrase
        #     order by call_frequency desc
        # ) t1''')

        # where_clause = where_clause.replace('sentiment', 'k.sentiment')
        # where_clause = where_clause.replace('StartTime', 'k.StartTime')
        # sql_stmt =  f'''select top 30 key_phrase as text, 
        #     'KEY_PHRASES' as id, 'Key Phrases' as chart_name, 'wordcloud' as chart_type,
        #     call_frequency as size, lower(average_sentiment) as average_sentiment from 
        #     (
        #         SELECT TOP 1 WITH TIES
        #         key_phrase,
        #         sentiment as average_sentiment,
        #         COUNT(*) AS call_frequency from
        #         (
        #             select key_phrase, k.sentiment, mined_topic from [dbo].[processed_data_key_phrases] as k
        #             inner join [dbo].[processed_data] as p on k.ConversationId = p.ConversationId 
        #             {where_clause}
        #         ) t
        #         GROUP BY key_phrase, sentiment
        #         ORDER BY ROW_NUMBER() OVER (PARTITION BY key_phrase ORDER BY COUNT(*) DESC)
        #     ) t2
        #     order by call_frequency desc
        #     '''

        # where_clause = where_clause.replace('sentiment', 'k.sentiment')
        where_clause = where_clause.replace('mined_topic', 'topic')
        sql_stmt =  f'''select top 15 key_phrase as text, 
            'KEY_PHRASES' as id, 'Key Phrases' as chart_name, 'wordcloud' as chart_type,
            call_frequency as size, lower(average_sentiment) as average_sentiment from 
            (
                SELECT TOP 1 WITH TIES
                key_phrase,
                sentiment as average_sentiment,
                COUNT(*) AS call_frequency from
                (
                    select key_phrase, sentiment from [dbo].[processed_data_key_phrases]  
                    { where_clause}
                ) t
                GROUP BY key_phrase, sentiment
                ORDER BY ROW_NUMBER() OVER (PARTITION BY key_phrase ORDER BY COUNT(*) DESC)
            ) t2
            order by call_frequency desc
            '''

        cursor.execute(sql_stmt)

        # rows = cursor.fetchall()
        rows = [tuple(row) for row in cursor.fetchall()]

        column_names = [i[0] for i in cursor.description]
        df = pd.DataFrame(rows, columns=column_names)
        
        df = df.head(15)

        nested_json3 = (
            df.groupby(['id', 'chart_name', 'chart_type']).apply(lambda x: x[['text', 'size', 'average_sentiment']].to_dict(orient='records')).reset_index(name='chart_value')
            
        )
        result3 = nested_json3.to_dict(orient='records')

        final_result = result1 + result2 + result3
        json_response = json.dumps(final_result, indent=4)
        # # print(final_json_data)
        
        return func.HttpResponse(json_response, mimetype="application/json", status_code=200)
    
    cursor.close()
    conn.close()
