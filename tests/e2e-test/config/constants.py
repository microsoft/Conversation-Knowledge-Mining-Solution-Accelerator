"""
Constants Module
Contains configuration constants and loads test data
"""
from dotenv import load_dotenv
import os
import json

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

#remove 'tests/e2e-test' from below path if running locally

# Load Telecom prompts
telecom_json_file_path = os.path.join(repo_root, 'tests/e2e-test', 'testdata', 'telecom_prompts.json')
with open(telecom_json_file_path, 'r') as file:
    telecom_data = json.load(file)
    telecom_questions = telecom_data['questions']

# Load ITHelpdesk prompts
ithelpdesk_json_file_path = os.path.join(repo_root, 'tests/e2e-test', 'testdata', 'ithelpdesk_prompts.json')
with open(ithelpdesk_json_file_path, 'r') as file:
    ithelpdesk_data = json.load(file)
    ithelpdesk_questions = ithelpdesk_data['questions']

# Backward compatibility - keep 'questions' as alias for telecom_questions
questions = telecom_questions

