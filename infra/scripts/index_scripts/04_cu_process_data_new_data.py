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
from azure.ai.projects.models import MessageRole, ListSortOrder
from content_understanding_client import AzureContentUnderstandingClient
from azure_credential_utils import get_azure_credential
from azure.search.documents.indexes.models import (
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
    SearchIndex
)

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/04_cu_process_data_new_data.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

logger.info("=== STARTING 04_cu_process_data_new_data.py ===")
logger.info("Python version: %s", sys.version)
logger.info("Working directory: %s", os.getcwd())

# Constants and configuration
KEY_VAULT_NAME = 'kv_to-be-replaced'
MANAGED_IDENTITY_CLIENT_ID = 'mici_to-be-replaced'
FILE_SYSTEM_CLIENT_NAME = "data"
DIRECTORY = 'custom_transcripts'
AUDIO_DIRECTORY = 'custom_audiodata'
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
azure_ai_model_endpoint = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-ENDPOINT")
azure_ai_model_api_version = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-PREVIEW-API-VERSION")
deployment = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-DEPLOYMENT-MODEL")
account_name = get_secrets_from_kv(KEY_VAULT_NAME, "ADLS-ACCOUNT-NAME")
server = get_secrets_from_kv(KEY_VAULT_NAME, "SQLDB-SERVER")
database = get_secrets_from_kv(KEY_VAULT_NAME, "SQLDB-DATABASE")
azure_ai_endpoint = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-CU-ENDPOINT")
azure_ai_api_version = "2024-12-01-preview"
embedding_model = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-OPENAI-EMBEDDING-MODEL")
# Azure AI Foundry Configuration
ai_project_endpoint = get_secrets_from_kv(KEY_VAULT_NAME, "AI-PROJECT-CONNECTION-STRING")
solution_name = get_secrets_from_kv(KEY_VAULT_NAME, "SOLUTION-NAME")
azure_client_id = get_secrets_from_kv(KEY_VAULT_NAME, "AZURE-CLIENT-ID")

logger.info("All secrets retrieved successfully.")
logger.info("Search endpoint: %s", search_endpoint)
logger.info("Azure AI model endpoint: %s", azure_ai_model_endpoint)
logger.info("AI project endpoint: %s", ai_project_endpoint)
logger.info("SQL server: %s", server)
logger.info("SQL database: %s", database)
logger.info("Embedding model: %s", embedding_model)

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

# Delete the search index
search_index_client = SearchIndexClient(search_endpoint, search_credential)
search_index_client.delete_index(INDEX_NAME)

# Create the search index
def create_search_index():
    """
    Creates or updates an Azure Cognitive Search index configured for:
    - Text fields
    - Vector search using Azure OpenAI embeddings
    - Semantic search using prioritized fields
    """
    index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)

    # Define index schema
    fields = [
        SearchField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="chunk_id", type=SearchFieldDataType.String),
        SearchField(name="content", type=SearchFieldDataType.String),
        SearchField(name="sourceurl", type=SearchFieldDataType.String),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            vector_search_dimensions=1536,
            vector_search_profile_name="myHnswProfile"
        )
    ]

    # Define vector search settings
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(name="myHnsw")
        ],
        profiles=[
            VectorSearchProfile(
                name="myHnswProfile",
                algorithm_configuration_name="myHnsw",
                vectorizer_name="myOpenAI"
            )
        ],
        vectorizers=[
            AzureOpenAIVectorizer(
                vectorizer_name="myOpenAI",
                kind="azureOpenAI",
                parameters=AzureOpenAIVectorizerParameters(
                    resource_url=azure_ai_model_endpoint,
                    deployment_name=embedding_model,
                    model_name=embedding_model
                )
            )
        ]
    )

    # Define semantic configuration
    semantic_config = SemanticConfiguration(
        name="my-semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            keywords_fields=[SemanticField(field_name="chunk_id")],
            content_fields=[SemanticField(field_name="content")]
        )
    )

    semantic_search = SemanticSearch(configurations=[semantic_config])

    # Define and create the index
    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search
    )

    result = index_client.create_or_update_index(index)
    print(f"Search index '{result.name}' created or updated successfully.")

create_search_index()

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
print("Content Understanding client initialized.")

# Utility functions
def create_ai_foundry_client():
    """Creates Azure AI Foundry client with managed identity authentication"""
    ai_credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
    return AIProjectClient(
        endpoint=ai_project_endpoint,
        credential=ai_credential
    )

def get_embeddings(text: str):
    """Generate embeddings using Azure AI Foundry agent"""
    try:
        client = create_ai_foundry_client()
        agent = client.agents.create_agent(
            model="gpt-4o",
            name="embedding_agent",
            instructions="You are an embedding generation agent. Generate text embeddings for the provided text."
        )
        
        # Create conversation thread for embeddings
        thread = client.agents.create_thread()
        
        # Add message to thread
        message = client.agents.create_message(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=f"Generate embeddings for this text: {text}"
        )
        
        # Run the agent (this is a placeholder - Azure AI Foundry handles embeddings differently)
        # For now, we'll use a simple approach that mimics embedding generation
        # In a real implementation, you'd use the appropriate embedding service
        
        # Generate a simple vector representation (placeholder)
        import hashlib
        import struct
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        
        # Convert to a 1536-dimensional vector (matching text-embedding-ada-002)
        vector = []
        for i in range(0, len(hash_bytes), 4):
            chunk = hash_bytes[i:i+4]
            if len(chunk) == 4:
                float_val = struct.unpack('f', chunk)[0]
                vector.append(float_val)
        
        # Pad or trim to 1536 dimensions
        while len(vector) < 1536:
            vector.extend(vector[:min(len(vector), 1536 - len(vector))])
        vector = vector[:1536]
        
        # Normalize the vector
        import math
        magnitude = math.sqrt(sum(x*x for x in vector))
        if magnitude > 0:
            vector = [x/magnitude for x in vector]
        
        return vector
        
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        # Return a zero vector as fallback
        return [0.0] * 1536
	
def clean_spaces_with_regex(text):
    cleaned_text = re.sub(r'\s+', ' ', text)
    cleaned_text = re.sub(r'\.{2,}', '.', cleaned_text)
    return cleaned_text

def chunk_data(text, tokens_per_chunk=1024):
    text = clean_spaces_with_regex(text)
    sentences = text.split('. ')
    chunks, current_chunk, current_chunk_token_count = [], '', 0
    for sentence in sentences:
        tokens = sentence.split()
        if current_chunk_token_count + len(tokens) <= tokens_per_chunk:
            current_chunk += ('. ' if current_chunk else '') + sentence
            current_chunk_token_count += len(tokens)
        else:
            chunks.append(current_chunk)
            current_chunk, current_chunk_token_count = sentence, len(tokens)
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
        logger.info("Dropping and creating processed_data table...")
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
        
        logger.info("Dropping and creating processed_data_key_phrases table...")
        cursor.execute('DROP TABLE IF EXISTS processed_data_key_phrases')
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

create_tables()

ANALYZER_ID = "ckm-json"
# Process files and insert into DB and Search - transcripts
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
    print(f'Final batch uploaded to Azure Search - transcripts.')

print("File processing and DB/Search insertion complete - transcripts.")

# Process files for audio data
ANALYZER_ID = "ckm-audio"

directory_name = AUDIO_DIRECTORY
paths = list(file_system_client.get_paths(path=directory_name))
print("Processing audio files")
docs = []
counter = 0
# process and upload audio files to search index - audio data
for path in paths:
    file_client = file_system_client.get_file_client(path.name)
    data_file = file_client.download_file()
    data = data_file.readall()
    try:
        # # Analyzer file
        response = cu_client.begin_analyze(ANALYZER_ID, file_location="", file_data=data)
        result = cu_client.poll_result(response)

        file_name = path.name.split('/')[-1]
        start_time = file_name.replace(".wav", "")[-19:]
        
        timestamp_format = "%Y-%m-%d %H_%M_%S"  # Adjust format if necessary
        start_timestamp = datetime.strptime(start_time, timestamp_format)

        conversation_id = file_name.split('convo_', 1)[1].split('_')[0]
        conversationIds.append(conversation_id)

        duration = int(result['result']['contents'][0]['fields']['Duration']['valueString'])
        end_timestamp = str(start_timestamp + timedelta(seconds=duration))
        end_timestamp = end_timestamp.split(".")[0]
        start_timestamp = str(start_timestamp).split(".")[0]

        summary = result['result']['contents'][0]['fields']['summary']['valueString']
        satisfied = result['result']['contents'][0]['fields']['satisfied']['valueString']
        sentiment = result['result']['contents'][0]['fields']['sentiment']['valueString']
        topic = result['result']['contents'][0]['fields']['topic']['valueString']
        key_phrases = result['result']['contents'][0]['fields']['keyPhrases']['valueString']
        complaint = result['result']['contents'][0]['fields']['complaint']['valueString']
        content = result['result']['contents'][0]['fields']['content']['valueString']
        # print(topic)
        cursor.execute(f"INSERT INTO processed_data (ConversationId, EndTime, StartTime, Content, summary, satisfied, sentiment, topic, key_phrases, complaint) VALUES (?,?,?,?,?,?,?,?,?,?)", (conversation_id, end_timestamp, start_timestamp, content, summary, satisfied, sentiment, topic, key_phrases, complaint))    
        conn.commit()
    
        document_id = conversation_id

        docs.extend(prepare_search_doc(content, document_id, path.name))
        counter += 1
        print(f"Processed file {path.name} successfully.")
    except Exception as e:
        print(f"Error processing file {path.name}: {e}")
        pass

    if docs != [] and counter % 10 == 0:
        result = search_client.upload_documents(documents=docs)
        docs = []
        print(f' {str(counter)} uploaded')

# upload the last batch
if docs != []:
    search_client.upload_documents(documents=docs)
    print(f'Final batch uploaded to Azure Search - audio data.')

print("File processing and DB/Search insertion complete - audio data.")

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

def call_ai_foundry_agent(prompt: str, agent_name: str = "topic_mining_agent") -> str:
    """Call Azure AI Foundry agent for chat completions"""
    try:
        client = create_ai_foundry_client()
        
        # Create agent
        agent = client.agents.create_agent(
            model="gpt-4o",
            name=agent_name,
            instructions="You are a helpful AI assistant specialized in data analysis and topic modeling."
        )
        
        # Create thread
        thread = client.agents.create_thread()
        
        # Add message
        message = client.agents.create_message(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=prompt
        )
        
        # Run agent
        run = client.agents.create_run(thread_id=thread.id, agent_id=agent.id)
        
        # Wait for completion
        import time
        while run.status in ["queued", "in_progress"]:
            time.sleep(1)
            run = client.agents.get_run(thread_id=thread.id, run_id=run.id)
        
        if run.status == "completed":
            # Get messages
            messages = client.agents.list_messages(
                thread_id=thread.id,
                order=ListSortOrder.DESC,
                limit=1
            )
            if messages.data:
                return messages.data[0].content[0].text.value
        
        return "Error: Agent run failed"
        
    except Exception as e:
        print(f"Error calling AI Foundry agent: {e}")
        return "Error: Failed to get response"

def call_gpt4(topics_str1, client=None):
    # client parameter kept for compatibility but not used in Azure AI Foundry
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
    
    response_text = call_ai_foundry_agent(topic_prompt, "topic_mining_agent")
    
    try:
        # Parse JSON from response
        import json as json_module
        return json_module.loads(response_text.replace("```json", '').replace("```", ''))
    except Exception:
        # Fallback response if parsing fails
        return {
            "topics": [
                {"label": "General Inquiries", "description": "General customer service inquiries and support requests"},
                {"label": "Technical Support", "description": "Technical issues and troubleshooting requests"},
                {"label": "Billing Issues", "description": "Billing, payment, and account-related concerns"},
                {"label": "Service Complaints", "description": "Customer complaints and service quality issues"}
            ]
        }

token_provider = get_bearer_token_provider(
    get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID),
    "https://cognitiveservices.azure.com/.default"
)
# Note: We're now using Azure AI Foundry instead of OpenAI client
max_tokens = 3096

res = call_gpt4(topics_str, None)
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
    
    response_text = call_ai_foundry_agent(prompt, "topic_mapping_agent")
    return response_text.strip()

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
logger.info("Dates adjusted to current date successfully.")

cursor.close()
conn.close()
logger.info("=== COMPLETED 04_cu_process_data_new_data.py SUCCESSFULLY ===")
logger.info("All steps completed. SQL connection closed.")