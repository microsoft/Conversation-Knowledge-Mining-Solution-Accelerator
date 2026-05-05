"""Seed a different use case (insurance claims) to test generic insights.

Usage:
  python scripts/test-usecase.py              # seeds insurance claims
  python scripts/test-usecase.py --clear      # clears and restores call transcripts
"""

import argparse
import json
import os
import struct
import sys
import random
from datetime import datetime, timedelta

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
env_path = os.path.join(project_root, ".env")

if os.path.exists(env_path):
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().split("#")[0].strip())

SQL_SERVER = os.getenv("AZURE_SQL_SERVER", "")
SQL_DATABASE = os.getenv("AZURE_SQL_DATABASE", "km-db")

CLAIM_TYPES = ["Auto", "Property", "Health", "Life", "Travel"]
STATUSES = ["Approved", "Denied", "Pending"]
REGIONS = ["Northeast", "Southeast", "Midwest", "West", "Southwest"]
AGENTS = ["Agent A", "Agent B", "Agent C", "Agent D", "Agent E"]
PRIORITIES = ["High", "Medium", "Low"]


def generate_claims(n=200):
    """Generate synthetic insurance claim records."""
    docs = []
    base_date = datetime(2025, 11, 1)
    for i in range(n):
        claim_type = random.choice(CLAIM_TYPES)
        # Bias: Travel claims get denied more
        if claim_type == "Travel":
            status = random.choices(STATUSES, weights=[40, 45, 15])[0]
        elif claim_type == "Auto":
            status = random.choices(STATUSES, weights=[70, 20, 10])[0]
        else:
            status = random.choices(STATUSES, weights=[65, 25, 10])[0]

        filed = base_date + timedelta(days=random.randint(0, 60))
        resolved = filed + timedelta(days=random.randint(2, 30))
        amount = random.randint(500, 50000)
        region = random.choice(REGIONS)
        agent = random.choice(AGENTS)
        priority = random.choice(PRIORITIES)

        kp = random.sample([
            "water damage", "collision", "theft", "fire damage",
            "medical expense", "liability", "deductible",
            "coverage limit", "pre-existing condition", "delayed flight",
            "lost luggage", "property assessment", "claim investigation",
            "policy renewal", "premium adjustment",
        ], k=random.randint(2, 5))

        docs.append({
            "id": f"claim-{i:04d}",
            "doc_type": "insurance_claim",
            "text_content": f"Insurance claim #{i} for {claim_type} filed by customer in {region}. "
                            f"Amount: ${amount}. Status: {status}. Priority: {priority}.",
            "summary": f"{claim_type} claim for ${amount} - {status}",
            "key_phrases": json.dumps(kp),
            "topics": json.dumps([claim_type]),
            "metadata": json.dumps({
                "claim_type": claim_type,
                "status": status,
                "region": region,
                "agent": agent,
                "priority": priority,
                "amount": str(amount),
                "filed_date": filed.strftime("%Y-%m-%d %H:%M:%S"),
                "resolved_date": resolved.strftime("%Y-%m-%d %H:%M:%S"),
            }),
        })
    return docs


def get_conn():
    import pyodbc
    from azure.identity import DefaultAzureCredential
    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={SQL_SERVER};Database={SQL_DATABASE};"
        f"Encrypt=yes;TrustServerCertificate=no;"
    )
    return pyodbc.connect(conn_str, attrs_before={1256: token_struct})


def seed_claims():
    docs = generate_claims(200)
    conn = get_conn()
    cursor = conn.cursor()

    # Clear existing data
    cursor.execute("DELETE FROM documents")
    cursor.execute("DELETE FROM uploaded_files")
    # Clear insights cache so LLM re-plans
    try:
        cursor.execute("DELETE FROM insights_cache")
    except Exception:
        pass
    conn.commit()

    # Insert claims
    for doc in docs:
        cursor.execute("""
            INSERT INTO documents (id, doc_type, text_content, summary, key_phrases, topics, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, doc["id"], doc["doc_type"], doc["text_content"], doc["summary"],
            doc["key_phrases"], doc["topics"], doc["metadata"])

    # Register file
    cursor.execute("""
        MERGE uploaded_files AS target
        USING (SELECT 'test-insurance-claims' AS id) AS source ON target.id = source.id
        WHEN MATCHED THEN UPDATE SET filename=?, doc_count=?, summary=?, keywords=?, filter_values=?, uploaded_at=?
        WHEN NOT MATCHED THEN INSERT (id, filename, doc_count, summary, keywords, filter_values, uploaded_at)
            VALUES ('test-insurance-claims', ?, ?, ?, ?, ?, ?);
    """,
        "insurance_claims.json", len(docs), f"{len(docs)} insurance claims",
        json.dumps(["insurance", "claims"]), json.dumps({}), "2025-11-01T00:00:00Z",
        "insurance_claims.json", len(docs), f"{len(docs)} insurance claims",
        json.dumps(["insurance", "claims"]), json.dumps({}), "2025-11-01T00:00:00Z",
    )

    conn.commit()
    conn.close()
    print(f"[OK] Seeded {len(docs)} insurance claims")
    print(f"     Restart the backend, then open Insights and click Re-analyze")


def clear_and_restore():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE id LIKE 'claim-%'")
    cursor.execute("DELETE FROM uploaded_files WHERE id = 'test-insurance-claims'")
    try:
        cursor.execute("DELETE FROM insights_cache")
    except Exception:
        pass
    conn.commit()
    conn.close()
    print("[OK] Cleared test claims. Run seed-sample-data.ps1 to restore call transcripts.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Clear test data and restore")
    args = parser.parse_args()

    if not SQL_SERVER:
        print("ERROR: AZURE_SQL_SERVER not set")
        sys.exit(1)

    if args.clear:
        clear_and_restore()
    else:
        seed_claims()


if __name__ == "__main__":
    main()
