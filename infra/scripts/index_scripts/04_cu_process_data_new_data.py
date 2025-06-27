import json
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from content_understanding_client import AzureContentUnderstandingClient
from azure.keyvault.secrets import SecretClient  
from openai import AzureOpenAI
import pandas as pd

import re

from datetime import datetime, timedelta
import time
import pyodbc
import struct

key_vault_name = 'kv_to-be-replaced'

file_system_client_name = "data"
directory = 'custom_transcripts'
audio_directory = 'custom_audiodata'

def get_secrets_from_kv(kv_name, secret_name):
    # Set the name of the Azure Key Vault  
    key_vault_name = kv_name 
    credential = DefaultAzureCredential()

    # Create a secret client object using the credential and Key Vault name  
    secret_client =  SecretClient(vault_url=f"https://{key_vault_name}.vault.azure.net/", credential=credential)  
    return(secret_client.get_secret(secret_name).value)


search_endpoint = get_secrets_from_kv(key_vault_name,"AZURE-SEARCH-ENDPOINT")
search_key =  get_secrets_from_kv(key_vault_name,"AZURE-SEARCH-KEY")

openai_api_base =  get_secrets_from_kv(key_vault_name,"AZURE-OPENAI-ENDPOINT")
openai_api_version = get_secrets_from_kv(key_vault_name,"AZURE-OPENAI-PREVIEW-API-VERSION") 
deployment =  get_secrets_from_kv(key_vault_name,"AZURE-OPENAI-DEPLOYMENT-MODEL")  #"gpt-4o-mini"


# Function: Get Embeddings 
def get_embeddings(text: str,openai_api_base,openai_api_version):
    model_id = "text-embedding-ada-002"

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
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

def chunk_data(text):
    tokens_per_chunk = 1024 #500
    text = clean_spaces_with_regex(text)
    SENTENCE_ENDINGS = [".", "!", "?"]
    WORDS_BREAKS = ['\n', '\t', '}', '{', ']', '[', ')', '(', ' ', ':', ';', ',']

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

from azure.search.documents import SearchClient
from azure.storage.filedatalake import (
    DataLakeServiceClient
)

account_name =  get_secrets_from_kv(key_vault_name, "ADLS-ACCOUNT-NAME")

account_url = f"https://{account_name}.dfs.core.windows.net"

credential = DefaultAzureCredential()
service_client = DataLakeServiceClient(account_url, credential=credential,api_version='2023-01-03') 

file_system_client = service_client.get_file_system_client(file_system_client_name)  
directory_name = directory
paths = file_system_client.get_paths(path=directory_name)
print(paths)

index_name = "call_transcripts_index"

from azure.search.documents.indexes import SearchIndexClient

search_credential = AzureKeyCredential(search_key)

search_client = SearchClient(search_endpoint, index_name, search_credential)

index_client = SearchIndexClient(endpoint=search_endpoint, credential=search_credential)

# Delete the search index
search_index_client = SearchIndexClient(search_endpoint, search_credential)
search_index_client.delete_index(index_name)

# Create the search index
def create_search_index():
    from azure.core.credentials import AzureKeyCredential 
    search_credential = AzureKeyCredential(search_key)

    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SimpleField,
        SearchFieldDataType,
        SearchableField,
        SearchField,
        VectorSearch,
        HnswAlgorithmConfiguration,
        VectorSearchProfile,
        SemanticConfiguration,
        SemanticPrioritizedFields,
        SemanticField,
        SemanticSearch,
        SearchIndex
    )

    # Create a search index 
    index_client = SearchIndexClient(endpoint=search_endpoint, credential=search_credential)

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="chunk_id", type=SearchFieldDataType.String),
        SearchField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="sourceurl", type=SearchFieldDataType.String),
        SearchField(name="contentVector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), \
        vector_search_dimensions=1536,vector_search_profile_name="myHnswProfile"
        )
    ]

    # Configure the vector search configuration 
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="myHnsw"
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="myHnswProfile",
                algorithm_configuration_name="myHnsw",
            )
        ]
    )

    semantic_config = SemanticConfiguration(
        name="my-semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            keywords_fields=[SemanticField(field_name="chunk_id")],
            content_fields=[SemanticField(field_name="content")]
        )
    )

    # Create the semantic settings with the configuration
    semantic_search = SemanticSearch(configurations=[semantic_config])

    # Create the search index with the semantic settings
    index = SearchIndex(name=index_name, fields=fields,
                        vector_search=vector_search, semantic_search=semantic_search)
    result = index_client.create_or_update_index(index)
    print(f' {result.name} created')

create_search_index()


driver = "{ODBC Driver 17 for SQL Server}"
server =  get_secrets_from_kv(key_vault_name,"SQLDB-SERVER")
database = get_secrets_from_kv(key_vault_name,"SQLDB-DATABASE")

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

# conn = pymssql.connect(server, username, password, database)
cursor = conn.cursor()
print("Connected to the database")
cursor.execute('DROP TABLE IF EXISTS processed_data')
conn.commit()

create_processed_data_sql = """CREATE TABLE processed_data (
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
            );"""
cursor.execute(create_processed_data_sql)
conn.commit()

cursor.execute('DROP TABLE IF EXISTS processed_data_key_phrases')
conn.commit()


create_processed_data_sql = """CREATE TABLE processed_data_key_phrases (
                    ConversationId varchar(255),
                    key_phrase varchar(500), 
                    sentiment varchar(255),
                    topic varchar(255), 
                    StartTime varchar(255),
                    );"""
cursor.execute(create_processed_data_sql)
conn.commit()


AZURE_AI_ENDPOINT = get_secrets_from_kv(key_vault_name,"AZURE-OPENAI-CU-ENDPOINT")
AZURE_AI_API_VERSION = "2024-12-01-preview" 

credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

client = AzureContentUnderstandingClient(
    endpoint=AZURE_AI_ENDPOINT,
    api_version=AZURE_AI_API_VERSION,
    token_provider=token_provider
    )

print("Connected to the content understanding client")
ANALYZER_ID = "ckm-json"

def prepare_search_doc(content, document_id): 
    chunks = chunk_data(content)
    chunk_num = 0
    for chunk in chunks:
        chunk_num += 1
        chunk_id = document_id + '_' + str(chunk_num).zfill(2)
        
        try:
            v_contentVector = get_embeddings(str(chunk),openai_api_base,openai_api_version)
        except:
            time.sleep(30)
            try: 
                v_contentVector = get_embeddings(str(chunk),openai_api_base,openai_api_version)
            except: 
                v_contentVector = []
        result = {
                "id": chunk_id,
                "chunk_id": chunk_id,
                "content": chunk,
                "sourceurl": path.name.split('/')[-1],
                "contentVector": v_contentVector
            }
    return result
        
conversationIds = []
docs = []
counter = 0
from datetime import datetime, timedelta

for path in paths:
    file_client = file_system_client.get_file_client(path.name)
    data_file = file_client.download_file()
    data = data_file.readall()
   
    try:
        #Analyzer file
        response = client.begin_analyze(ANALYZER_ID, file_location="", file_data=data)
        result = client.poll_result(response)
        
        file_name = path.name.split('/')[-1].replace("%3A", "_")
        start_time = file_name.replace(".json", "")[-19:]
        
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

        cursor.execute(f"INSERT INTO processed_data (ConversationId, EndTime, StartTime, Content, summary, satisfied, sentiment, topic, key_phrases, complaint) VALUES (?,?,?,?,?,?,?,?,?,?)", (conversation_id, end_timestamp, start_timestamp, content, summary, satisfied, sentiment, topic, key_phrases, complaint))    
        conn.commit()
        
        # keyPhrases = key_phrases.split(',')
        # for keyPhrase in keyPhrases:
        #     cursor.execute(f"INSERT INTO processed_data_key_phrases (ConversationId, key_phrase, sentiment) VALUES (?,?,?)", (conversation_id, keyPhrase, sentiment))

        document_id = conversation_id

        result = prepare_search_doc(content, document_id)
        docs.append(result)
        counter += 1
    except:
        pass

    if docs != [] and counter % 10 == 0:
        result = search_client.upload_documents(documents=docs)
        docs = []
        print(f' {str(counter)} uploaded')

# upload the last batch
if docs != []:
    search_client.upload_documents(documents=docs)

   
ANALYZER_ID = "ckm-audio"

directory_name = audio_directory
paths = file_system_client.get_paths(path=directory_name)
print("Processing audio files")
docs = []
counter = 0
# process and upload audio files to search index
for path in paths:
    file_client = file_system_client.get_file_client(path.name)
    data_file = file_client.download_file()
    data = data_file.readall()
    try:
        # # Analyzer file
        response = client.begin_analyze(ANALYZER_ID, file_location="", file_data=data)
        result = client.poll_result(response)

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

        result = prepare_search_doc(content, document_id)
        docs.append(result)
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


sql_stmt = 'SELECT distinct topic FROM processed_data'
cursor.execute(sql_stmt)

rows = [tuple(row) for row in cursor.fetchall()]
column_names = [i[0] for i in cursor.description]
df = pd.DataFrame(rows, columns=column_names)

cursor.execute('DROP TABLE IF EXISTS km_mined_topics')
conn.commit()

# write topics to the database table 
create_mined_topics_sql = """CREATE TABLE km_mined_topics (
                label varchar(255) NOT NULL PRIMARY KEY,
                description varchar(255)
            );"""
cursor.execute(create_mined_topics_sql)
conn.commit()

# print("Created mined topics table")

topics_str = ', '.join(df['topic'].tolist())

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)
client = AzureOpenAI(  
        azure_endpoint=openai_api_base,  
        azure_ad_token_provider=token_provider,  
        api_version=openai_api_version,  
    )

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

    # GPT-4o model client
    response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": topic_prompt},
                ],
                temperature=0,
            )

    res = response.choices[0].message.content
    return(json.loads(res.replace("```json",'').replace("```",'')))

import tiktoken
# Function to count the number of tokens in a string using tiktoken
def count_tokens(text, encoding='gpt-4'):
    tokenizer = tiktoken.encoding_for_model(encoding)
    tokens = tokenizer.encode(text)
    return len(tokens)

# Function to split a comma-separated string into chunks that fit within max_tokens
def split_data_into_chunks(text, max_tokens=2000, encoding='gpt-4'):
    tokenizer = tiktoken.encoding_for_model(encoding)
    
    # Split the string by commas
    items = text.split(',')
    
    current_chunk = []
    all_chunks = []
    current_token_count = 0

    for item in items:
        item = item.strip()  # Clean up any extra whitespace
        # Count the tokens for the current item
        item_token_count = len(tokenizer.encode(item))
        
        # Check if adding the item exceeds the max token limit
        if current_token_count + item_token_count > max_tokens:
            # Save the current chunk and start a new one
            all_chunks.append(', '.join(current_chunk))
            current_chunk = [item]
            current_token_count = item_token_count
        else:
            # Add item to the current chunk
            current_chunk.append(item)
            current_token_count += item_token_count

    # Append the last chunk if it has any content
    if current_chunk:
        all_chunks.append(', '.join(current_chunk))

    return all_chunks

# Define the max tokens per chunk (4096 for GPT-4)
max_tokens = 3096

# Split the string into chunks
chunks = split_data_into_chunks(topics_str, max_tokens)

def reduce_data_until_fits(topics_str, max_tokens, client):
    if len(topics_str) <= max_tokens:
        return call_gpt4(topics_str, client)
    chunks = split_data_into_chunks(topics_str)
    # print(chunks)
    reduced_data = []

    for idx, chunk in enumerate(chunks):
        print(f"Processing chunk {idx + 1}/{len(chunks)}...")
        try:
            result = call_gpt4(chunk, client)
            topics_object = res #json.loads(res)
            for object1 in topics_object['topics']:
                reduced_data.extend([object1['label']])
        except Exception as e:
            print(f"Error processing chunk {idx + 1}: {str(e)}")
    combined_data = ", ".join(reduced_data)
    return reduce_data_until_fits(combined_data, max_tokens, client)


# res = reduce_data_until_fits(topics_str, max_tokens, client)
res = call_gpt4(topics_str, client)

topics_object = res #json.loads(res)
reduced_data = []
for object1 in topics_object['topics']:
    cursor.execute(f"INSERT INTO km_mined_topics (label, description) VALUES (?,?)", (object1['label'], object1['description']))
print("function completed")
# print(res)
conn.commit()

sql_stmt = 'SELECT label FROM km_mined_topics'
cursor.execute(sql_stmt)

rows = [tuple(row) for row in cursor.fetchall()]
column_names = [i[0] for i in cursor.description]
df_topics = pd.DataFrame(rows, columns=column_names)

mined_topics_list = df_topics['label'].tolist()
mined_topics =  ", ".join(mined_topics_list) 

# Function to get the mined topic mapping for a given input text and list of topics
def get_mined_topic_mapping(input_text, list_of_topics):
    prompt = f'''You are a data analysis assistant to help find the closest topic for a given text {input_text} 
                from a list of topics - {list_of_topics}.
                ALWAYS only return a topic from list - {list_of_topics}. Do not add any other text.'''

    # GPT-4o model client
    response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )

    return(response.choices[0].message.content)

sql_stmt = 'SELECT * FROM processed_data'
cursor.execute(sql_stmt)

rows = [tuple(row) for row in cursor.fetchall()]
column_names = [i[0] for i in cursor.description]
df_processed_data = pd.DataFrame(rows, columns=column_names)
counter = 0
df_processed_data = df_processed_data[df_processed_data['ConversationId'].isin(conversationIds)]

# call get_mined_topic_mapping function for each row in the dataframe and update the mined_topic column in the database table
for index, row in df_processed_data.iterrows():
    # print(row['topic'])
    mined_topic_str = get_mined_topic_mapping(row['topic'], str(mined_topics_list))
    cursor.execute(f"UPDATE processed_data SET mined_topic = ? WHERE ConversationId = ?", (mined_topic_str, row['ConversationId']))
    # print(f"Updated mined_topic for ConversationId: {row['ConversationId']}")
conn.commit()

# update processed data to be used in RAG
cursor.execute('DROP TABLE IF EXISTS km_processed_data')
conn.commit()

create_processed_data_sql = """CREATE TABLE km_processed_data (
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
            );"""
cursor.execute(create_processed_data_sql)
conn.commit()

sql_stmt = '''select ConversationId, StartTime, EndTime, Content, summary, satisfied, sentiment, 
key_phrases as keyphrases, complaint, mined_topic as topic from processed_data'''

cursor.execute(sql_stmt)

rows = cursor.fetchall()
data_list = [list(row) for row in rows]
import_table = 'km_processed_data'

columns = ["ConversationId", "StartTime", "EndTime", "Content", "summary", "satisfied", "sentiment", 
           "keyphrases", "complaint", "topic"]
columns_str = ", ".join(columns)
placeholders = ", ".join(["?"] * len(columns))  # Generate `?` placeholders for values

# Insert statement
insert_sql = f"INSERT INTO {import_table} ({columns_str}) VALUES ({placeholders})"

print("Inserting data into km_processed_data table...")
print("Data count:", len(data_list))
# Bulk insert using executemany()
cursor.executemany(insert_sql, data_list)

conn.commit()

sql_stmt = '''select ConversationId, key_phrases, sentiment, mined_topic as topic, StartTime from processed_data'''
cursor.execute(sql_stmt)
rows = [tuple(row) for row in cursor.fetchall()]

column_names = [i[0] for i in cursor.description]
df = pd.DataFrame(rows, columns=column_names)
columns_lst = df.columns
# print(columns_lst)

df = df[df['ConversationId'].isin(conversationIds)]
for idx, row in df.iterrows(): 
    key_phrases = row['key_phrases'].split(',')
    for key_phrase in key_phrases:
        key_phrase = key_phrase.strip()
        cursor.execute(f"INSERT INTO processed_data_key_phrases (ConversationId, key_phrase, sentiment, topic, StartTime) VALUES (?,?,?,?,?)", (row['ConversationId'], key_phrase, row['sentiment'], row['topic'], row['StartTime']))
conn.commit()
print("Inserted data into processed_data_key_phrases table")

# to adjust the dates to current date
# Get today's date
today = datetime.today()
# Get the max StartTime from the processed_data table
cursor.execute("SELECT MAX(CAST(StartTime AS DATETIME)) FROM [dbo].[processed_data]")
max_start_time = cursor.fetchone()[0]
# Calculate the days difference
days_difference = (today - max_start_time).days - 1 if max_start_time else 0

# Update processed_data table
cursor.execute(f"UPDATE [dbo].[processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference, days_difference))
# Update km_processed_data table
cursor.execute(f"UPDATE [dbo].[km_processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference, days_difference))
# Update processed_data_key_phrases table
cursor.execute(f"UPDATE [dbo].[processed_data_key_phrases] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference))

conn.commit()
print("Updated StartTime and EndTime in processed_data, km_processed_data, and processed_data_key_phrases tables")
cursor.close()
conn.close()
