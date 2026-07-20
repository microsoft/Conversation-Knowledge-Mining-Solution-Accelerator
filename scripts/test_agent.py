"""
test_agent.py - Test the Foundry agent using the Agent Framework

Interactive chat loop that connects to the deployed Knowledge Mining agent with
agent_framework.foundry.FoundryAgent and streams responses. The agent already
exists in Foundry (created by create_agent.py) and is bound here by name.

Usage:
    python scripts/test_agent.py                # Default agent
    python scripts/test_agent.py -v             # Verbose mode
    python scripts/test_agent.py --agent-name MyAgent

Prerequisites:
    - Run scripts/create_agent.py first
    - .env file configured with AZURE_AI_AGENT_ENDPOINT and AGENT_NAME_CHAT
"""

import argparse
import asyncio
import json
import os
import re
import sys
import traceback

# Parse arguments
parser = argparse.ArgumentParser(description="Test Knowledge Mining Agent")
parser.add_argument("--agent-name", type=str, help="Agent name to test")
parser.add_argument("-v", "--verbose", action="store_true",
                    help="Show detailed tool calls and config")
args = parser.parse_args()

VERBOSE = args.verbose

# Load .env
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

from azure.identity.aio import DefaultAzureCredential
from azure.ai.projects.aio import AIProjectClient
from agent_framework.foundry import FoundryAgent
from agent_framework_openai._chat_client import RawOpenAIChatClient

# ============================================================================
# Configuration
# ============================================================================

ENDPOINT = os.getenv("AZURE_AI_AGENT_ENDPOINT")
if not ENDPOINT:
    print("ERROR: AZURE_AI_AGENT_ENDPOINT not set")
    sys.exit(1)

# Agent name: CLI arg > env > agent_ids.json
config_dir = os.path.join(project_root, "data", "config")
agent_ids = {}
agent_ids_path = os.path.join(config_dir, "agent_ids.json")
if os.path.exists(agent_ids_path):
    with open(agent_ids_path) as f:
        agent_ids = json.load(f)

CHAT_AGENT_NAME = (
    args.agent_name
    or os.getenv("AGENT_NAME_CHAT")
    or agent_ids.get("chat_agent_name")
)
if not CHAT_AGENT_NAME:
    print("ERROR: No agent name found. Run scripts/create_agent.py first or pass --agent-name")
    sys.exit(1)

# SQL is a client-side function tool: the agent only has a get_sql_response
# declaration, so SQL-enabled scenarios must supply the callable at runtime
# (same pattern as src/api/services/chat_service.py).
USE_SQL = bool(agent_ids.get("use_sql", False))
DATA_SOURCE_TYPE = agent_ids.get("data_source_type", "azure_search")

print(f"\n{'='*60}")
print("Knowledge Mining Agent Chat (Agent Framework)")
print(f"{'='*60}")
print(f"Agent: {CHAT_AGENT_NAME}")
print(f"Search Index: {agent_ids.get('search_index', 'N/A')}")
print(f"Model: {agent_ids.get('model', 'N/A')}")
if DATA_SOURCE_TYPE == "fabric":
    print(f"Tools: Fabric + SQL")
else:
    print(f"Tools: Search{' + SQL' if USE_SQL else ' only'}")
print("Type 'quit' to exit, 'help' for sample questions\n")

sample_questions = [
    "What are the top customer support issues?",
    "Summarize the key themes across all documents",
    "Which products are mentioned most frequently?",
    "What are common billing-related problems?",
    "How are connectivity issues typically resolved?",
    "What FAQs exist for the ZX-3000?",
]


def show_help():
    print("\nSample questions to try:")
    for i, q in enumerate(sample_questions, 1):
        print(f"  {i}. {q}")
    print("\n  Type a number (1-6) to use a sample question\n")


def clean(text: str) -> str:
    """Strip citation markers like the source markers for readable console output."""
    return re.sub(r"【\d+:\d+†[^】]+】", "", text)


def collect_citations(response, get_urls: list) -> list:
    """Build a citation list from the final response, enriching doc_N citations
    with the per-document get_urls extracted from the raw Azure AI Search stream.
    """
    citations = []
    seen = set()
    url_iter = iter(get_urls)
    for message in getattr(response, "messages", None) or []:
        for content in getattr(message, "contents", None) or []:
            for ann in getattr(content, "annotations", None) or []:
                if not isinstance(ann, dict) or ann.get("type") != "citation":
                    continue
                title = ann.get("title", "N/A")
                add_props = ann.get("additional_properties") or {}
                url = add_props.get("get_url") or ann.get("url")
                # GA regression: doc_N citations only carry the root search URL,
                # so fall back to the next per-document get_url from the raw stream.
                if isinstance(title, str) and title.startswith("doc_"):
                    url = add_props.get("get_url") or next(url_iter, url)
                key = (title, url)
                if key in seen:
                    continue
                seen.add(key)
                citations.append({"title": title, "url": url or "N/A"})
    return citations


def extract_get_urls(response) -> list:
    """Extract per-document get_urls from the raw Azure AI Search stream events."""
    get_urls = []
    for raw_agent_update in getattr(response, "raw_representation", None) or []:
        raw_chat_update = getattr(raw_agent_update, "raw_representation", raw_agent_update)
        event = getattr(raw_chat_update, "raw_representation", raw_chat_update)
        for url in RawOpenAIChatClient._extract_azure_ai_search_get_urls(event):
            if url not in get_urls:
                get_urls.append(url)
    return get_urls


def print_citations(citations: list) -> None:
    if not citations:
        return
    print("\n  Citations:")
    for i, c in enumerate(citations, 1):
        print(f"    [{i}] {c['title']} — {c['url']}")


from src.api.modules.rag.agent_tools import (
    get_sql_response,
    get_schema_and_sample_values,
    query_fabric_data,
)


async def main():
    credential = DefaultAzureCredential()
    project_client = AIProjectClient(endpoint=ENDPOINT, credential=credential)

    async with credential, project_client:
        if DATA_SOURCE_TYPE == "fabric":
            tools = [query_fabric_data, get_schema_and_sample_values, get_sql_response]
        elif USE_SQL:
            tools = [get_schema_and_sample_values, get_sql_response]
        else:
            tools = None
        async with FoundryAgent(
            project_client=project_client,
            agent_name=CHAT_AGENT_NAME,
            tools=tools,
        ) as agent:
            if VERBOSE:
                print(f"[OK] Connected to agent '{CHAT_AGENT_NAME}'")
                print(f"[OK] SQL tool {'enabled' if USE_SQL else 'disabled'} for this scenario")

            openai_client = project_client.get_openai_client()
            conversation = await openai_client.conversations.create()
            conversation_id = conversation.id
            print(f"[OK] Created conversation {conversation_id}")
            print("-" * 60)

            while True:
                try:
                    user_input = input("\nYou: ").strip()
                    if not user_input:
                        continue
                    if user_input.lower() in ("quit", "exit", "q"):
                        print("Goodbye!")
                        break
                    if user_input.lower() == "help":
                        show_help()
                        continue
                    if user_input.isdigit():
                        idx = int(user_input) - 1
                        if 0 <= idx < len(sample_questions):
                            user_input = sample_questions[idx]
                            print(f"  -> {user_input}")

                    print("\nAssistant: ", end="", flush=True)
                    stream = agent.run(
                        user_input,
                        stream=True,
                        options={"conversation_id": conversation_id},
                    )
                    async for update in stream:
                        if update.text:
                            print(update.text, end="", flush=True)
                    print()

                    response = await stream.get_final_response()
                    get_urls = extract_get_urls(response)
                    citations = collect_citations(response, get_urls)
                    print_citations(citations)
                except KeyboardInterrupt:
                    print("\n\nGoodbye!")
                    break
                except EOFError:
                    print("\nGoodbye!")
                    break
                except Exception as e:
                    print(f"\nError: {e}")
                    if VERBOSE:
                        traceback.print_exc()

            try:
                await openai_client.conversations.delete(conversation_id=conversation_id)
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())
