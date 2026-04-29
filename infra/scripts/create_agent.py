"""
create_agent.py - Create Azure AI Foundry Agent for Knowledge Mining Platform

Creates an AI agent that can search and answer questions about ingested documents
using Azure AI Search as the retrieval tool.

Usage:
    python infra/scripts/create_agent.py
    python infra/scripts/create_agent.py --index-name my-custom-index
    python infra/scripts/create_agent.py --agent-name MyAgent

Prerequisites:
    - Azure AI Foundry project deployed
    - Azure AI Search index populated with documents
    - .env file configured with required environment variables

Environment Variables:
    - AZURE_AI_AGENT_ENDPOINT: Azure AI Foundry project endpoint
    - AZURE_AI_AGENT_MODEL: Model deployment name (default: gpt-4o)
    - AZURE_SEARCH_ENDPOINT: Azure AI Search endpoint
    - AZURE_SEARCH_INDEX_NAME: AI Search index name
    - AZURE_AI_SEARCH_CONNECTION_NAME: AI Search connection name in AI Foundry
"""

import os
import sys
import json
import argparse

parser = argparse.ArgumentParser(description="Create AI Foundry Agent for Knowledge Mining")
parser.add_argument("--agent-name", type=str, default="ChatAgent",
                    help="Name for the chat agent (default: ChatAgent)")
parser.add_argument("--index-name", type=str,
                    help="Azure AI Search index name (overrides env)")
parser.add_argument("--connection-name", type=str,
                    help="Azure AI Search connection name (overrides env)")
args = parser.parse_args()

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
env_path = os.path.join(project_root, ".env")

if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key and value:
                    os.environ.setdefault(key, value)

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    AzureAISearchTool,
    AzureAISearchToolResource,
    AISearchIndexResource,
)

# ============================================================================
# Configuration
# ============================================================================

ENDPOINT = os.getenv("AZURE_AI_AGENT_ENDPOINT")
MODEL = os.getenv("AZURE_AI_AGENT_MODEL") or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")

# Search configuration
SEARCH_CONNECTION_NAME = args.connection_name or os.getenv("AZURE_AI_SEARCH_CONNECTION_NAME")
INDEX_NAME = args.index_name or os.getenv("AZURE_SEARCH_INDEX_NAME", "knowledge-mining-index")

# Agent names
CHAT_AGENT_NAME = args.agent_name
TITLE_AGENT_NAME = "SummaryAgent"

# Validation
if not ENDPOINT:
    print("ERROR: AZURE_AI_AGENT_ENDPOINT not set")
    print("       Set it in your .env file or as an environment variable")
    sys.exit(1)

if not SEARCH_CONNECTION_NAME:
    print("ERROR: AZURE_AI_SEARCH_CONNECTION_NAME not set")
    print("       Set it in your .env file or pass --connection-name")
    sys.exit(1)

# ============================================================================
# Build Agent Instructions
# ============================================================================

def build_agent_instructions():
    """Build generic agent instructions for knowledge mining."""

    return """You are a knowledge mining assistant that helps users explore and understand a document knowledge base.

## Tools

**Azure AI Search** - Search the document knowledge base
- Use this tool to find relevant documents when answering user questions
- The search index contains document text with metadata

## When to Use the Search Tool
- **Factual questions** → Search first, then answer from results
- **Summarization requests** → Search for relevant documents, then summarize
- **Theme/pattern analysis** → Search broadly, then identify patterns
- **Specific lookups** → Search by keywords, topics, or categories

## Response Guidelines
- Always ground your answers in the retrieved documents
- If the search returns no relevant results, say so honestly
- Use structured formatting (bullet points, tables) when presenting multiple items
- For theme/pattern questions, identify and group recurring topics across documents

## Greeting
If the question is a greeting (e.g., "Hello", "Hi"), respond naturally and offer to help explore the knowledge base.

## Content Safety
- Only answer questions that can be addressed from the document knowledge base
- If asked about unrelated topics, politely redirect to knowledge base queries
- Do not invent or fabricate information not present in the documents
- If you cannot answer from available data, say: "I cannot answer this question from the available documents. Please try a different question."
"""


instructions = build_agent_instructions()
print(f"\nBuilt instructions ({len(instructions)} chars)")

# Title Agent Instructions
title_agent_instructions = """You are a specialized agent for generating concise conversation titles.
Create 4-word or less titles that capture the main topic or question.
Focus on key nouns and actions (e.g., 'Top Support Issues', 'Product FAQ Summary').
Never use quotation marks or punctuation.
Be descriptive but concise.
Respond only with the title, no additional commentary."""

# ============================================================================
# Build Search Tool
# ============================================================================

def build_search_tool():
    """Build Azure AI Search tool for document retrieval."""
    tool = AzureAISearchTool(
        azure_ai_search=AzureAISearchToolResource(
            indexes=[
                AISearchIndexResource(
                    project_connection_id=SEARCH_CONNECTION_NAME,
                    index_name=INDEX_NAME,
                    query_type="simple",
                )
            ]
        )
    )
    print(f"  Added Azure AI Search tool: {INDEX_NAME}")
    return tool


agent_tools = [build_search_tool()]

# ============================================================================
# Print Configuration
# ============================================================================

print(f"\n{'='*60}")
print(f"Creating Knowledge Mining Agent")
print(f"{'='*60}")
print(f"Endpoint: {ENDPOINT}")
print(f"Model: {MODEL}")
print(f"Agent Name: {CHAT_AGENT_NAME}")
print(f"Search Index: {INDEX_NAME}")
print(f"Search Connection: {SEARCH_CONNECTION_NAME}")

# ============================================================================
# Create the Agent
# ============================================================================

print("\nInitializing AI Project Client...")
credential = DefaultAzureCredential()

try:
    project_client = AIProjectClient(
        endpoint=ENDPOINT,
        credential=credential,
    )
    print("[OK] AI Project Client initialized")
except Exception as e:
    print(f"[FAIL] Failed to initialize client: {e}")
    sys.exit(1)


def create_agents(project_client, instructions, title_instructions, agent_tools):
    """Create ChatAgent and TitleAgent in AI Foundry."""
    with project_client:
        # Delete existing agent if it exists
        print(f"\nChecking if agent '{CHAT_AGENT_NAME}' already exists...")
        try:
            existing_agent = project_client.agents.get(CHAT_AGENT_NAME)
            if existing_agent:
                print("  Found existing agent, deleting...")
                project_client.agents.delete(CHAT_AGENT_NAME)
                print("[OK] Deleted existing agent")
        except Exception:
            print("  No existing agent found")

        # Create chat agent
        print(f"\nCreating agent with Azure AI Search tool...")
        agent_definition = PromptAgentDefinition(
            model=MODEL,
            instructions=instructions,
            tools=agent_tools,
        )

        chat_agent = project_client.agents.create_version(
            agent_name=CHAT_AGENT_NAME,
            definition=agent_definition,
        )

        print(f"\n[OK] Chat agent created successfully!")
        print(f"  Agent Name: {CHAT_AGENT_NAME}")

        # Print tool info
        if hasattr(chat_agent, "definition") and chat_agent.definition and hasattr(chat_agent.definition, "tools"):
            print("\n  Tools registered on agent:")
            for i, tool in enumerate(chat_agent.definition.tools, 1):
                tool_type = type(tool).__name__
                if hasattr(tool, "azure_ai_search"):
                    indexes = tool.azure_ai_search.indexes if hasattr(tool.azure_ai_search, "indexes") else []
                    idx_names = [getattr(idx, "index_name", None) or getattr(idx, "name", "unknown") for idx in indexes]
                    print(f"    {i}. [{tool_type}] indexes: {', '.join(idx_names)}")
                else:
                    print(f"    {i}. [{tool_type}]")
        else:
            print(f"    Configured tools: {len(agent_tools)}")

        # Delete existing title agent if it exists
        try:
            existing_title = project_client.agents.get(TITLE_AGENT_NAME)
            if existing_title:
                project_client.agents.delete(TITLE_AGENT_NAME)
        except Exception:
            pass

        # Create title agent
        title_definition = PromptAgentDefinition(
            model=MODEL,
            instructions=title_instructions,
            tools=[],
        )

        title_agent = project_client.agents.create_version(
            agent_name=TITLE_AGENT_NAME,
            definition=title_definition,
        )
        print(f"\n[OK] Title agent created successfully!")

    return chat_agent, title_agent


try:
    chat_agent, title_agent = create_agents(
        project_client, instructions, title_agent_instructions, agent_tools
    )
except Exception as e:
    print(f"\n[FAIL] Failed to create agent: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Save Agent Configuration
# ============================================================================

config_dir = os.path.join(project_root, "Sample_Data", "config")
os.makedirs(config_dir, exist_ok=True)

agent_ids_path = os.path.join(config_dir, "agent_ids.json")
agent_ids = {}
if os.path.exists(agent_ids_path):
    with open(agent_ids_path) as f:
        agent_ids = json.load(f)

agent_ids.update({
    "chat_agent_name": CHAT_AGENT_NAME,
    "title_agent_name": TITLE_AGENT_NAME,
    "search_index": INDEX_NAME,
    "search_connection": SEARCH_CONNECTION_NAME,
    "model": MODEL,
})

with open(agent_ids_path, "w") as f:
    json.dump(agent_ids, f, indent=2)

print(f"\n[OK] Agent config saved to: {agent_ids_path}")

# ============================================================================
# Summary
# ============================================================================

print(f"""
{'='*60}
Knowledge Mining Agents Created Successfully!
{'='*60}

Chat Agent:
  Agent Name: {CHAT_AGENT_NAME}
  Model: {MODEL}
  Tools:
    1. Azure AI Search - {INDEX_NAME}

Title Agent:
  Agent Name: {TITLE_AGENT_NAME}
  Model: {MODEL}
  Tools: None (text generation only)

Next step:
  python infra/scripts/test_agent.py
""")
