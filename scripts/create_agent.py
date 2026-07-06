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
    - AZURE_AI_AGENT_MODEL: Model deployment name (default: gpt-5.1)
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
parser.add_argument("--scenario", type=str,
                    help="Scenario key from scenarios.json (selects the agent prompt)")
args = parser.parse_args()

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
config_dir = os.path.join(project_root, "data", "config")
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
MODEL = os.getenv("AZURE_AI_AGENT_MODEL") or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5.1")

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
    """Load scenario-tailored instructions from agent_prompt.txt.

    Generates them via generate_agent_prompt.py if missing.
    """
    prompt_path = os.path.join(config_dir, "agent_prompt.txt")
    # Always regenerate the prompt so it matches the current scenario.
    print("  Generating scenario prompt...")
    import subprocess
    cmd = [sys.executable, os.path.join(script_dir, "generate_agent_prompt.py")]
    if args.scenario:
        cmd += ["--scenario", args.scenario]
    subprocess.run(cmd, check=False)
    if os.path.exists(prompt_path):
        with open(prompt_path, encoding="utf-8") as f:
            return f.read()
    return ("You are a knowledge mining assistant. Use Azure AI Search to ground every "
            "answer in the knowledge base. If no documents match, say so.")


instructions = build_agent_instructions()
print(f"\nBuilt instructions ({len(instructions)} chars)")

# Determine scenario tool capabilities directly from scenarios.json.
# json/csv/wav scenarios have structured analytics (SQL); pdf-only are search-only.
# An explicit `sql_enabled` flag wins. Default to search-only if unknown.
USE_SQL = False
_scenario_key = args.scenario or ""
_scenarios_path = os.path.join(config_dir, "scenarios.json")
if os.path.exists(_scenarios_path):
    with open(_scenarios_path, encoding="utf-8") as _f:
        _sc = json.load(_f).get("scenarios", {}).get(_scenario_key, {})
    if "sql_enabled" in _sc:
        USE_SQL = bool(_sc["sql_enabled"])
    else:
        USE_SQL = any(t in ("json", "csv", "wav") for t in _sc.get("data_types", []))

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

# Add the SQL tool only for scenarios with structured analytics data.
if USE_SQL:
    try:
        from azure.ai.projects.models import FunctionTool
        agent_tools.append(FunctionTool(
            name="get_sql_response",
            description="Execute T-SQL on the documents table to retrieve counts, "
                        "aggregations, sentiment/topic breakdowns, and metrics.",
            parameters={
                "type": "object",
                "properties": {
                    "sql_query": {
                        "type": "string",
                        "description": "A valid T-SQL query against the documents table.",
                    }
                },
                "required": ["sql_query"],
            },
        ))
        print("  Added SQL function tool: get_sql_response")
    except ImportError:
        print("  FunctionTool unavailable — SQL tool skipped (search-only)")
else:
    print("  Search-only scenario — SQL tool not added")

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

config_dir = os.path.join(project_root, "data", "config")
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
    "scenario": _scenario_key,
    "use_sql": USE_SQL,
})

with open(agent_ids_path, "w") as f:
    json.dump(agent_ids, f, indent=2)

print(f"\n[OK] Agent config saved to: {agent_ids_path}")

# Persist agent names so the API and test scripts can find them.
def set_azd_env(key, value):
    """Set a key in the azd environment."""
    import subprocess
    subprocess.run(["azd", "env", "set", key, value], check=False, shell=True,
                   capture_output=True)
    os.environ[key] = value

set_azd_env("AGENT_NAME_CHAT", CHAT_AGENT_NAME)
set_azd_env("AGENT_NAME_TITLE", TITLE_AGENT_NAME)
print(f"[OK] azd env set: AGENT_NAME_CHAT={CHAT_AGENT_NAME}, AGENT_NAME_TITLE={TITLE_AGENT_NAME}")

# Update the API App Service with the agent names so the running app picks them up.
def update_app_service_agent_names():
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    resource_group = os.getenv("RESOURCE_GROUP_NAME") or os.getenv("AZURE_RESOURCE_GROUP")
    app_name = os.getenv("API_APP_NAME")
    if not (subscription_id and resource_group and app_name):
        print("  [SKIP] App Service update — set AZURE_SUBSCRIPTION_ID, RESOURCE_GROUP_NAME, API_APP_NAME")
        return
    try:
        from azure.mgmt.web import WebSiteManagementClient
        web_client = WebSiteManagementClient(credential, subscription_id)
        current = web_client.web_apps.list_application_settings(resource_group, app_name)
        props = dict(current.properties or {})
        props.update({"AGENT_NAME_CHAT": CHAT_AGENT_NAME, "AGENT_NAME_TITLE": TITLE_AGENT_NAME})
        web_client.web_apps.update_application_settings(resource_group, app_name, {"properties": props})
        print(f"  [OK] App Service '{app_name}' agent settings updated")
    except Exception as e:
        print(f"  [WARN] Failed to update App Service: {e}")

update_app_service_agent_names()



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
