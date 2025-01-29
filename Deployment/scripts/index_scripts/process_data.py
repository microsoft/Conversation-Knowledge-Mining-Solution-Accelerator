import os
import openai
import json
import time
import ast
# from azure.ai.inference import ChatCompletionsClient
# from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
# from dotenv import load_dotenv
import pandas as pd
from azure.keyvault.secrets import SecretClient  
from azure.identity import DefaultAzureCredential 
from openai import AzureOpenAI
import pymssql
from datetime import datetime
import re
import tiktoken

# load_dotenv()
key_vault_name = 'kv_to-be-replaced'

index_name = "call_transcripts_index"


file_system_client_name = "data"
directory = 'calltranscripts' 
# csv_file_name = 'transcriptsdata/call_transcripts_metadata/transcripts_metadata.csv'

def get_secrets_from_kv(kv_name, secret_name):

    # Set the name of the Azure Key Vault  
    key_vault_name = kv_name 
    credential = DefaultAzureCredential()

    # Create a secret client object using the credential and Key Vault name  
    secret_client =  SecretClient(vault_url=f"https://{key_vault_name}.vault.azure.net/", credential=credential)  

    # Retrieve the secret value  
    return(secret_client.get_secret(secret_name).value)

search_endpoint = get_secrets_from_kv(key_vault_name,"AZURE-SEARCH-ENDPOINT")
search_key =  get_secrets_from_kv(key_vault_name,"AZURE-SEARCH-KEY")

# Use for Phi-3 model endpoint
# aistudio_api_key  =  get_secrets_from_kv(key_vault_name,"AZURE-AISTUDIO-API-KEY")
# aistudio_api_base = get_secrets_from_kv(key_vault_name,"AZURE-AISTUDIO-MODEL-ENDPOINT")
# client = ChatCompletionsClient(endpoint=aistudio_api_base, credential=AzureKeyCredential(aistudio_api_key))

# Use for GPT-4 model endpoint and embeddings model endpoint
openai_api_key  =  get_secrets_from_kv(key_vault_name,"AZURE-OPENAI-KEY")
openai_api_base =  get_secrets_from_kv(key_vault_name,"AZURE-OPENAI-ENDPOINT")
openai_api_version = get_secrets_from_kv(key_vault_name,"AZURE-OPENAI-PREVIEW-API-VERSION") 
deployment = "gpt-4o-mini"

client = AzureOpenAI(  
        azure_endpoint=openai_api_base,  
        api_key=openai_api_key,  
        api_version=openai_api_version,  
    )  


# Create the search index
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
    SimpleField(name="id", type=SearchFieldDataType.String, key=True, sortable=True, filterable=True, facetable=True),
    SearchableField(name="chunk_id", type=SearchFieldDataType.String),
    SearchableField(name="content", type=SearchFieldDataType.String),
    SearchableField(name="sourceurl", type=SearchFieldDataType.String),
    SearchField(name="contentVector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True, vector_search_dimensions=1536, vector_search_profile_name="myHnswProfile"),
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

# Function: Get Embeddings 
def get_embeddings(text: str,openai_api_base,openai_api_version,openai_api_key):
    model_id = "text-embedding-ada-002"
    client = AzureOpenAI(
        api_version=openai_api_version,
        azure_endpoint=openai_api_base,
        api_key = openai_api_key
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

# get the details of the content from call transcripts
def get_details(input_text):
    # Construct the prompt  
    prompt = f'''You are a JSON formatter for extracting information out of a single chat conversation -
            {input_text}
            Summarize the conversation, key: summary . 
            Is the customer satisfied with the agent interaction (Yes or No), key: satisfied . 
            Identify the sentiment of the conversation (Positive, Neutral, Negative), key: sentiment . 
            Identify the single primary topic of the conversation in 6 words or less,key: topic . 
            Identify the top 10 key phrases as comma seperated string excluding people names , key: keyPhrases .
            Identify the single primary complaint of the conversation in 3 words or less, key: complaint .
            Answer in JSON machine-readable format, using the keys from above. 
            Pretty print the JSON and make sure that it is properly closed at the end and do not generate any other content.'''

            # Identify the single primary complaint of the conversation in 3 words or less, key: complaint. 

    # Phi-3 model client
    # response = client.complete(
    #     messages=[
    #         # SystemMessage(content=prompt),
    #         UserMessage(content=prompt),
    #     ],
    #     max_tokens = 500,
    #     temperature = 0,
    #     top_p = 1
    # )

    # GPT-4o model client
    response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )

    res = response.choices[0].message.content
    return(json.loads(res.replace("```json",'').replace("```",'')))

#add documents to the index

import json
import base64
import time
# import pandas as pd
from azure.search.documents import SearchClient
import os

# foldername = 'call_transcripts'
# path_name = f'Data/{foldername}/'
# # # paths = mssparkutils.fs.ls(path_name)

# paths = os.listdir(path_name)

from azure.storage.filedatalake import (
    DataLakeServiceClient,
    DataLakeDirectoryClient,
    FileSystemClient
)

account_name =  get_secrets_from_kv(key_vault_name, "ADLS-ACCOUNT-NAME")

account_url = f"https://{account_name}.dfs.core.windows.net"

credential = DefaultAzureCredential()
service_client = DataLakeServiceClient(account_url, credential=credential,api_version='2023-01-03') 

file_system_client = service_client.get_file_system_client(file_system_client_name)  
directory_name = directory
paths = file_system_client.get_paths(path=directory_name)
print(paths)

search_credential = AzureKeyCredential(search_key)

search_client = SearchClient(search_endpoint, index_name, search_credential)
index_client = SearchIndexClient(endpoint=search_endpoint, credential=search_credential)

# metadata_filepath = f'Data/{foldername}/meeting_transcripts_metadata/transcripts_metadata.csv'
# # df_metadata = spark.read.format("csv").option("header","true").option("multiLine", "true").option("quote", "\"").option("escape", "\"").load(metadata_filepath).toPandas()
# df_metadata = pd.read_csv(metadata_filepath)
# display(df_metadata)


import pandas as pd
import pymssql
import os
from datetime import datetime

from azure.keyvault.secrets import SecretClient  
from azure.identity import DefaultAzureCredential 
server =  get_secrets_from_kv(key_vault_name,"SQLDB-SERVER")
database = get_secrets_from_kv(key_vault_name,"SQLDB-DATABASE")
username =  get_secrets_from_kv(key_vault_name,"SQLDB-USERNAME")
password =  get_secrets_from_kv(key_vault_name,"SQLDB-PASSWORD")

conn = pymssql.connect(server, username, password, database)
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
                sentiment varchar(255)
            );"""
cursor.execute(create_processed_data_sql)
conn.commit()

# Read the CSV file into a Pandas DataFrame
# file_path = csv_file_name
# print(file_path)
# file_client = file_system_client.get_file_client(file_path)
# csv_file = file_client.download_file()
# df_metadata = pd.read_csv(csv_file, encoding='utf-8')
# print(df_metadata)  

docs = []
counter = 0

for path in paths:
    # file_path = f'Data/{foldername}/meeting_transcripts/' + path
    # with open(file_path, "r") as file:
    #     data = json.load(file)

    file_client = file_system_client.get_file_client(path.name)
    data_file = file_client.download_file()
    data = json.load(data_file)
    text = data['Content']
    # print(text)

    result = get_details(text)
    # print(result)
    
    cursor.execute(f"INSERT INTO processed_data (ConversationId, EndTime, StartTime, Content, summary, satisfied, sentiment, topic, key_phrases, complaint) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (data['ConversationId'], data['EndTime'], data['StartTime'], data['Content'], result['summary'], result['satisfied'], result['sentiment'], result['topic'], result['keyPhrases'], result['complaint']))    
    conn.commit()

    key_phrases = result['keyPhrases'].split(',')
    for key_phrase in key_phrases:
        key_phrase = key_phrase.strip()
        cursor.execute(f"INSERT INTO processed_data_key_phrases (ConversationId, key_phrase, sentiment) VALUES (%s,%s,%s)", (data['ConversationId'], key_phrase, result['sentiment']))
    
    filename = path.name.split('/')[-1]
    document_id = data['ConversationId'] #filename.split('convo_', 1)[1].split('_')[0]
    
    
    # print(document_id)
    # df_file_metadata = df_metadata[df_metadata['ConversationId']==str(document_id)].iloc[0]
    # print(df_file_metadata)
    chunks = chunk_data(text)
    chunk_num = 0
    for chunk in chunks:
        chunk_num += 1
        d = {
                "chunk_id" : document_id + '_' + str(chunk_num).zfill(2),
                "content": chunk,       
            }
        counter += 1
        try:
            v_contentVector = get_embeddings(str(d["content"]),openai_api_base,openai_api_version,openai_api_key)
        except:
            time.sleep(30)
            # print(d["content"])
            try: 
                v_contentVector = get_embeddings(str(d["content"]),openai_api_base,openai_api_version,openai_api_key)
            except: 
                v_contentVector = []

        docs.append(
            {
                    "id": base64.urlsafe_b64encode(bytes(d["chunk_id"], encoding='utf-8')).decode('utf-8'),
                    "chunk_id": d["chunk_id"],
                    "content": d["content"],
                    "sourceurl": path.name.split('/')[-1],
                    "contentVector": v_contentVector
            }
        )
  
        if counter % 10 == 0:
            result = search_client.upload_documents(documents=docs)
            docs = []
            print(f' {str(counter)} uploaded')

# upload the last batch
if docs != []:
    search_client.upload_documents(documents=docs)


sql_stmt = 'SELECT distinct topic FROM processed_data'
cursor.execute(sql_stmt)

rows = cursor.fetchall()
column_names = [i[0] for i in cursor.description]
df = pd.DataFrame(rows, columns=column_names)
# print(df)

cursor.execute('DROP TABLE IF EXISTS km_mined_topics')
conn.commit()

# write topics to the database table 
create_mined_topics_sql = """CREATE TABLE km_mined_topics (
                label varchar(255) NOT NULL PRIMARY KEY,
                description varchar(255)
            );"""
cursor.execute(create_mined_topics_sql)
conn.commit()

print("Created mined topics table")

topics_str = ', '.join(df['topic'].tolist())
# print(topics_str)

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

        Return the topics and their labels in JSON format.Always add 'topics' node and 'label', 'description' attriubtes in json.
        Do not return anything else.
        """
    # Phi-3 model client
    # response = client.complete(
    #     messages=[
    #         # SystemMessage(content=prompt),
    #         UserMessage(content=topic_prompt),
    #     ],
    #     max_tokens = 1000,
    #     temperature = 0,
    #     top_p = 1
    # )

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
# res = json.loads(res.replace("```json",'').replace("```",''))
topics_object = res #json.loads(res)
reduced_data = []
for object1 in topics_object['topics']:
    # print(object1['label'],object1['description'])
    # intert object1['label'],object1['description'] into the mined topics table
    cursor.execute(f"INSERT INTO km_mined_topics (label, description) VALUES (%s,%s)", (object1['label'], object1['description']))
print("function completed")
# print(res)
conn.commit()

sql_stmt = 'SELECT label FROM km_mined_topics'
cursor.execute(sql_stmt)

rows = cursor.fetchall()
column_names = [i[0] for i in cursor.description]
df_topics = pd.DataFrame(rows, columns=column_names)


mined_topics_list = df_topics['label'].tolist()
mined_topics =  ", ".join(mined_topics_list)
# print(mined_topics)

# Function to get the mined topic mapping for a given input text and list of topics
def get_mined_topic_mapping(input_text, list_of_topics):
    # Construct the prompt  
    # prompt = f'''You are a data analysis assistant to help find topic from a given text {input_text} 
    #          and a list of predefined topics {list_of_topics}.  
    #          Always find the topic from the predefined list. Do not make any assumptions or add new topics.
    #         Only return topic and nothing else.'''

    prompt = f'''You are a data analysis assistant to help find the closest topic for a given text {input_text} 
                from a list of topics - {list_of_topics}.
                ALLWAYS only return a topic from list - {list_of_topics}. Do not add any other text.'''

    # Phi-3 model client
    # response = client.complete(
    #     messages=[
    #         # SystemMessage(content=prompt),
    #         UserMessage(content=prompt),
    #     ],
    #     max_tokens = 500,
    #     temperature = 0,
    #     top_p = 1
    # )

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

rows = cursor.fetchall()
column_names = [i[0] for i in cursor.description]
df_processed_data = pd.DataFrame(rows, columns=column_names)
counter = 0
# call get_mined_topic_mapping function for each row in the dataframe and update the mined_topic column in the database table
for index, row in df_processed_data.iterrows():
    mined_topic_str = get_mined_topic_mapping(row['topic'], str(mined_topics_list))
    # update the dataframe
    # df_processed_data.at[index, 'mined_topic'] = mined_topic_str
    
    cursor.execute(f"UPDATE processed_data SET mined_topic = %s WHERE ConversationId = %s", (mined_topic_str, row['ConversationId']))
    # print(f"Updated mined_topic for ConversationId: {row['ConversationId']}")
conn.commit()

import uuid
import random
sql_stmt = 'SELECT * FROM processed_data'
cursor.execute(sql_stmt)

rows = cursor.fetchall()
column_names = [i[0] for i in cursor.description]
df = pd.DataFrame(rows, columns=column_names)
columns_lst = df.columns
df_append = pd.DataFrame(df, columns=columns_lst)
days_list = [7, 14, 21, 28, 35, 42]
rows = [5, 7, 8]

# Define the sentiment values and their probabilities
sentiment_values = ['Negative', 'Positive', 'Neutral']
probabilities = [0.7, 0.2, 0.1]  # 70% for value1 and 30% for value2

for idx, row in df.iterrows():
    for i in range(random.choice(rows)):
    
        days = random.choice(days_list)
       
        if ('billing' in row['mined_topic'].lstrip().lower()) or ('issue' in row['mined_topic'].lstrip().lower()):
            
            row['sentiment'] = random.choices(sentiment_values, probabilities)[0] #'Negative'
            row['satisfied'] = 'No'
            row['EndTime'] = pd.to_datetime(row['EndTime']) - pd.to_timedelta(f"{days} days")
            row['StartTime'] = pd.to_datetime(row['StartTime']) - pd.to_timedelta(f"{days} days")
            row['EndTime'] = row['EndTime'].strftime('%Y-%m-%d %H:%M:%S')
            row['StartTime'] = row['StartTime'].strftime('%Y-%m-%d %H:%M:%S')
            row['ConversationId'] = str(uuid.uuid4())
                
        else:
            row['ConversationId'] = str(uuid.uuid4())
            row['EndTime'] = pd.to_datetime(row['EndTime']) - pd.to_timedelta(f"{days} days")
            row['StartTime'] = pd.to_datetime(row['StartTime']) - pd.to_timedelta(f"{days} days")
            row['EndTime'] = row['EndTime'].strftime('%Y-%m-%d %H:%M:%S')
            row['StartTime'] = row['StartTime'].strftime('%Y-%m-%d %H:%M:%S')
        # write the new row to the processed_data table
        cursor.execute(f"INSERT INTO processed_data (ConversationId, EndTime, StartTime, Content, summary, satisfied, sentiment, topic, key_phrases, complaint, mined_topic) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (row['ConversationId'], row['EndTime'], row['StartTime'], row['Content'], row['summary'], row['satisfied'], row['sentiment'], row['topic'], row['key_phrases'], row['complaint'], row['mined_topic']))
       
        
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
# sql_stmt = 'SELECT * FROM processed_data'
sql_stmt = '''select ConversationId, StartTime, EndTime, Content, summary, satisfied, sentiment, 
key_phrases as keyphrases, complaint, mined_topic as topic from processed_data'''

cursor.execute(sql_stmt)

rows = cursor.fetchall()
column_names = [i[0] for i in cursor.description]
df = pd.DataFrame(rows, columns=column_names)
# df.rename(columns={'mined_topic': 'topic'}, inplace=True)
# print(df.columns)
for idx, row in df.iterrows():
    # row['ConversationId'] = str(uuid.uuid4())
    cursor.execute(f"INSERT INTO km_processed_data (ConversationId, StartTime, EndTime, Content, summary, satisfied, sentiment, keyphrases, complaint, topic) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (row['ConversationId'], row['StartTime'], row['EndTime'], row['Content'], row['summary'], row['satisfied'], row['sentiment'], row['keyphrases'], row['complaint'], row['topic']))
conn.commit()

# update keyphrase table after the data update
cursor.execute('DROP TABLE IF EXISTS processed_data_key_phrases')
conn.commit()
print("Dropped processed_data_key_phrases table")

create_processed_data_sql = """CREATE TABLE processed_data_key_phrases (
                ConversationId varchar(255),
                key_phrase varchar(500), 
                sentiment varchar(255),
                topic varchar(255), 
                StartTime varchar(255),
            );"""
cursor.execute(create_processed_data_sql)
conn.commit()
print('created processed_data_key_phrases table')

sql_stmt = '''select ConversationId, key_phrases, sentiment, mined_topic as topic, StartTime from processed_data'''
cursor.execute(sql_stmt)
rows = cursor.fetchall()


column_names = [i[0] for i in cursor.description]
df = pd.DataFrame(rows, columns=column_names)
columns_lst = df.columns
print(columns_lst)

for idx, row in df.iterrows(): 

    key_phrases = row['key_phrases'].split(',')
    for key_phrase in key_phrases:
        key_phrase = key_phrase.strip()
        cursor.execute(f"INSERT INTO processed_data_key_phrases (ConversationId, key_phrase, sentiment, topic, StartTime) VALUES (%s,%s,%s,%s,%s)", (row['ConversationId'], key_phrase, row['sentiment'], row['topic'], row['StartTime']))
        # print(row['ConversationId'], key_phrase, row['sentiment'],row['topic'], row['StartTime1'])

# sql_stmt = 'SELECT ConversationId,key_Phrases,sentiment, mined_topic as topic FROM processed_data'
# cursor.execute(sql_stmt)
# rows = cursor.fetchall()

# # Generate the SQL query for insertion
# insert_query = f"INSERT INTO processed_data_key_phrases (ConversationId, key_phrase, sentiment,topic) VALUES (%s, %s, %s, %s)"

# # Perform the bulk insert
# cursor.executemany(insert_query, rows)

# chunk_size = 1000
# for i in range(0, len(rows), chunk_size):
#     cursor.executemany(insert_query, rows[i:i + chunk_size])

conn.commit()

# to adjust the dates to current date
# Get today's date
today = datetime.today()
# Get the max StartTime from the processed_data table
cursor.execute("SELECT MAX(CAST(StartTime AS DATETIME)) FROM [dbo].[processed_data]")
max_start_time = cursor.fetchone()[0]
# Calculate the days difference
days_difference = (today - max_start_time).days - 1 if max_start_time else 0

# Update processed_data table
cursor.execute(f"UPDATE [dbo].[processed_data] SET StartTime = FORMAT(DATEADD(DAY, %s, StartTime), 'yyyy-MM-dd HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, %s, EndTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference, days_difference))
# Update km_processed_data table
cursor.execute(f"UPDATE [dbo].[km_processed_data] SET StartTime = FORMAT(DATEADD(DAY, %s, StartTime), 'yyyy-MM-dd HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, %s, EndTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference, days_difference))
# Update processed_data_key_phrases table
cursor.execute(f"UPDATE [dbo].[processed_data_key_phrases] SET StartTime = FORMAT(DATEADD(DAY, %s, StartTime), 'yyyy-MM-dd HH:mm:ss')", (days_difference,))
# Commit the changes
conn.commit()

cursor.close()
conn.close()
