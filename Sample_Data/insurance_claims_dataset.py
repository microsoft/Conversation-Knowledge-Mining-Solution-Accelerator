import json
import random
from datetime import datetime

products = ["AutoProtect", "HomeShield", "LifeSecure"]
categories = ["claims", "policy", "billing", "support", "fraud"]

def generate_claim(i):
    return {
        "id": f"claim_{i:03d}",
        "type": "insurance_claim",
        "text": f"""
Claim ID: CLM-{1000+i}
Customer reports a {random.choice(['car accident', 'water damage', 'roof leak'])}.
Incident date: 2026-03-{random.randint(10,28)}.
Estimated damage: ${random.randint(1000,15000)}.
Status: {random.choice(['pending', 'approved', 'rejected'])}.
Adjuster notes: {random.choice([
    'Photos confirm damage severity',
    'Customer statement inconsistent',
    'Third-party verification required'
])}.
""",
        "metadata": {
            "product": random.choice(products),
            "category": "claims",
            "timestamp": datetime.now().strftime("%Y-%m-%d")
        }
    }

def generate_call(i):
    return {
        "id": f"call_{i:03d}",
        "type": "audio_transcript",
        "text": [
            {"speaker": "Customer", "start_time": "00:00:01", "end_time": "00:00:05",
             "text": random.choice([
                 "I want to check my claim status",
                 "Why was my claim rejected?",
                 "I need help filing a claim"
             ])},
            {"speaker": "Agent", "start_time": "00:00:06", "end_time": "00:00:12",
             "text": random.choice([
                 "Let me pull up your claim details",
                 "I see your claim was recently processed",
                 "I'll guide you through the filing process"
             ])}
        ],
        "metadata": {
            "product": random.choice(products),
            "category": "support",
            "timestamp": datetime.now().strftime("%Y-%m-%d")
        }
    }

def generate_policy(i):
    return {
        "id": f"policy_{i:03d}",
        "type": "policy_document",
        "text": f"""
Policy Section {i}:
Coverage includes damages caused by {random.choice(['fire', 'flood', 'collision'])}.
Exclusions: {random.choice([
    'Intentional damage is not covered',
    'Wear and tear is excluded',
    'Delayed reporting voids claim eligibility'
])}.
Claims must be filed within {random.choice([7, 14, 30])} days of incident.
""",
        "metadata": {
            "product": random.choice(products),
            "category": "policy",
            "timestamp": datetime.now().strftime("%Y-%m-%d")
        }
    }

def generate_email(i):
    return {
        "id": f"email_{i:03d}",
        "type": "email",
        "text": f"""
Subject: Claim Update

Dear Customer,

Your claim has been {random.choice(['approved', 'rejected', 'escalated'])}.
Reason: {random.choice([
    'Insufficient documentation',
    'Policy coverage confirmed',
    'Further investigation required'
])}.

Regards,
Claims Team
""",
        "metadata": {
            "product": random.choice(products),
            "category": random.choice(categories),
            "timestamp": datetime.now().strftime("%Y-%m-%d")
        }
    }

dataset = []

for i in range(1, 51):
    dataset.append(generate_claim(i))
    dataset.append(generate_call(i))
    dataset.append(generate_policy(i))
    dataset.append(generate_email(i))

with open("insurance_dataset.json", "w") as f:
    json.dump(dataset, f, indent=2)