"""
Data processing script for conversation knowledge mining.

This module processes call transcripts using Azure Content Understanding,
generates embeddings, and stores processed data in SQL Server and Azure Search.
"""
import argparse
import asyncio
import json
import os
import re
import struct
from datetime import datetime, timedelta
from urllib.parse import urlparse

import pandas as pd
import pyodbc
from azure.ai.inference.aio import EmbeddingsClient
from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity.aio import AzureCliCredential as AsyncAzureCliCredential
from azure.identity import AzureCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.storage.filedatalake import DataLakeServiceClient

from agent_framework import ChatAgent
from agent_framework.azure import AzureAIClient

from content_understanding_client import AzureContentUnderstandingClient

# Get parameters from command line
p = argparse.ArgumentParser()
p.add_argument("--search_endpoint", required=True)
p.add_argument("--ai_project_endpoint", required=True)
p.add_argument("--deployment_model", required=True)
p.add_argument("--embedding_model", required=True)
p.add_argument("--storage_account_name", required=True)
p.add_argument("--sql_server", required=True)
p.add_argument("--sql_database", required=True)
p.add_argument("--cu_endpoint", required=True)
p.add_argument("--cu_api_version", required=True)
p.add_argument("--usecase", required=True)
p.add_argument("--solution_name", required=True)
args = p.parse_args()

SEARCH_ENDPOINT = args.search_endpoint
AI_PROJECT_ENDPOINT = args.ai_project_endpoint
DEPLOYMENT_MODEL = args.deployment_model
EMBEDDING_MODEL = args.embedding_model
STORAGE_ACCOUNT_NAME = args.storage_account_name
SQL_SERVER = args.sql_server
SQL_DATABASE = args.sql_database
CU_ENDPOINT = args.cu_endpoint
CU_API_VERSION = args.cu_api_version
USE_CASE = args.usecase
SOLUTION_NAME = args.solution_name

# Construct agent names from solution name (matching 01_create_agents.py pattern)
TOPIC_MINING_AGENT_NAME = f"KM-TopicMiningAgent-{SOLUTION_NAME}"
TOPIC_MAPPING_AGENT_NAME = f"KM-TopicMappingAgent-{SOLUTION_NAME}"

FILE_SYSTEM_CLIENT_NAME = "data"
DIRECTORY = 'call_transcripts'
INDEX_NAME = "call_transcripts_index"

if USE_CASE == "telecom":
    SAMPLE_IMPORT_FILE = 'infra/data/telecom/sample_search_index_data.json'
    SAMPLE_PROCESSED_DATA_FILE = 'infra/data/telecom/sample_processed_data.json'
    SAMPLE_PROCESSED_DATA_KEY_PHRASES_FILE = 'infra/data/telecom/sample_processed_data_key_phrases.json'
else:
    SAMPLE_IMPORT_FILE = 'infra/data/IT_helpdesk/sample_search_index_data.json'
    SAMPLE_PROCESSED_DATA_FILE = 'infra/data/IT_helpdesk/sample_processed_data.json'
    SAMPLE_PROCESSED_DATA_KEY_PHRASES_FILE = 'infra/data/IT_helpdesk/sample_processed_data_key_phrases.json'

# Azure DataLake setup
account_url = f"https://{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net"
credential = AzureCliCredential(process_timeout=30)
service_client = DataLakeServiceClient(account_url, credential=credential, api_version='2023-01-03')
file_system_client = service_client.get_file_system_client(FILE_SYSTEM_CLIENT_NAME)
directory_name = DIRECTORY
paths = list(file_system_client.get_paths(path=directory_name))

# Azure Search setup
search_credential = AzureCliCredential(process_timeout=30)
search_client = SearchClient(SEARCH_ENDPOINT, INDEX_NAME, search_credential)
index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=search_credential)

# SQL Server setup
try:
    driver = "{ODBC Driver 18 for SQL Server}"
    token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    connection_string = f"DRIVER={driver};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
    conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
    cursor = conn.cursor()
except: 
    driver = "{ODBC Driver 17 for SQL Server}"
    token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    connection_string = f"DRIVER={driver};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
    conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
    cursor = conn.cursor()

# SQL data type mapping for pandas to SQL conversion
sql_data_types = {
    'int64': 'INT',
    'float64': 'DECIMAL(10,2)',
    'object': 'NVARCHAR(MAX)',
    'bool': 'BIT',
    'datetime64[ns]': 'DATETIME2(6)',
    'timedelta[ns]': 'TIME'
}


# Helper function to generate and execute optimized SQL insert scripts
def generate_sql_insert_script(df, table_name, columns, sql_file_name):
    """
    Generate and execute optimized SQL INSERT script from DataFrame.

    Args:
        df: pandas DataFrame with data to insert
        table_name: Target SQL table name
        columns: List of column names
        sql_file_name: Output SQL file name

    Returns:
        Number of records inserted
    """
    if df.empty:
        print(f"No data to insert into {table_name}.")
        return 0

    # Prepare output directory
    sql_output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'index_scripts', 'sql_files'))
    os.makedirs(sql_output_dir, exist_ok=True)
    output_file_path = os.path.join(sql_output_dir, sql_file_name)

    # Generate INSERT statements
    insert_sql = f"INSERT INTO {table_name} ([{'],['.join(columns)}]) VALUES "
    values_list = []
    sql_commands = []
    count = 0

    for _, row in df.iterrows():
        values = []
        for value in row:
            if pd.isna(value) or value is None:
                values.append('NULL')
            elif isinstance(value, str):
                str_value = value.replace("'", "''")
                values.append(f"'{str_value}'")
            elif isinstance(value, bool):
                values.append("1" if value else "0")
            else:
                values.append(str(value))

        count += 1
        values_list.append(f"({', '.join(values)})")

        # Batch inserts in groups of 1000 for performance
        if count == 1000:
            insert_sql += ",\n".join(values_list) + ";\n"
            sql_commands.append(insert_sql)
            # Reset for next batch
            insert_sql = f"INSERT INTO {table_name} ([{'],['.join(columns)}]) VALUES "
            values_list = []
            count = 0

    # Handle remaining records
    if values_list:
        insert_sql += ",\n".join(values_list) + ";\n"
        sql_commands.append(insert_sql)

    # Write SQL script to file
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(sql_commands))

    # Execute SQL script
    with open(output_file_path, 'r', encoding='utf-8') as f:
        sql_script = f.read()
        cursor.execute(sql_script)
    conn.commit()

    record_count = len(df)
    print(f"Inserted {record_count} records into {table_name} using optimized SQL script.")
    return record_count


# Content Understanding client
cu_credential = AzureCliCredential(process_timeout=30)
cu_token_provider = get_bearer_token_provider(cu_credential, "https://cognitiveservices.azure.com/.default")
cu_client = AzureContentUnderstandingClient(
    endpoint=CU_ENDPOINT,
    api_version=CU_API_VERSION,
    token_provider=cu_token_provider
)
ANALYZER_ID = "ckm-json"

# Azure AI Foundry (Inference) embeddings client (async)
inference_endpoint = f"https://{urlparse(AI_PROJECT_ENDPOINT).netloc}/models"


# Utility functions
async def get_embeddings_async(text: str, embeddings_client):
    """Get embeddings using async EmbeddingsClient."""
    try:
        resp = await embeddings_client.embed(model=EMBEDDING_MODEL, input=[text])
        return resp.data[0].embedding
    except Exception as e:
        print(f"Error getting embeddings: {e}")
        raise


# Function: Clean Spaces with Regex
def clean_spaces_with_regex(text):
    # Use a regular expression to replace multiple spaces with a single space
    cleaned_text = re.sub(r'\s+', ' ', text)
    # Use a regular expression to replace consecutive dots with a single dot
    cleaned_text = re.sub(r'\.{2,}', '.', cleaned_text)
    return cleaned_text


def chunk_data(text, tokens_per_chunk=1024):
    text = clean_spaces_with_regex(text)

    sentences = text.split('. ')  # Split text into sentences
    chunks = []
    current_chunk = ''
    current_chunk_token_count = 0

    # Iterate through each sentence
    for sentence in sentences:
        # Split sentence into tokens
        tokens = sentence.split()

        # Check if adding the current sentence exceeds tokens_per_chunk
        if current_chunk_token_count + len(tokens) <= tokens_per_chunk:
            # Add the sentence to the current chunk
            if current_chunk:
                current_chunk += '. ' + sentence
            else:
                current_chunk += sentence
            current_chunk_token_count += len(tokens)
        else:
            # Add current chunk to chunks list and start a new chunk
            chunks.append(current_chunk)
            current_chunk = sentence
            current_chunk_token_count = len(tokens)

    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


async def prepare_search_doc(content, document_id, path_name, embeddings_client):
    chunks = chunk_data(content)
    docs = []
    for idx, chunk in enumerate(chunks, 1):
        chunk_id = f"{document_id}_{str(idx).zfill(2)}"
        try:
            v_contentVector = await get_embeddings_async(str(chunk), embeddings_client)
        except:
            await asyncio.sleep(30)
            try:
                v_contentVector = await get_embeddings_async(str(chunk), embeddings_client)
            except:
                v_contentVector = []
        docs.append({
            "id": chunk_id,
            "chunk_id": chunk_id,
            "content": chunk,
            "sourceurl": path_name.split('/')[-1],
            "contentVector": v_contentVector
        })
    return docs


# Database table creation
def create_tables():
    cursor.execute('DROP TABLE IF EXISTS processed_data')
    cursor.execute("""CREATE TABLE processed_data (
        ConversationId varchar(255) NOT NULL PRIMARY KEY,
        EndTime varchar(255),
        StartTime varchar(255),
        Content varchar(max),
        summary varchar(3000),
        satisfied varchar(255),
        sentiment varchar(255),
        topic varchar(255),
        key_phrases nvarchar(max),
        complaint varchar(255),
        mined_topic varchar(255)
    );""")
    cursor.execute('DROP TABLE IF EXISTS processed_data_key_phrases')
    cursor.execute("""CREATE TABLE processed_data_key_phrases (
        ConversationId varchar(255),
        key_phrase varchar(500),
        sentiment varchar(255),
        topic varchar(255),
        StartTime varchar(255)
    );""")
    conn.commit()


create_tables()


# Process files and insert into DB and Search
async def process_files():
    """Process all files with async embeddings client."""
    conversationIds, docs, counter = [], [], 0

    # Create embeddings client for entire processing session
    async with (
        AsyncAzureCliCredential(process_timeout=30) as async_cred,
        EmbeddingsClient(
            endpoint=inference_endpoint,
            credential=async_cred,
            credential_scopes=["https://ai.azure.com/.default"],
        ) as embeddings_client
    ):
        for path in paths:
            file_client = file_system_client.get_file_client(path.name)
            data_file = file_client.download_file()
            data = data_file.readall()
            try:
                response = cu_client.begin_analyze(ANALYZER_ID, file_location="", file_data=data)
                result = cu_client.poll_result(response)
                file_name = path.name.split('/')[-1].replace("%3A", "_")
                if USE_CASE == 'telecom':
                    start_time = file_name.replace(".json", "")[-19:]
                    timestamp_format = "%Y-%m-%d %H_%M_%S"
                else:
                    start_time = file_name.replace(".json", "")[-16:]
                    timestamp_format = "%Y-%m-%d%H%M%S"
                start_timestamp = datetime.strptime(start_time, timestamp_format)
                conversation_id = file_name.split('convo_', 1)[1].split('_')[0]
                conversationIds.append(conversation_id)
                duration = int(result['result']['contents'][0]['fields']['Duration']['valueString'])
                end_timestamp = str(start_timestamp + timedelta(seconds=duration)).split(".")[0]
                start_timestamp = str(start_timestamp).split(".")[0]
                fields = result['result']['contents'][0]['fields']
                summary = fields['summary']['valueString']
                satisfied = fields['satisfied']['valueString']
                sentiment = fields['sentiment']['valueString']
                topic = fields['topic']['valueString']
                key_phrases = fields['keyPhrases']['valueString']
                complaint = fields['complaint']['valueString']
                content = fields['content']['valueString']
                cursor.execute(
                    "INSERT INTO processed_data (ConversationId, EndTime, StartTime, Content, summary, satisfied, sentiment, topic, key_phrases, complaint) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (conversation_id, end_timestamp, start_timestamp, content, summary, satisfied, sentiment, topic, key_phrases, complaint)
                )
                conn.commit()
                docs.extend(await prepare_search_doc(content, conversation_id, path.name, embeddings_client))
                counter += 1
            except:
                pass
            if docs != [] and counter % 10 == 0:
                result = search_client.upload_documents(documents=docs)
                docs = []
        if docs:
            search_client.upload_documents(documents=docs)

    return conversationIds, counter


conversationIds, counter = asyncio.run(process_files())
print(f"✓ Processed {counter} files")


# Load sample data to search index and database
def bulk_import_json_to_table(json_file, table_name):
    with open(file=json_file, mode="r", encoding='utf-8') as f:
        data = json.load(f)

    if not data:
        return

    df = pd.DataFrame(data)
    generate_sql_insert_script(df, table_name, list(df.columns), f'{table_name}_import.sql')


with open(file=SAMPLE_IMPORT_FILE, mode='r', encoding='utf-8') as file:
    documents = json.load(file)
batch = [{"@search.action": "upload", **doc} for doc in documents]
search_client.upload_documents(documents=batch)

bulk_import_json_to_table(SAMPLE_PROCESSED_DATA_FILE, 'processed_data')
bulk_import_json_to_table(SAMPLE_PROCESSED_DATA_KEY_PHRASES_FILE, 'processed_data_key_phrases')
print(f"✓ Loaded {len(documents)} sample records")

# Topic mining and mapping
cursor.execute('SELECT distinct topic FROM processed_data')
rows = [tuple(row) for row in cursor.fetchall()]
column_names = [i[0] for i in cursor.description]
df = pd.DataFrame(rows, columns=column_names)
cursor.execute('DROP TABLE IF EXISTS km_mined_topics')
cursor.execute("""CREATE TABLE km_mined_topics (
    label varchar(255) NOT NULL PRIMARY KEY,
    description varchar(255)
);""")
conn.commit()
topics_str = ', '.join(df['topic'].tolist())

# Create agents for topic mining and mapping
print("Creating topic mining and mapping agents...")

# Topic Mining Agent instruction
TOPIC_MINING_AGENT_INSTRUCTION = '''You are a data analysis assistant specialized in natural language processing and topic modeling.
Your task is to analyze conversation topics and identify distinct categories.

Rules:
1. Identify key topics using topic modeling techniques
2. Choose the right number of topics based on data (try to keep it up to 8 topics)
3. Assign clear and concise labels to each topic
4. Provide brief descriptions for each topic
5. Include common topics like parental controls, billing issues if relevant
6. If data is insufficient, indicate more data is needed
7. Return topics in JSON format with 'topics' array containing objects with 'label' and 'description' fields
8. Return ONLY the JSON, no other text or markdown formatting
'''

# Topic Mapping Agent instruction
TOPIC_MAPPING_AGENT_INSTRUCTION = '''You are a data analysis assistant that maps conversation topics to the closest matching category.
Return ONLY the matching topic EXACTLY as written in the list (case-sensitive)
Do not add any explanatory text, punctuation, quotes, or formatting
Do not create, rephrase, abbreviate, or pluralize topics
If no topic is a perfect match, choose the closest one from the list ONLY
'''

# Create async project client and agents
async def create_agents():
    """Create topic mining and mapping agents asynchronously."""
    async with (
        AsyncAzureCliCredential(process_timeout=30) as async_cred,
        AIProjectClient(endpoint=AI_PROJECT_ENDPOINT, credential=async_cred) as project_client,
    ):
        topic_mining_agent = await project_client.agents.create_version(
            agent_name=TOPIC_MINING_AGENT_NAME,
            definition=PromptAgentDefinition(
                model=DEPLOYMENT_MODEL,
                instructions=TOPIC_MINING_AGENT_INSTRUCTION,
            ),
        )

        topic_mapping_agent = await project_client.agents.create_version(
            agent_name=TOPIC_MAPPING_AGENT_NAME,
            definition=PromptAgentDefinition(
                model=DEPLOYMENT_MODEL,
                instructions=TOPIC_MAPPING_AGENT_INSTRUCTION,
            ),
        )

        return topic_mining_agent, topic_mapping_agent


topic_mining_agent, topic_mapping_agent = asyncio.run(create_agents())
print(f"✓ Created agents: {topic_mining_agent.name}, {topic_mapping_agent.name}")

try:
    async def call_topic_mining_agent(topics_str1):
        """Use Topic Mining Agent with Agent Framework to analyze and categorize topics."""
        async with (
            AsyncAzureCliCredential(process_timeout=30) as async_cred,
            AIProjectClient(endpoint=AI_PROJECT_ENDPOINT, credential=async_cred) as project_client,
        ):
            # Create chat client with topic mining agent
            chat_client = AzureAIClient(
                project_client=project_client,
                agent_name=TOPIC_MINING_AGENT_NAME,
                use_latest_version=True,
            )
            
            async with ChatAgent(
                chat_client=chat_client,
                store=False,  # No need to store conversation history
            ) as chat_agent:
                # Query with the topics string
                query = f"""Analyze these conversation topics and identify distinct categories:
                {topics_str1}
                
                Return the result as JSON with a 'topics' array containing objects with 'label' and 'description' fields."""
                
                result = await chat_agent.run(messages=query)
                res = result.text
                # Clean up markdown formatting if present
                res = res.replace("```json", '').replace("```", '').strip()
                return json.loads(res)

    res = asyncio.run(call_topic_mining_agent(topics_str))
    for object1 in res['topics']:
        cursor.execute("INSERT INTO km_mined_topics (label, description) VALUES (?,?)", (object1['label'], object1['description']))
    conn.commit()

    cursor.execute('SELECT label FROM km_mined_topics')
    rows = [tuple(row) for row in cursor.fetchall()]
    column_names = [i[0] for i in cursor.description]
    df_topics = pd.DataFrame(rows, columns=column_names)
    mined_topics_list = df_topics['label'].tolist()
    mined_topics = ", ".join(mined_topics_list)
    print(f"✓ Mined {len(mined_topics_list)} topics")


    async def call_topic_mapping_agent(input_text, list_of_topics):
        """Use Topic Mapping Agent with Agent Framework to map topic to category."""
        async with (
            AsyncAzureCliCredential(process_timeout=30) as async_cred,
            AIProjectClient(endpoint=AI_PROJECT_ENDPOINT, credential=async_cred) as project_client,
        ):
            # Create chat client with topic mapping agent
            chat_client = AzureAIClient(
                project_client=project_client,
                agent_name=TOPIC_MAPPING_AGENT_NAME,
                use_latest_version=True,
            )

            async with ChatAgent(
                chat_client=chat_client,
                store=False,
            ) as chat_agent:
                query = f"""Find the closest topic for this text: '{input_text}' from this list of topics: {list_of_topics}"""

                result = await chat_agent.run(messages=query)
                return result.text.strip()


    cursor.execute('SELECT * FROM processed_data')
    rows = [tuple(row) for row in cursor.fetchall()]
    column_names = [i[0] for i in cursor.description]
    df_processed_data = pd.DataFrame(rows, columns=column_names)
    df_processed_data = df_processed_data[df_processed_data['ConversationId'].isin(conversationIds)]


    # Map topics using agent asynchronously
    async def map_all_topics():
        """Map all topics to categories using agent."""
        for _, row in df_processed_data.iterrows():
            mined_topic_str = await call_topic_mapping_agent(row['topic'], str(mined_topics_list))
            cursor.execute("UPDATE processed_data SET mined_topic = ? WHERE ConversationId = ?", (mined_topic_str, row['ConversationId']))
        conn.commit()


    asyncio.run(map_all_topics())

    # Update processed data for RAG
    cursor.execute('DROP TABLE IF EXISTS km_processed_data')
    cursor.execute("""CREATE TABLE km_processed_data (
        ConversationId varchar(255) NOT NULL PRIMARY KEY,
        StartTime varchar(255),
        EndTime varchar(255),
        Content varchar(max),
        summary varchar(max),
        satisfied varchar(255),
        sentiment varchar(255),
        keyphrases nvarchar(max),
        complaint varchar(255),
        topic varchar(255)
    );""")
    conn.commit()
    cursor.execute('''select ConversationId, StartTime, EndTime, Content, summary, satisfied, sentiment,
                      key_phrases as keyphrases, complaint, mined_topic as topic from processed_data''')
    rows = cursor.fetchall()
    columns = ["ConversationId", "StartTime", "EndTime", "Content", "summary", "satisfied", "sentiment",
               "keyphrases", "complaint", "topic"]

    df_km = pd.DataFrame([list(row) for row in rows], columns=columns)
    generate_sql_insert_script(df_km, 'km_processed_data', columns, 'km_processed_data_insert.sql')

    # Update processed_data_key_phrases table
    cursor.execute('''select ConversationId, key_phrases, sentiment, mined_topic as topic, StartTime from processed_data''')
    rows = [tuple(row) for row in cursor.fetchall()]
    column_names = [i[0] for i in cursor.description]
    df = pd.DataFrame(rows, columns=column_names)
    df = df[df['ConversationId'].isin(conversationIds)]
    for _, row in df.iterrows():
        key_phrases = row['key_phrases'].split(',')
        for key_phrase in key_phrases:
            key_phrase = key_phrase.strip()
            cursor.execute("INSERT INTO processed_data_key_phrases (ConversationId, key_phrase, sentiment, topic, StartTime) VALUES (?,?,?,?,?)",
                        (row['ConversationId'], key_phrase, row['sentiment'], row['topic'], row['StartTime']))
    conn.commit()

    # Adjust dates to current date
    today = datetime.today()
    cursor.execute("SELECT MAX(CAST(StartTime AS DATETIME)) FROM [dbo].[processed_data]")
    max_start_time = cursor.fetchone()[0]
    days_difference = (today.date() - max_start_time.date()).days - 1 if max_start_time else 0
    if days_difference > 0:
        cursor.execute("UPDATE [dbo].[processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference, days_difference))
        cursor.execute("UPDATE [dbo].[km_processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference, days_difference))
        cursor.execute("UPDATE [dbo].[processed_data_key_phrases] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference,))
        conn.commit()

        cursor.close()
        conn.close()
        print("✓ Data processing completed")

finally:
    # Delete the agents after processing is complete
    print("Deleting topic mining and mapping agents...")
    try:
        async def delete_agents():
            """Delete topic mining and mapping agents asynchronously."""
            async with (
                AsyncAzureCliCredential(process_timeout=30) as async_cred,
                AIProjectClient(endpoint=AI_PROJECT_ENDPOINT, credential=async_cred) as project_client,
            ):
                await project_client.agents.delete(topic_mining_agent.name)
                await project_client.agents.delete(topic_mapping_agent.name)
        
        asyncio.run(delete_agents())
        print(f"✓ Deleted agents: {topic_mining_agent.name}, {topic_mapping_agent.name}")
    except Exception as e:
        print(f"Warning: Could not delete agents: {e}")

