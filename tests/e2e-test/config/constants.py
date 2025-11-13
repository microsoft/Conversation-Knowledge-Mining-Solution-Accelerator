"""
Constants Module
Contains configuration constants and loads test data
"""
import json
import os
from dotenv import load_dotenv

load_dotenv()
URL = os.getenv('url')
if URL.endswith('/'):
    URL = URL[:-1]

load_dotenv()
API_URL = os.getenv('api_url')
if API_URL.endswith('/'):
    API_URL = API_URL[:-1]

# Get the absolute path to the repository root
repo_root = os.getenv('GITHUB_WORKSPACE', os.getcwd())

# Construct the absolute path to the JSON file
#note: may have to remove 'tests/e2e-test' from below when running locally
json_file_path = os.path.join(repo_root, 'tests/e2e-test', 'testdata', 'prompts.json')

with open(json_file_path, 'r', encoding='utf-8') as file:
    data = json.load(file)
    questions = data['questions']
