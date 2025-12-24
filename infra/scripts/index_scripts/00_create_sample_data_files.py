import pyodbc
import struct
import csv
import json
import os
from datetime import datetime
from azure.identity import AzureCliCredential, get_bearer_token_provider
# SQL Server setup

SQL_SERVER = '<YOUR-SQL-SERVER-NAME>.database.windows.net'
SQL_DATABASE = '<YOUR-DATABASE-NAME>'

credential = AzureCliCredential(process_timeout=30)

try: 
    driver = "{ODBC Driver 18 for SQL Server}"
    token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    connection_string = f"DRIVER={driver};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
    conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
    cursor = conn.cursor()
    print("SQL Server connection established.")
except: 
    driver = "{ODBC Driver 17 for SQL Server}"
    token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    connection_string = f"DRIVER={driver};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
    conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
    cursor = conn.cursor()
    print("SQL Server connection established.")

def export_table_to_csv(table_name, output_dir=".", cursor=cursor):
    """
    Export a SQL table to CSV file.
    
    Args:
        table_name: Name of the table to export
        output_dir: Directory to save the CSV file (default: current directory)
        cursor: Database cursor to use (default: uses the global cursor)
    
    Returns:
        Path to the created CSV file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"sample_{table_name}.csv"
    # csv_filename = f"{table_name}_{timestamp}.csv"
    csv_path = os.path.join(output_dir, csv_filename)
    
    try:
        # Query all data from the table
        query = f"SELECT * FROM {table_name}"
        print(f"Executing query: {query}")
        cursor.execute(query)
        
        # Get column names
        columns = [column[0] for column in cursor.description]
        
        # Write to CSV
        print(f"Writing data to '{csv_path}'...")
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(columns)
            
            # Write data rows
            row_count = 0
            while True:
                rows = cursor.fetchmany(1000)  # Fetch in batches for better performance
                if not rows:
                    break
                
                for row in rows:
                    # Convert each value to string, handling None values
                    writer.writerow([str(val) if val is not None else '' for val in row])
                    row_count += 1
                
                if row_count % 10000 == 0:
                    print(f"  Exported {row_count} rows...")
        
        print(f"✓ Successfully exported {row_count} rows to '{csv_path}'")
        return csv_path
        
    except Exception as e:
        print(f"Error exporting table '{table_name}': {e}")
        raise


def export_table_to_json(table_name, output_dir=".", cursor=cursor, format="json"):
    """
    Export a SQL table to JSON or JSON Lines file.
    
    Args:
        table_name: Name of the table to export
        output_dir: Directory to save the file (default: current directory)
        cursor: Database cursor to use (default: uses the global cursor)
        format: Output format - "json" for JSON array or "jsonl" for JSON Lines (default: "json")
    
    Returns:
        Path to the created file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_extension = "json" if format == "json" else "jsonl"
    filename = f"sample_{table_name}.{file_extension}"
    # filename = f"{table_name}_{timestamp}.{file_extension}"
    file_path = os.path.join(output_dir, filename)
    
    try:
        # Query all data from the table
        query = f"SELECT * FROM {table_name}"
        print(f"Executing query: {query}")
        cursor.execute(query)
        
        # Get column names
        columns = [column[0] for column in cursor.description]
        
        if format == "json":
            # Collect all rows for JSON array format
            print(f"Collecting data from table...")
            rows_data = []
            row_count = 0
            
            while True:
                rows = cursor.fetchmany(1000)  # Fetch in batches for better performance
                if not rows:
                    break
                
                for row in rows:
                    # Convert row to dictionary
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        # Convert datetime and other types to string for JSON serialization
                        if hasattr(value, 'isoformat'):
                            row_dict[col] = value.isoformat()
                        else:
                            row_dict[col] = value
                    rows_data.append(row_dict)
                    row_count += 1
                
                if row_count % 10000 == 0:
                    print(f"  Collected {row_count} rows...")
            
            # Write as JSON array
            print(f"Writing {row_count} rows to '{file_path}'...")
            with open(file_path, 'w', encoding='utf-8') as json_file:
                json.dump(rows_data, json_file, ensure_ascii=False, indent=2)
        
        else:  # jsonl format
            # Write to JSON Lines format (one JSON object per line)
            print(f"Writing data to '{file_path}'...")
            row_count = 0
            
            with open(file_path, 'w', encoding='utf-8') as jsonl_file:
                while True:
                    rows = cursor.fetchmany(1000)  # Fetch in batches for better performance
                    if not rows:
                        break
                    
                    for row in rows:
                        # Convert row to dictionary
                        row_dict = {}
                        for i, col in enumerate(columns):
                            value = row[i]
                            # Convert datetime and other types to string for JSON serialization
                            if hasattr(value, 'isoformat'):
                                row_dict[col] = value.isoformat()
                            else:
                                row_dict[col] = value
                        jsonl_file.write(json.dumps(row_dict, ensure_ascii=False) + '\n')
                        row_count += 1
                    
                    if row_count % 10000 == 0:
                        print(f"  Exported {row_count} rows...")
        
        print(f"✓ Successfully exported {row_count} rows to '{file_path}'")
        return file_path
        
    except Exception as e:
        print(f"Error exporting table '{table_name}': {e}")
        raise


# Example usage - export tables to JSON

export_table_to_json("processed_data_key_phrases", output_dir="./exported_data", format="json")
export_table_to_json("processed_data", output_dir="./exported_data", format="json")
# export_table_to_json("processed_data_key_phrases", output_dir="./exported_data", format="jsonl")
# export_table_to_json("processed_data", output_dir="./exported_data", format="jsonl")

# Close connection when done
cursor.close()
conn.close()
print("Database connection closed.")


from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
SEARCH_ENDPOINT = "https://<YOUR-SEARCH-SERVICE-NAME>.search.windows.net"
INDEX_NAME = "call_transcripts_index"

# Azure Search setup
search_credential = AzureCliCredential(process_timeout=30)
search_client = SearchClient(SEARCH_ENDPOINT, INDEX_NAME, search_credential)
index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=search_credential)
print("Azure Search setup complete.")


def export_search_index_to_json(index_name, output_dir=".", search_client=search_client, format="json"):
    """
    Export all documents from an Azure AI Search index to JSON or JSON Lines file.
    
    Args:
        index_name: Name of the search index
        output_dir: Directory to save the file (default: current directory)
        search_client: Azure Search client to use (default: uses the global search_client)
        format: Output format - "json" for JSON array or "jsonl" for JSON Lines (default: "json")
    
    Returns:
        Path to the created file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_extension = "json" if format == "json" else "jsonl"
    filename = f"sample_{index_name}.{file_extension}"
    # filename = f"{index_name}_{timestamp}.{file_extension}"
    file_path = os.path.join(output_dir, filename)
    
    try:
        # Search for all documents (empty search returns everything)
        print(f"Retrieving documents from search index '{index_name}'...")
        results = search_client.search(
            search_text="*",
            include_total_count=True,
            top=1000  # Adjust batch size as needed
        )
        
        # Collect documents
        documents = []
        doc_count = 0
        
        if format == "json":
            # Collect all documents for JSON array format
            print(f"Collecting documents...")
            for result in results:
                doc = dict(result)
                documents.append(doc)
                doc_count += 1
                
                if doc_count % 1000 == 0:
                    print(f"  Collected {doc_count} documents...")
            
            if doc_count == 0:
                print(f"No documents found in index '{index_name}'")
                return None
            
            # Write as JSON array
            print(f"Writing {doc_count} documents to '{file_path}'...")
            with open(file_path, 'w', encoding='utf-8') as json_file:
                json.dump(documents, json_file, ensure_ascii=False, indent=2)
        
        else:  # jsonl format
            # Write to JSON Lines format (one JSON object per line)
            print(f"Writing documents to '{file_path}'...")
            with open(file_path, 'w', encoding='utf-8') as jsonl_file:
                for result in results:
                    doc = dict(result)
                    jsonl_file.write(json.dumps(doc, ensure_ascii=False) + '\n')
                    doc_count += 1
                    
                    if doc_count % 1000 == 0:
                        print(f"  Exported {doc_count} documents...")
            
            if doc_count == 0:
                print(f"No documents found in index '{index_name}'")
                return None
        
        print(f"✓ Successfully exported {doc_count} documents to '{file_path}'")
        return file_path
        
    except Exception as e:
        print(f"Error exporting search index '{index_name}': {e}")
        raise


# Export search index to JSON and JSON Lines
export_search_index_to_json(INDEX_NAME, output_dir="./exported_data", format="json")
# export_search_index_to_json(INDEX_NAME, output_dir="./exported_data", format="jsonl")

