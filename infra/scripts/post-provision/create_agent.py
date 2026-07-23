"""
create_agent.py - Create Azure AI Foundry Agent for Knowledge Mining Platform

Creates an AI agent that can search and answer questions about ingested documents
using Azure AI Search as the retrieval tool.

Usage:
    python scripts/create_agent.py
    python scripts/create_agent.py --index-name my-custom-index
    python scripts/create_agent.py --agent-name MyAgent
    python scripts/create_agent.py --scenario azure_search_byod --index-name my-index

Prerequisites:
    - Azure AI Foundry project deployed
    - Azure AI Search index populated with documents
    - .env file configured with required environment variables

Environment Variables:
    - AZURE_AI_AGENT_ENDPOINT: Azure AI Foundry project endpoint
    - AZURE_AI_AGENT_MODEL: Model deployment name (default: gpt-5.2)
    - AZURE_SEARCH_ENDPOINT: Azure AI Search endpoint
    - AZURE_SEARCH_INDEX_NAME: AI Search index name
    - AZURE_AI_SEARCH_CONNECTION_NAME: AI Search connection name in AI Foundry
"""

import os
import sys
import json
import argparse
import logging

parser = argparse.ArgumentParser(description="Create AI Foundry Agent for Knowledge Mining")
parser.add_argument("--agent-name", type=str, default="ChatAgent",
                    help="Name for the chat agent (default: ChatAgent)")
parser.add_argument("--index-name", type=str,
                    help="Azure AI Search index name (overrides env)")
parser.add_argument("--connection-name", type=str,
                    help="Azure AI Search connection name (overrides env)")
parser.add_argument("--scenario", type=str,
                    help="Scenario key from scenarios.json (selects the agent prompt)")
parser.add_argument("--data-source-type", type=str, choices=["azure_search", "fabric"],
                    help="Data source type for BYOD scenarios (azure_search or fabric)")
parser.add_argument("--data-source-name", type=str,
                    help="Display name for the data source (used in agent instructions)")
parser.add_argument("--data-source-table", type=str,
                    help="Table name in the Fabric source (included in agent prompt)")
args = parser.parse_args()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

# Quiet the noisy Azure SDK / HTTP request logs
for _noisy in (
    "azure",
    "azure.core.pipeline.policies.http_logging_policy",
    "azure.identity",
    "httpx",
    "httpcore",
    "urllib3",
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
config_dir = os.path.join(project_root, "data", "config")
env_path = os.path.join(project_root, ".env")

if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
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
MODEL = os.getenv("AZURE_AI_AGENT_MODEL") or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5.2")

# Determine data source type
DATA_SOURCE_TYPE = args.data_source_type or "azure_search"  # Default to Azure Search when unspecified
DATA_SOURCE_NAME = args.data_source_name or "Knowledge Base"
DATA_SOURCE_TABLE = getattr(args, "data_source_table", None) or ""

# Search configuration (for Azure Search BYOD)
SEARCH_CONNECTION_NAME = args.connection_name or os.getenv("AZURE_AI_SEARCH_CONNECTION_NAME")
INDEX_NAME = args.index_name or os.getenv("AZURE_SEARCH_INDEX_NAME", "knowledge-mining-index")
if DATA_SOURCE_TYPE != "azure_search":
    SEARCH_CONNECTION_NAME = ""
    INDEX_NAME = ""

# Agent names ΓÇö from env, else default to <Name>-<solution suffix>.
SOLUTION_SUFFIX = os.getenv("SOLUTION_SUFFIX", "")
CHAT_AGENT_NAME = os.getenv("AGENT_NAME_CHAT") or (f"ChatAgent-{SOLUTION_SUFFIX}" if SOLUTION_SUFFIX else "ChatAgent")
TITLE_AGENT_NAME = os.getenv("AGENT_NAME_TITLE") or (f"SummaryAgent-{SOLUTION_SUFFIX}" if SOLUTION_SUFFIX else "SummaryAgent")

# Validation
if not ENDPOINT:
    logger.error("AZURE_AI_AGENT_ENDPOINT not set. Set it in your .env file or as an environment variable")
    sys.exit(1)

# For Azure Search BYOD, require search connection
if DATA_SOURCE_TYPE == "azure_search" and not SEARCH_CONNECTION_NAME:
    logger.error("AZURE_AI_SEARCH_CONNECTION_NAME not set. Set it in your .env file or pass --connection-name")
    sys.exit(1)

# ============================================================================
# Build Agent Instructions
# ============================================================================

def build_agent_instructions():
    """Load scenario-tailored instructions from agent_prompt.txt.

    All scenarios (seeded, BYOD Azure AI Search, and BYOD Fabric) generate their
    instructions via generate_agent_prompt.py. BYOD scenarios pass the data source
    type/name so Fabric gets a Fabric-specific prompt.
    """
    # Check if this is a BYOD scenario
    _is_byod = False
    _scenarios_path = os.path.join(config_dir, "scenarios.json")
    if os.path.exists(_scenarios_path):
        with open(_scenarios_path, encoding="utf-8") as _f:
            _all_scenarios = json.load(_f).get("scenarios", {})
            if args.scenario in _all_scenarios:
                _is_byod = _all_scenarios[args.scenario].get("byod", False)

    # Seeded scenarios, BYOD Azure AI Search, and BYOD Fabric all use the generated
    # scenario prompt. Fabric BYOD gets a Fabric-specific prompt (Fabric + SQL) driven
    # by the data source args passed through to generate_agent_prompt.py.
    prompt_path = os.path.join(config_dir, "agent_prompt.txt")
    logger.info("Generating scenario prompt")
    import subprocess
    cmd = [sys.executable, os.path.join(script_dir, "generate_agent_prompt.py")]
    if args.scenario:
        cmd += ["--scenario", args.scenario]
    if _is_byod:
        cmd += ["--data-source-type", DATA_SOURCE_TYPE,
                "--data-source-name", DATA_SOURCE_NAME]
        if DATA_SOURCE_TABLE:
            cmd += ["--data-source-table", DATA_SOURCE_TABLE]
    subprocess.run(cmd, check=False)
    if os.path.exists(prompt_path):
        with open(prompt_path, encoding="utf-8") as f:
            return f.read()
    return ("You are a knowledge mining assistant. Use Azure AI Search to ground every "
            "answer in the knowledge base. If no documents match, say so.")


instructions = build_agent_instructions()
logger.info(f"Built instructions ({len(instructions)} chars)")

# Determine scenario tool capabilities. Seeded/BYOD azure_search -> AI Search + SQL;
# BYOD fabric -> SQL only. An explicit `sql_enabled` flag wins.
USE_SQL = False
_scenario_key = args.scenario or os.getenv("SCENARIO") or os.getenv("AZURE_SCENARIO") or ""
_scenarios_path = os.path.join(config_dir, "scenarios.json")
_is_byod = False
if os.path.exists(_scenarios_path):
    with open(_scenarios_path, encoding="utf-8") as _f:
        _all_scenarios = json.load(_f).get("scenarios", {})

    # If no explicit scenario was provided, fall back to the first non-BYOD configured scenario.
    if not _scenario_key and _all_scenarios:
        for key in _all_scenarios.keys():
            if not _all_scenarios[key].get("byod"):
                _scenario_key = key
                break

    _sc = _all_scenarios.get(_scenario_key, {})
    _is_byod = _sc.get("byod", False)
    
    if "sql_enabled" in _sc:
        USE_SQL = bool(_sc["sql_enabled"])
    else:
        USE_SQL = True

# Title Agent Instructions
title_agent_instructions = """You are a specialized agent for generating concise conversation titles.
Create 4-word or less titles that capture the main topic or question.
Focus on key nouns and actions (e.g., 'Top Support Issues', 'Product FAQ Summary').
Never use quotation marks or punctuation.
Be descriptive but concise.
Respond only with the title, no additional commentary."""

# ============================================================================
# Build Tools (Unified for Seeded and BYOD Scenarios)
# ============================================================================

def build_tools():
    """Build and validate tools with clear error reporting.
    
    Raises:
        RuntimeError: If no critical tools can be built or prerequisites are missing.
    """
    tools = []
    warnings = []
    
    # Validate prerequisites based on data source type
    if DATA_SOURCE_TYPE == "fabric":
        if not DATA_SOURCE_NAME:
            raise RuntimeError("Fabric data source name not configured. Use --data-source-name or set in environment.")
        logger.info(f"Building tools for Fabric scenario: {DATA_SOURCE_NAME}")
    elif DATA_SOURCE_TYPE == "azure_search":
        if not SEARCH_CONNECTION_NAME:
            raise RuntimeError("Azure Search connection not configured. Set AZURE_AI_SEARCH_CONNECTION_NAME or use --connection-name.")
        if not INDEX_NAME:
            raise RuntimeError("Azure Search index name not configured. Set AZURE_SEARCH_INDEX_NAME or use --index-name.")
        logger.info(f"Building tools for Azure Search scenario: {INDEX_NAME}")
    
    # Fabric uses a Fabric query tool + SQL tools; Azure Search uses AI Search + SQL.
    if DATA_SOURCE_TYPE == "fabric":
        try:
            from azure.ai.projects.models import FunctionTool
            tools.append(FunctionTool(
                name="query_fabric_data",
                description=(
                    f"Query the {DATA_SOURCE_NAME} Fabric warehouse/lakehouse for live source records "
                    "using natural language."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query to run against the Fabric data.",
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                strict=False,
            ))
            logger.info(f"Added Fabric tool: query_fabric_data ({DATA_SOURCE_NAME})")
        except ImportError as e:
            raise RuntimeError(f"Failed to import Fabric tool dependencies: {e}")
    elif DATA_SOURCE_TYPE == "azure_search":
        # For Azure Search (seeded or BYOD)
        try:
            search_tool = AzureAISearchTool(
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
            tools.append(search_tool)
            logger.info(f"Added Azure AI Search tool: {INDEX_NAME}")
        except Exception as e:
            raise RuntimeError(f"Failed to build Azure Search tool: {type(e).__name__}: {e}")
    
    # Add SQL tools only for seeded scenarios (not BYOD)
    if USE_SQL:
        try:
            from azure.ai.projects.models import FunctionTool
            tools.append(FunctionTool(
                name="get_schema_and_sample_values",
                description=(
                    "Discover the exact metadata field names and sample values stored in the "
                    "documents table. Call this BEFORE writing SQL queries with metadata filters, "
                    "especially when a previous query returned zero rows or you are unsure of "
                    "exact field names or value casing."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "top_n": {
                            "type": "integer",
                            "description": "Number of distinct sample values to return per field (default: 5).",
                        }
                    },
                    "required": [],
                    "additionalProperties": False,
                },
                strict=False,
            ))
            tools.append(FunctionTool(
                name="get_sql_response",
                description=(
                    "Execute T-SQL on the documents table. "
                    "All metadata is stored as JSON ΓÇö use JSON_VALUE(metadata, '$.field') for filtering. "
                    "All values are strings; match exactly. "
                    "Call get_schema_and_sample_values first to verify exact field values if a query returns zero rows."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "A valid T-SQL query against the documents table.",
                        }
                    },
                    "required": ["sql_query"],
                    "additionalProperties": False,
                },
                strict=True,
            ))
            logger.info("Added SQL tools: get_schema_and_sample_values, get_sql_response")
        except ImportError as e:
            warnings.append(f"SQL tools unavailable (FunctionTool import failed): {e}")
            logger.warning(f"SQL tools skipped: {e}")
    elif tools:
        logger.info("Search-only scenario ΓÇö SQL tools not needed")
    
    # Fail loudly if no tools were built
    if not tools:
        error_msg = "No tools available. Critical configuration missing."
        if warnings:
            error_msg += f" Warnings: {'; '.join(warnings)}"
        raise RuntimeError(error_msg)
    
    logger.info(f"Tool validation passed. Built {len(tools)} tool(s).")
    
    return tools


# Build and validate tools with proper error handling
try:
    agent_tools = build_tools()
except RuntimeError as e:
    logger.error(f"Failed to build tools: {e}")
    sys.exit(1)

# ============================================================================
# Print Configuration
# ============================================================================

logger.info("="*60)
logger.info("Creating Knowledge Mining Agent")
logger.info("="*60)
logger.info(f"Endpoint: {ENDPOINT}")
logger.info(f"Model: {MODEL}")
logger.info(f"Agent Name: {CHAT_AGENT_NAME}")
logger.info(f"Data Source Type: {DATA_SOURCE_TYPE}")
logger.info(f"Data Source Name: {DATA_SOURCE_NAME}")
if DATA_SOURCE_TYPE == "azure_search":
    logger.info(f"Search Index: {INDEX_NAME}")
    logger.info(f"Search Connection: {SEARCH_CONNECTION_NAME}")

# ============================================================================
# Create the Agent
# ============================================================================

logger.info("Initializing AI Project Client...")
credential = DefaultAzureCredential()

try:
    project_client = AIProjectClient(
        endpoint=ENDPOINT,
        credential=credential,
    )
    logger.info("AI Project Client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize client: {type(e).__name__}: {e}")
    sys.exit(1)


def create_agents(project_client, instructions, title_instructions, agent_tools):
    """Create ChatAgent and TitleAgent in AI Foundry."""
    with project_client:
        # Delete existing agent if it exists
        logger.info(f"Checking if agent '{CHAT_AGENT_NAME}' already exists...")
        try:
            existing_agent = project_client.agents.get(CHAT_AGENT_NAME)
            if existing_agent:
                logger.info("Found existing agent, deleting...")
                project_client.agents.delete(CHAT_AGENT_NAME)
                logger.info("Deleted existing agent")
        except Exception:
            logger.info("No existing agent found")

        # Create chat agent
        logger.info(f"Creating chat agent '{CHAT_AGENT_NAME}' with {len(agent_tools)} tool(s)...")
        agent_definition = PromptAgentDefinition(
            model=MODEL,
            instructions=instructions,
            tools=agent_tools,
        )

        chat_agent = project_client.agents.create_version(
            agent_name=CHAT_AGENT_NAME,
            definition=agent_definition,
        )

        logger.info(f"Chat agent created successfully: {CHAT_AGENT_NAME}")

        # Print tool info
        if hasattr(chat_agent, "definition") and chat_agent.definition and hasattr(chat_agent.definition, "tools"):
            logger.info(f"Tools registered on agent ({len(chat_agent.definition.tools)} total):")
            for i, tool in enumerate(chat_agent.definition.tools, 1):
                tool_type = type(tool).__name__
                if hasattr(tool, "azure_ai_search"):
                    indexes = tool.azure_ai_search.indexes if hasattr(tool.azure_ai_search, "indexes") else []
                    idx_names = [getattr(idx, "index_name", None) or getattr(idx, "name", "unknown") for idx in indexes]
                    logger.info(f"  {i}. [{tool_type}] indexes: {', '.join(idx_names)}")
                elif hasattr(tool, "name"):
                    logger.info(f"  {i}. [{tool.name}] {tool_type}")
                else:
                    logger.info(f"  {i}. [{tool_type}]")
        else:
            logger.info(f"Tools configured: {len(agent_tools)}")

        # Delete existing title agent if it exists
        logger.info(f"Checking if title agent '{TITLE_AGENT_NAME}' already exists...")
        try:
            existing_title = project_client.agents.get(TITLE_AGENT_NAME)
            if existing_title:
                logger.info("Found existing title agent, deleting...")
                project_client.agents.delete(TITLE_AGENT_NAME)
                logger.info("Deleted existing title agent")
        except Exception:
            logger.info("No existing title agent found")

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
        logger.info(f"Title agent created successfully: {TITLE_AGENT_NAME}")

    return chat_agent, title_agent


try:
    chat_agent, title_agent = create_agents(
        project_client, instructions, title_agent_instructions, agent_tools
    )
except Exception as e:
    logger.error(f"Failed to create agents: {type(e).__name__}: {e}")
    logger.debug("", exc_info=True)
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
    "data_source_type": DATA_SOURCE_TYPE,
    "data_source_name": DATA_SOURCE_NAME,
    "search_index": INDEX_NAME,
    "search_connection": SEARCH_CONNECTION_NAME,
    "model": MODEL,
    "scenario": _scenario_key,
    "use_sql": USE_SQL,
})

with open(agent_ids_path, "w") as f:
    json.dump(agent_ids, f, indent=2)

logger.info(f"Agent config saved to: {agent_ids_path}")

# Persist agent names so the API and test scripts can find them.
def set_azd_env(key, value):
    """Set a key in the azd environment."""
    import subprocess
    subprocess.run(["azd", "env", "set", key, value], check=False,
                   capture_output=True)
    os.environ[key] = value

set_azd_env("AGENT_NAME_CHAT", CHAT_AGENT_NAME)
set_azd_env("AGENT_NAME_TITLE", TITLE_AGENT_NAME)
set_azd_env("USE_SQL", str(USE_SQL))
set_azd_env("DATA_SOURCE_TYPE", DATA_SOURCE_TYPE)
logger.info(f"azd env set: AGENT_NAME_CHAT={CHAT_AGENT_NAME}, AGENT_NAME_TITLE={TITLE_AGENT_NAME}, USE_SQL={USE_SQL}, DATA_SOURCE_TYPE={DATA_SOURCE_TYPE}")

# Write the agent values back into .env so the local backend picks them up
# without needing azd. Existing keys are updated in-place; missing keys are appended.
_ENV_KEYS_TO_WRITE = {
    "AGENT_NAME_CHAT": CHAT_AGENT_NAME,
    "AGENT_NAME_TITLE": TITLE_AGENT_NAME,
    "USE_SQL": str(USE_SQL).lower(),
    "DATA_SOURCE_TYPE": DATA_SOURCE_TYPE,
}
if os.path.exists(env_path):
    try:
        with open(env_path, encoding="utf-8") as _ef:
            _env_lines = _ef.readlines()
        _written_keys = set()
        _new_lines = []
        for _line in _env_lines:
            _stripped = _line.strip()
            if _stripped and not _stripped.startswith("#") and "=" in _stripped:
                _k = _stripped.split("=", 1)[0].strip()
                if _k in _ENV_KEYS_TO_WRITE:
                    _new_lines.append(f'{_k}={_ENV_KEYS_TO_WRITE[_k]}\n')
                    _written_keys.add(_k)
                    continue
            _new_lines.append(_line)
        # Append any keys not already present
        for _k, _v in _ENV_KEYS_TO_WRITE.items():
            if _k not in _written_keys:
                _new_lines.append(f'{_k}={_v}\n')
        with open(env_path, "w", encoding="utf-8") as _ef:
            _ef.writelines(_new_lines)
        logger.info(f".env updated: AGENT_NAME_CHAT={CHAT_AGENT_NAME}, AGENT_NAME_TITLE={TITLE_AGENT_NAME}, USE_SQL={USE_SQL}")
    except Exception as _env_err:
        logger.warning(f"Could not update .env automatically: {_env_err}")
else:
    logger.info(".env file not found ΓÇö skipping local .env update")

# The API App Service settings (AGENT_NAME_CHAT / AGENT_NAME_TITLE / USE_SQL) are
# updated by the calling PowerShell script (setup-agent.ps1) using `az webapp
# config appsettings set`, so the running app picks up the freshly created agents.



# ============================================================================
# Summary
# ============================================================================

# ============================================================================
# Summary
# ============================================================================

logger.info("="*60)
logger.info("Knowledge Mining Agents Created Successfully!")
logger.info("="*60)
logger.info(f"Chat Agent: {CHAT_AGENT_NAME}")
logger.info(f"  Model: {MODEL}")
logger.info(f"  Tools: {', '.join([(getattr(t, 'name', None) or type(t).__name__) for t in agent_tools]) if agent_tools else 'None'}")
logger.info(f"Title Agent: {TITLE_AGENT_NAME}")
logger.info(f"  Model: {MODEL}")
logger.info(f"  Tools: None (text generation only)")
