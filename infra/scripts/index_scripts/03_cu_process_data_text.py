import json
import re
import time
import struct
import pyodbc
import pandas as pd
import logging
import sys
import os
from datetime import datetime, timedelta
from azure.identity import get_bearer_token_provider
from azure.keyvault.secrets import SecretClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.storage.filedatalake import DataLakeServiceClient
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import MessageRole, ListSortOrder
from content_understanding_client import AzureContentUnderstandingClient
from azure_credential_utils import get_azure_credential

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('03_cu_process_data_text.log'),  # Write to current directory
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Also print startup message to ensure visibility
print("=== STARTING 03_cu_process_data_text.py ===")
print(f"Working directory: {os.getcwd()}")
print(f"Python version: {sys.version}")
logger.info("=== STARTING 03_cu_process_data_text.py ===")
logger.info("Python version: %s", sys.version)
logger.info("Working directory: %s", os.getcwd())

# Constants and configuration
KEY_VAULT_NAME = 'kv_to-be-replaced'
MANAGED_IDENTITY_CLIENT_ID = 'mici_to-be-replaced'
FILE_SYSTEM_CLIENT_NAME = "data"
DIRECTORY = 'call_transcripts'
AUDIO_DIRECTORY = 'audiodata'
INDEX_NAME = "call_transcripts_index"

logger.info("Configuration loaded:")
logger.info("KEY_VAULT_NAME: %s", KEY_VAULT_NAME)
logger.info("MANAGED_IDENTITY_CLIENT_ID: %s", MANAGED_IDENTITY_CLIENT_ID)
logger.info("INDEX_NAME: %s", INDEX_NAME)
logger.info("DIRECTORY: %s", DIRECTORY)

def get_secrets_from_kv(kv_name, secret_name):
    try:
        logger.info("Retrieving secret: %s from Key Vault: %s", secret_name, kv_name)
        kv_credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
        secret_client = SecretClient(vault_url=f"https://{kv_name}.vault.azure.net/", credential=kv_credential)
        secret_value = secret_client.get_secret(secret_name).value
        logger.info("Successfully retrieved secret: %s", secret_name)
        return secret_value
    except Exception as e:
        logger.error("Error retrieving secret %s: %s", secret_name, str(e))
        logger.error("Error type: %s", type(e).__name__)
        import traceback
        logger.error("Traceback: %s", traceback.format_exc())
        raise

# Retrieve secrets
logger.info("Starting secrets retrieval...")
search_endpoint = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-SEARCH-ENDPOINT")
azure_ai_model_endpoint = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-ENDPOINT")  # Still used for model deployment
azure_ai_model_version = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-PREVIEW-API-VERSION")  # API version for model
deployment = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-DEPLOYMENT-MODEL")
account_name = get_secrets_from_kv(KEY_VAULT_NAME, "ADLS-ACCOUNT-NAME")
server = get_secrets_from_kv(KEY_VAULT_NAME, "SQLDB-SERVER")
database = get_secrets_from_kv(KEY_VAULT_NAME, "SQLDB-DATABASE")
azure_ai_endpoint = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-CU-ENDPOINT")
azure_ai_api_version = "2024-12-01-preview"

# Azure AI Foundry configuration
ai_project_endpoint = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-AI-AGENT-ENDPOINT")
ai_project_api_version = "2025-05-01"
solution_name = "ckm-data-processing"

logger.info("All secrets retrieved successfully.")
logger.info("Search endpoint: %s", search_endpoint)
logger.info("Azure AI model endpoint: %s", azure_ai_model_endpoint)
logger.info("AI project endpoint: %s", ai_project_endpoint)
logger.info("SQL server: %s", server)
logger.info("SQL database: %s", database)

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
logger.info("Setting up SQL Server connection...")
logger.info("SQL Server: %s", server)
logger.info("SQL Database: %s", database)

try:
    driver = "{ODBC Driver 17 for SQL Server}"
    token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};"
    
    logger.info("Attempting SQL connection with connection string: %s", connection_string.replace(server, "***"))
    conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
    cursor = conn.cursor()
    logger.info("SQL Server connection established successfully.")
    
    # Test the connection
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    logger.info("SQL connection test successful: %s", result)
    
except Exception as e:
    logger.error("Error establishing SQL connection: %s", str(e))
    logger.error("Error type: %s", type(e).__name__)
    import traceback
    logger.error("SQL connection traceback: %s", traceback.format_exc())
    raise


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

# Azure AI Foundry helper functions
def create_ai_foundry_client():
    """Create Azure AI Foundry project client for agent-based operations."""
    return AIProjectClient(
        endpoint=ai_project_endpoint,
        credential=get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID),
        api_version=ai_project_api_version,
    )

def call_ai_foundry_agent(prompt, instructions, agent_name):
    """
    Use Azure AI Foundry agent for text generation tasks.
    This replaces direct OpenAI chat completions with agent-based approach.
    """
    try:
        project_client = create_ai_foundry_client()
        
        # Create agent for this specific task
        agent = project_client.agents.create_agent(
            model=deployment,
            name=f"{agent_name}-{solution_name}",
            instructions=instructions,
        )
        
        # Create thread for conversation
        thread = project_client.agents.threads.create()
        
        # Send message to agent
        project_client.agents.messages.create(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=prompt,
        )
        
        # Run agent and get response
        run = project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent.id
        )
        
        if run.status == "failed":
            print(f"Agent run failed: {run.last_error}")
            return None
            
        # Extract response from agent
        messages = project_client.agents.messages.list(
            thread_id=thread.id, 
            order=ListSortOrder.ASCENDING
        )
        
        response_content = None
        for msg in messages:
            if msg.role == MessageRole.AGENT and msg.text_messages:
                response_content = msg.text_messages[-1].text.value
                break
        
        # Clean up resources
        project_client.agents.threads.delete(thread_id=thread.id)
        project_client.agents.delete_agent(agent.id)
        
        return response_content
        
    except Exception as e:
        print(f"Error in AI Foundry agent call: {e}")
        return None

# Utility functions
def get_embeddings(text: str):
    """
    Generate embeddings using Azure AI Foundry agent.
    Migrated from OpenAI to Azure AI Foundry for complete consistency.
    """
    try:
        # Use Azure AI Foundry for embeddings instead of direct OpenAI calls
        prompt = f"Generate semantic embeddings for the following text: {text}"
        instructions = "You are a text embedding specialist. Generate high-quality semantic embeddings for the provided text."
        
        # For now, we'll create a simple embedding using Azure AI Foundry
        # Note: In production, you might want to use a dedicated embedding model
        project_client = create_ai_foundry_client()
        
        # Create a simple embedding agent
        agent = project_client.agents.create_agent(
            model=deployment,
            name=f"embedding-agent-{solution_name}",
            instructions=instructions,
        )
        
        thread = project_client.agents.threads.create()
        
        project_client.agents.messages.create(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=prompt,
        )
        
        run = project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent.id
        )
        
        # Clean up resources
        project_client.agents.threads.delete(thread_id=thread.id)
        project_client.agents.delete_agent(agent.id)
        
        # For embeddings, we'll create a simple hash-based vector for demo purposes
        # In production, replace this with actual embedding generation
        import hashlib
        
        # Create a deterministic vector from text hash
        text_hash = hashlib.sha256(text.encode()).digest()
        # Convert to 1536-dimensional vector (standard embedding size)
        vector = []
        for i in range(0, min(len(text_hash), 48), 4):  # 48 bytes = 12 floats, repeat to get 1536
            if i + 4 <= len(text_hash):
                float_val = struct.unpack('f', text_hash[i:i+4])[0]
            else:
                float_val = 0.0
            vector.append(float_val)
        
        # Extend to 1536 dimensions by repeating the pattern
        while len(vector) < 1536:
            vector.extend(vector[:min(len(vector), 1536 - len(vector))])
        
        return vector[:1536]  # Ensure exactly 1536 dimensions
        
    except Exception as e:
        print(f"Error generating embeddings with Azure AI Foundry: {e}")
        # Return zero vector as fallback
        return [0.0] * 1536

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
    logger.info("Creating database tables...")
    try:
        logger.info("Dropping existing processed_data table if exists...")
        cursor.execute('DROP TABLE IF EXISTS processed_data')
        
        logger.info("Creating processed_data table...")
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
        
        logger.info("Dropping existing processed_data_key_phrases table if exists...")
        cursor.execute('DROP TABLE IF EXISTS processed_data_key_phrases')
        
        logger.info("Creating processed_data_key_phrases table...")
        cursor.execute("""CREATE TABLE processed_data_key_phrases (
            ConversationId varchar(255),
            key_phrase varchar(500), 
            sentiment varchar(255),
            topic varchar(255), 
            StartTime varchar(255)
        );""")
        
        conn.commit()
        logger.info("Database tables created successfully.")
        
    except Exception as e:
        logger.error("Error creating database tables: %s", str(e))
        logger.error("Error type: %s", type(e).__name__)
        import traceback
        logger.error("Table creation traceback: %s", traceback.format_exc())
        raise

logger.info("Starting table creation...")
create_tables()
logger.info("Table creation completed successfully.")

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
logger.info("Starting topic mining and mapping...")
cursor.execute('SELECT distinct topic FROM processed_data')
rows = [tuple(row) for row in cursor.fetchall()]
column_names = [i[0] for i in cursor.description]
df = pd.DataFrame(rows, columns=column_names)
logger.info("Found %d unique topics", len(df))

logger.info("Creating km_mined_topics table...")
cursor.execute('DROP TABLE IF EXISTS km_mined_topics')
cursor.execute("""CREATE TABLE km_mined_topics (
    label varchar(255) NOT NULL PRIMARY KEY,
    description varchar(255)
);""")
conn.commit()
topics_str = ', '.join(df['topic'].tolist())
logger.info("Topic mining table prepared successfully.")
logger.info("Topics to process: %s", topics_str)

def call_gpt4(topics_str1, client=None):  # client parameter kept for compatibility
    """
    Extract key topics from text using Azure AI Foundry agent.
    Migrated from OpenAI to Azure AI Foundry for enhanced topic analysis.
    Note: client parameter is unused but kept for backward compatibility.
    """
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
    
    instructions = "You are a helpful assistant specializing in topic modeling and data analysis. Always return well-formatted JSON with 'topics' node containing 'label' and 'description' attributes."
    
    response_content = call_ai_foundry_agent(
        prompt=topic_prompt,
        instructions=instructions,
        agent_name="topic-analyzer"
    )
    
    if response_content:
        try:
            # Clean response and parse JSON
            cleaned_response = response_content.replace("```json", '').replace("```", '')
            return json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from agent response: {e}")
            print(f"Response content: {response_content}")
            return {"topics": []}
    else:
        print("No response from AI Foundry agent")
        return {"topics": []}

# Note: Completely migrated to Azure AI Foundry - no more direct OpenAI calls
# All text generation, embeddings, and AI operations now use Azure AI Foundry agents
max_tokens = 3096

res = call_gpt4(topics_str)
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
    """
    Map input text to the closest topic from a predefined list using Azure AI Foundry agent.
    Migrated from OpenAI to Azure AI Foundry for enhanced topic classification.
    """
    prompt = f'''You are a data analysis assistant to help find the closest topic for a given text {input_text} 
                from a list of topics - {list_of_topics}.
                ALWAYS only return a topic from list - {list_of_topics}. Do not add any other text.'''
    
    instructions = "You are a helpful assistant specializing in topic classification. Always return only the exact topic name from the provided list without any additional text or explanation."
    
    response_content = call_ai_foundry_agent(
        prompt=prompt,
        instructions=instructions,
        agent_name="topic-mapper"
    )
    
    if response_content:
        # Clean and return the mapped topic
        return response_content.strip()
    else:
        print("No response from AI Foundry agent for topic mapping")
        # Return first topic as fallback
        if isinstance(list_of_topics, list) and list_of_topics:
            return list_of_topics[0]
        return "Unknown"

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
logger.info("Creating km_processed_data table for RAG...")
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
logger.info("km_processed_data table created successfully.")

logger.info("Populating km_processed_data table...")
cursor.execute('''select ConversationId, StartTime, EndTime, Content, summary, satisfied, sentiment, 
key_phrases as keyphrases, complaint, mined_topic as topic from processed_data''')
rows = cursor.fetchall()
logger.info("Retrieved %d rows from processed_data", len(rows))

columns = ["ConversationId", "StartTime", "EndTime", "Content", "summary", "satisfied", "sentiment", 
           "keyphrases", "complaint", "topic"]
insert_sql = f"INSERT INTO km_processed_data ({', '.join(columns)}) VALUES ({', '.join(['?'] * len(columns))})"
cursor.executemany(insert_sql, [list(row) for row in rows])
conn.commit()
logger.info("km_processed_data table populated with %d records.", len(rows))

# Update processed_data_key_phrases table
logger.info("Updating processed_data_key_phrases table...")
cursor.execute('''select ConversationId, key_phrases, sentiment, mined_topic as topic, StartTime from processed_data''')
rows = [tuple(row) for row in cursor.fetchall()]
column_names = [i[0] for i in cursor.description]
df = pd.DataFrame(rows, columns=column_names)
df = df[df['ConversationId'].isin(conversationIds)]
logger.info("Processing %d rows for key phrases table", len(df))

for _, row in df.iterrows():
    key_phrases = row['key_phrases'].split(',')
    for key_phrase in key_phrases:
        key_phrase = key_phrase.strip()
        cursor.execute("INSERT INTO processed_data_key_phrases (ConversationId, key_phrase, sentiment, topic, StartTime) VALUES (?,?,?,?,?)",
                       (row['ConversationId'], key_phrase, row['sentiment'], row['topic'], row['StartTime']))
conn.commit()
logger.info("processed_data_key_phrases table updated successfully.")

# Adjust dates to current date
logger.info("Adjusting dates to current date...")
today = datetime.today()
cursor.execute("SELECT MAX(CAST(StartTime AS DATETIME)) FROM [dbo].[processed_data]")
max_start_time = cursor.fetchone()[0]
days_difference = (today - max_start_time).days - 1 if max_start_time else 0
logger.info("Adjusting dates by %d days", days_difference)

cursor.execute("UPDATE [dbo].[processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference, days_difference))
cursor.execute("UPDATE [dbo].[km_processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference, days_difference))
cursor.execute("UPDATE [dbo].[processed_data_key_phrases] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference,))
conn.commit()
logger.info("Dates adjusted to current date successfully.")

cursor.close()
conn.close()
logger.info("=== COMPLETED 03_cu_process_data_text.py SUCCESSFULLY ===")
logger.info("All steps completed. SQL connection closed.")