"""
test_agent.py - Test Azure AI Foundry Agent for Knowledge Mining Platform

Interactive chat loop that sends messages to the Knowledge Mining agent and
streams responses. The agent uses Azure AI Search to retrieve relevant documents
and answers questions grounded in the knowledge base.

Usage:
    python infra/scripts/test_agent.py                # Default agent
    python infra/scripts/test_agent.py -v             # Verbose mode
    python infra/scripts/test_agent.py --agent-name MyAgent

Prerequisites:
    - Run infra/scripts/create_agent.py first
    - .env file configured with AZURE_AI_AGENT_ENDPOINT
"""

import os
import sys
import json
import re
import argparse
import traceback

# Parse arguments
parser = argparse.ArgumentParser(description="Test Knowledge Mining Agent")
parser.add_argument("--agent-name", type=str, help="Agent name to test")
parser.add_argument("-v", "--verbose", action="store_true",
                    help="Show detailed search calls and results")
args = parser.parse_args()

VERBOSE = args.verbose

# Load .env
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
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

# ============================================================================
# Configuration
# ============================================================================

ENDPOINT = os.getenv("AZURE_AI_AGENT_ENDPOINT")

if not ENDPOINT:
    print("ERROR: AZURE_AI_AGENT_ENDPOINT not set")
    sys.exit(1)

# Load agent config
data_dir = os.path.join(project_root, "data")
config_dir = os.path.join(data_dir, "config")
if not os.path.exists(config_dir):
    config_dir = data_dir

agent_ids_path = os.path.join(config_dir, "agent_ids.json")
if not os.path.exists(agent_ids_path):
    print("ERROR: agent_ids.json not found")
    print("       Run infra/scripts/create_agent.py first")
    sys.exit(1)

with open(agent_ids_path) as f:
    agent_ids = json.load(f)

# Get agent name
CHAT_AGENT_NAME = args.agent_name or agent_ids.get("chat_agent_name")
if not CHAT_AGENT_NAME:
    print("ERROR: No agent name found")
    print("       Run infra/scripts/create_agent.py first or provide --agent-name")
    sys.exit(1)

# ============================================================================
# Print Configuration
# ============================================================================

print(f"\n{'='*60}")
print(f"Knowledge Mining Agent Chat")
print(f"{'='*60}")
print(f"Agent: {CHAT_AGENT_NAME}")
print(f"Search Index: {agent_ids.get('search_index', 'N/A')}")
print(f"Model: {agent_ids.get('model', 'N/A')}")
print(f"Type 'quit' to exit, 'help' for sample questions\n")

# ============================================================================
# Sample Questions
# ============================================================================

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
    print("\n  The agent searches documents using Azure AI Search")
    print("  Type a number (1-6) to use a sample question")
    print()


# ============================================================================
# Initialize Client
# ============================================================================

credential = DefaultAzureCredential()
project_client = AIProjectClient(endpoint=ENDPOINT, credential=credential)

# Verify agent exists
try:
    agent_details = project_client.agents.get(CHAT_AGENT_NAME)
    print(f"[OK] Agent '{CHAT_AGENT_NAME}' found")
except Exception as e:
    print(f"[FAIL] Agent '{CHAT_AGENT_NAME}' not found: {e}")
    print("       Run infra/scripts/create_agent.py first")
    sys.exit(1)

# Get OpenAI client for conversations
openai_client = project_client.get_openai_client()

# Load agent definition (instructions + tools)
agent_def = dict(agent_details)
agent_version = agent_def.get("versions", {}).get("latest", {})
agent_defn = agent_version.get("definition", {})
AGENT_INSTRUCTIONS = agent_defn.get("instructions", "")
AGENT_MODEL = agent_defn.get("model", "gpt-4o")

# Build search tool config from agent definition — convert to plain dicts
AGENT_TOOLS = []
for tool in agent_defn.get("tools", []):
    if tool.get("type") == "azure_ai_search":
        # Convert to plain dict recursively
        def to_dict(obj):
            if isinstance(obj, dict):
                return {k: to_dict(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [to_dict(v) for v in obj]
            if hasattr(obj, "as_dict"):
                return obj.as_dict()
            if hasattr(obj, "__dict__"):
                return {k: to_dict(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
            return obj
        AGENT_TOOLS.append(to_dict(tool))

if VERBOSE:
    print(f"[Config] Model: {AGENT_MODEL}")
    print(f"[Config] Tools: {len(AGENT_TOOLS)}")
    print(f"[Config] Instructions: {len(AGENT_INSTRUCTIONS)} chars")

# ============================================================================
# Chat Function
# ============================================================================

def chat(user_message: str, prev_response_id: str | None) -> str | None:
    """Send a message using the agent's model, instructions, and search tools."""
    try:
        if VERBOSE:
            print(f"\n[Agent] Sending to '{AGENT_MODEL}' with agent tools...")

        kwargs = {
            "model": AGENT_MODEL,
            "instructions": AGENT_INSTRUCTIONS,
            "input": user_message,
            "tools": AGENT_TOOLS,
        }
        if prev_response_id:
            kwargs["previous_response_id"] = prev_response_id

        response = openai_client.responses.create(**kwargs)

        # Extract text from response
        text_output = ""
        for item in response.output:
            if hasattr(item, "content") and item.content:
                for content in item.content:
                    if hasattr(content, "text"):
                        text = content.text
                        # Remove citation markers like 【4:0†source】
                        text = re.sub(r'【\d+:\d+†[^】]+】', '', text)
                        text_output += text
            elif VERBOSE and hasattr(item, "type"):
                print(f"  [Tool call: {item.type}]")

        if text_output:
            print(f"\nAssistant: {text_output}")
        else:
            print("\nAssistant: (no response)")

        return response.id

    except Exception as e:
        print(f"\nError: {e}")
        if VERBOSE:
            traceback.print_exc()
        return prev_response_id


# ============================================================================
# Main Chat Loop
# ============================================================================

def main():
    prev_id: str | None = None
    print("-" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            if user_input.lower() == "help":
                show_help()
                continue

            # Numbered question shortcuts
            if user_input.isdigit():
                idx = int(user_input) - 1
                if 0 <= idx < len(sample_questions):
                    user_input = sample_questions[idx]
                    print(f"  → {user_input}")

            prev_id = chat(user_input, prev_id)

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\nGoodbye!")
            break


main()
