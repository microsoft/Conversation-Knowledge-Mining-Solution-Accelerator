import json
import re
import time
import struct
import os
import argparse
import pyodbc
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import urlparse
from azure.identity import AzureCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.storage.filedatalake import DataLakeServiceClient
from azure.ai.inference import ChatCompletionsClient, EmbeddingsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from content_understanding_client import AzureContentUnderstandingClient

# Get parameters from command line
p = argparse.ArgumentParser()
p.add_argument("--search_endpoint", required=True)
p.add_argument("--ai_project_endpoint", required=True)
p.add_argument("--openai_api_version", required=True)
p.add_argument("--deployment_model", required=True)
p.add_argument("--embedding_model", required=True)
p.add_argument("--storage_account", required=True)
p.add_argument("--sql_server", required=True)
p.add_argument("--sql_database", required=True)
p.add_argument("--cu_endpoint", required=True)
args = p.parse_args()

SEARCH_ENDPOINT = args.search_endpoint
AI_PROJECT_ENDPOINT = args.ai_project_endpoint
OPENAI_API_VERSION = args.openai_api_version
DEPLOYMENT_MODEL = args.deployment_model
EMBEDDING_MODEL = args.embedding_model
STORAGE_ACCOUNT = args.storage_account
SQL_SERVER = args.sql_server
SQL_DATABASE = args.sql_database
CU_ENDPOINT = args.cu_endpoint

FILE_SYSTEM_CLIENT_NAME = "data"
DIRECTORY = 'call_transcripts'
INDEX_NAME = "call_transcripts_index"

SAMPLE_IMPORT_FILE = 'infra/data/sample_search_index_data.json'
SAMPLE_PROCESSED_DATA_FILE = 'infra/data/sample_processed_data.json'
SAMPLE_PROCESSED_DATA_KEY_PHRASES_FILE = 'infra/data/sample_processed_data_key_phrases.json'

print("Parameters received.")

# Azure DataLake setup
account_url = f"https://{STORAGE_ACCOUNT}.dfs.core.windows.net"
credential = AzureCliCredential()
service_client = DataLakeServiceClient(account_url, credential=credential, api_version='2023-01-03')
file_system_client = service_client.get_file_system_client(FILE_SYSTEM_CLIENT_NAME)
directory_name = DIRECTORY
paths = list(file_system_client.get_paths(path=directory_name))
print("Azure DataLake setup complete.")

# Azure Search setup
search_credential = AzureCliCredential()
search_client = SearchClient(SEARCH_ENDPOINT, INDEX_NAME, search_credential)
index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=search_credential)
print("Azure Search setup complete.")

# SQL Server setup
driver = "{ODBC Driver 17 for SQL Server}"
token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-LE")
token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
SQL_COPT_SS_ACCESS_TOKEN = 1256
connection_string = f"DRIVER={driver};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
cursor = conn.cursor()
print("SQL Server connection established.")

# CU API setup
azure_ai_api_version = "2024-12-01-preview"
print("Setup complete.")

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
cu_credential = AzureCliCredential()
cu_token_provider = get_bearer_token_provider(cu_credential, "https://cognitiveservices.azure.com/.default")
cu_client = AzureContentUnderstandingClient(
    endpoint=CU_ENDPOINT,
    api_version=azure_ai_api_version,
    token_provider=cu_token_provider
)
ANALYZER_ID = "ckm-json"
print("Content Understanding client initialized.")

# Azure AI Foundry (Inference) clients (Managed Identity)
inference_endpoint = f"https://{urlparse(AI_PROJECT_ENDPOINT).netloc}/models"

chat_client = ChatCompletionsClient(
    endpoint=inference_endpoint,
    credential=credential,
    credential_scopes=["https://ai.azure.com/.default"],
)

embeddings_client = EmbeddingsClient(
    endpoint=inference_endpoint,
    credential=credential,
    credential_scopes=["https://ai.azure.com/.default"],
)


# Utility functions
def get_embeddings(text: str):
    try:
        resp = embeddings_client.embed(model=EMBEDDING_MODEL, input=[text])
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


def prepare_search_doc(content, document_id, path_name):
    chunks = chunk_data(content)
    docs = []
    for idx, chunk in enumerate(chunks, 1):
        chunk_id = f"{document_id}_{str(idx).zfill(2)}"
        try:
            v_contentVector = get_embeddings(str(chunk))
        except:
            time.sleep(30)
            try:
                v_contentVector = get_embeddings(str(chunk))
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
    print("Database tables created.")


create_tables()

# Process files and insert into DB and Search
conversationIds, docs, counter = [], [], 0
for path in paths:
    file_client = file_system_client.get_file_client(path.name)
    data_file = file_client.download_file()
    data = data_file.readall()
    try:
        response = cu_client.begin_analyze(ANALYZER_ID, file_location="", file_data=data)
        result = cu_client.poll_result(response)
        file_name = path.name.split('/')[-1].replace("%3A", "_")
        start_time = file_name.replace(".json", "")[-19:]
        timestamp_format = "%Y-%m-%d %H_%M_%S"
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
        docs.extend(prepare_search_doc(content, conversation_id, path.name))
        counter += 1
    except:
        pass
    if docs != [] and counter % 10 == 0:
        result = search_client.upload_documents(documents=docs)
        docs = []
        print(f'{counter} uploaded to Azure Search.')
if docs:
    search_client.upload_documents(documents=docs)
    print(f'Final batch uploaded to Azure Search.')

print("File processing and DB/Search insertion complete.")

# Load sample data to search index and database
def bulk_import_json_to_table(json_file, table_name):
    with open(file=json_file, mode="r") as f:
        data = json.load(f)

    if not data:
        print(f"No data to import into {table_name}.")
        return

    df = pd.DataFrame(data)
    generate_sql_insert_script(df, table_name, list(df.columns), f'{table_name}_import.sql')


with open(file=SAMPLE_IMPORT_FILE, mode='r', encoding='utf-8') as file:
    documents = json.load(file)
batch = [{"@search.action": "upload", **doc} for doc in documents]
search_client.upload_documents(documents=batch)
print(f'Successfully uploaded {len(documents)} sample index data records to search index {INDEX_NAME}.')

bulk_import_json_to_table(SAMPLE_PROCESSED_DATA_FILE, 'processed_data')
bulk_import_json_to_table(SAMPLE_PROCESSED_DATA_KEY_PHRASES_FILE, 'processed_data_key_phrases')
print("Sample data loaded to DB and Search.")

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
print("Topic mining table prepared.")


def call_gpt4(topics_str1, client):
    topic_prompt = f"""
        You are a data analysis assistant specialized in natural language processing and topic modeling.
        Your task is to analyze the given text corpus and identify distinct topics present within the data.
        {topics_str1}
        1. Identify the key topics in the text using topic modeling techniques.
        2. Choose the right number of topics based on data. Try to keep it up to 8 topics.
        3. Assign a clear and concise label to each topic based on its content.
        4. Provide a brief description of each topic along with its label.
        5. Add parental controls, billing issues like topics to the list of topics if the data includes calls related to them.
        If the input data is insufficient for reliable topic modeling, indicate that more data is needed rather than making assumptions.
        Ensure that the topics and labels are accurate, relevant, and easy to understand.
        Return the topics and their labels in JSON format.Always add 'topics' node and 'label', 'description' attributes in json.
        Do not return anything else.
        """
    response = client.complete(
        model=DEPLOYMENT_MODEL,
        messages=[
            SystemMessage(content="You are a helpful assistant."),
            UserMessage(content=topic_prompt),
        ],
        temperature=0,
    )
    res = response.choices[0].message.content
    return json.loads(res.replace("```json", '').replace("```", ''))


max_tokens = 3096

res = call_gpt4(topics_str, chat_client)
for object1 in res['topics']:
    cursor.execute("INSERT INTO km_mined_topics (label, description) VALUES (?,?)", (object1['label'], object1['description']))
conn.commit()
print("Topics mined and inserted into km_mined_topics.")

cursor.execute('SELECT label FROM km_mined_topics')
rows = [tuple(row) for row in cursor.fetchall()]
column_names = [i[0] for i in cursor.description]
df_topics = pd.DataFrame(rows, columns=column_names)
mined_topics_list = df_topics['label'].tolist()
mined_topics = ", ".join(mined_topics_list)
print("Mined topics loaded.")


def get_mined_topic_mapping(input_text, list_of_topics):
    prompt = f'''You are a data analysis assistant to help find the closest topic for a given text {input_text}
                from a list of topics - {list_of_topics}.
                ALWAYS only return a topic from list - {list_of_topics}. Do not add any other text.'''
    response = chat_client.complete(
        model=DEPLOYMENT_MODEL,
        messages=[
            SystemMessage(content="You are a helpful assistant."),
            UserMessage(content=prompt),
        ],
        temperature=0,
    )
    return response.choices[0].message.content


cursor.execute('SELECT * FROM processed_data')
rows = [tuple(row) for row in cursor.fetchall()]
column_names = [i[0] for i in cursor.description]
df_processed_data = pd.DataFrame(rows, columns=column_names)
df_processed_data = df_processed_data[df_processed_data['ConversationId'].isin(conversationIds)]
for _, row in df_processed_data.iterrows():
    mined_topic_str = get_mined_topic_mapping(row['topic'], str(mined_topics_list))
    cursor.execute("UPDATE processed_data SET mined_topic = ? WHERE ConversationId = ?", (mined_topic_str, row['ConversationId']))
conn.commit()
print("Processed data mapped to mined topics.")

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
print("Updating processed_data_key_phrases table")
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
print("processed_data_key_phrases table updated.")

# Adjust dates to current date
today = datetime.today()
cursor.execute("SELECT MAX(CAST(StartTime AS DATETIME)) FROM [dbo].[processed_data]")
max_start_time = cursor.fetchone()[0]
days_difference = (today - max_start_time).days - 1 if max_start_time else 0
cursor.execute("UPDATE [dbo].[processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference, days_difference))
cursor.execute("UPDATE [dbo].[km_processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference, days_difference))
cursor.execute("UPDATE [dbo].[processed_data_key_phrases] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference,))
conn.commit()
print("Dates adjusted to current date.")

cursor.close()
conn.close()
print("All steps completed. Connection closed.")
