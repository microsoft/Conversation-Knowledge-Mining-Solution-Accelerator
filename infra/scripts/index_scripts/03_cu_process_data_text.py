import json
import re
import time
import struct
import pyodbc
import pandas as pd
from datetime import datetime, timedelta
from azure.identity import get_bearer_token_provider
from azure.keyvault.secrets import SecretClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.storage.filedatalake import DataLakeServiceClient
from openai import AzureOpenAI
from content_understanding_client import AzureContentUnderstandingClient
from azure_credential_utils import get_azure_credential

# Constants and configuration
KEY_VAULT_NAME = 'kv_to-be-replaced'
MANAGED_IDENTITY_CLIENT_ID = 'mici_to-be-replaced'
FILE_SYSTEM_CLIENT_NAME = "data"
DIRECTORY = 'call_transcripts'
AUDIO_DIRECTORY = 'audiodata'
INDEX_NAME = "call_transcripts_index"

def get_secrets_from_kv(kv_name, secret_name):
    kv_credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
    secret_client = SecretClient(vault_url=f"https://{kv_name}.vault.azure.net/", credential=kv_credential)
    return secret_client.get_secret(secret_name).value

# Retrieve secrets
search_endpoint = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-SEARCH-ENDPOINT")
openai_api_base = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-ENDPOINT")
openai_api_version = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-PREVIEW-API-VERSION")
deployment = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-DEPLOYMENT-MODEL")
account_name = get_secrets_from_kv(KEY_VAULT_NAME, "ADLS-ACCOUNT-NAME")
server = get_secrets_from_kv(KEY_VAULT_NAME, "SQLDB-SERVER")
database = get_secrets_from_kv(KEY_VAULT_NAME, "SQLDB-DATABASE")
azure_ai_endpoint = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-CU-ENDPOINT")
azure_ai_api_version = "2024-12-01-preview"
print("Secrets retrieved.")

# Azure DataLake setup
account_url = f"https://{account_name}.dfs.core.windows.net"
credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
service_client = DataLakeServiceClient(account_url, credential=credential, api_version='2023-01-03')
file_system_client = service_client.get_file_system_client(FILE_SYSTEM_CLIENT_NAME)
directory_name = DIRECTORY
paths = list(file_system_client.get_paths(path=directory_name))
print("Azure DataLake setup complete.")

# Azure Search setup
search_credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
search_client = SearchClient(search_endpoint, INDEX_NAME, search_credential)
index_client = SearchIndexClient(endpoint=search_endpoint, credential=search_credential)
print("Azure Search setup complete.")

# SQL Server setup
driver = "{ODBC Driver 17 for SQL Server}"
token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-LE")
token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
SQL_COPT_SS_ACCESS_TOKEN = 1256
connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};"
conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
cursor = conn.cursor()
print("SQL Server connection established.")


# Content Understanding client
cu_credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
cu_token_provider = get_bearer_token_provider(cu_credential, "https://cognitiveservices.azure.com/.default")
cu_client = AzureContentUnderstandingClient(
    endpoint=azure_ai_endpoint,
    api_version=azure_ai_api_version,
    token_provider=cu_token_provider
)
ANALYZER_ID = "ckm-json"
print("Content Understanding client initialized.")

# Utility functions
def get_embeddings(text: str, openai_api_base, openai_api_version):
    model_id = "text-embedding-ada-002"
    token_provider = get_bearer_token_provider(
        get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID),
        "https://cognitiveservices.azure.com/.default"
    )
    client = AzureOpenAI(
        api_version=openai_api_version,
        azure_endpoint=openai_api_base,
        azure_ad_token_provider=token_provider
    )
    embedding = client.embeddings.create(input=text, model=model_id).data[0].embedding
    return embedding

# Function: Clean Spaces with Regex - 
def clean_spaces_with_regex(text):
    # Use a regular expression to replace multiple spaces with a single space
    cleaned_text = re.sub(r'\s+', ' ', text)
    # Use a regular expression to replace consecutive dots with a single dot
    cleaned_text = re.sub(r'\.{2,}', '.', cleaned_text)
    return cleaned_text

def chunk_data(text, tokens_per_chunk=1024):
    text = clean_spaces_with_regex(text)

    sentences = text.split('. ') # Split text into sentences
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
            v_contentVector = get_embeddings(str(chunk),openai_api_base,openai_api_version)
        except:
            time.sleep(30)
            try: 
                v_contentVector = get_embeddings(str(chunk),openai_api_base,openai_api_version)
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
    with open(json_file, "r") as f:
        data = json.load(f)
    data_list = [tuple(record.values()) for record in data]
    columns = ", ".join(data[0].keys())
    placeholders = ", ".join(["?"] * len(data[0]))
    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
    cursor.executemany(sql, data_list)
    conn.commit()
    print(f"Imported {len(data)} records into {table_name}.")

with open('sample_search_index_data.json', 'r') as file:
    documents = json.load(file)
batch = [{"@search.action": "upload", **doc} for doc in documents]
search_client.upload_documents(documents=batch)
print(f'Successfully uploaded {len(documents)} sample index data records to search index {INDEX_NAME}.')

bulk_import_json_to_table('sample_processed_data.json', 'processed_data')
bulk_import_json_to_table('sample_processed_data_key_phrases.json', 'processed_data_key_phrases')
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
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": topic_prompt},
        ],
        temperature=0,
    )
    res = response.choices[0].message.content
    return json.loads(res.replace("```json", '').replace("```", ''))

token_provider = get_bearer_token_provider(
    get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID),
    "https://cognitiveservices.azure.com/.default"
)
openai_client = AzureOpenAI(
    azure_endpoint=openai_api_base,
    azure_ad_token_provider=token_provider,
    api_version=openai_api_version,
)
max_tokens = 3096

res = call_gpt4(topics_str, openai_client)
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
    response = openai_client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
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
insert_sql = f"INSERT INTO km_processed_data ({', '.join(columns)}) VALUES ({', '.join(['?'] * len(columns))})"
cursor.executemany(insert_sql, [list(row) for row in rows])
conn.commit()
print("km_processed_data table updated.")

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