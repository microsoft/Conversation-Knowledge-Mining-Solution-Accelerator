import json
from datetime import datetime

dataset = [
  {
    "id": "report_001",
    "type": "incident_report",
    "text": """
Incident Report: ZX-3000 Connectivity Issue

Summary:
Multiple users reported intermittent internet disconnections over a 48-hour period.

Root Cause:
Outdated firmware (v1.0) caused instability under high traffic conditions.

Impact:
Approximately 120 users affected across multiple regions.

Resolution:
Firmware patch v1.1 deployed. Users instructed to update via admin panel.

Recommendation:
Enable auto-update for firmware to prevent recurrence.
""",
    "metadata": {
      "product": "ZX-3000",
      "category": "firmware",
      "timestamp": datetime.now().strftime("%Y-%m-%d")
    }
  },
  {
    "id": "report_002",
    "type": "incident_report",
    "text": """
Incident Report: Router-Y Network Congestion

Summary:
Users experienced slow speeds during peak evening hours.

Root Cause:
Network congestion due to high bandwidth usage.

Impact:
Reduced speeds for ~200 users.

Resolution:
Traffic balancing applied and bandwidth limits adjusted.

Recommendation:
Upgrade infrastructure in high-density areas.
""",
    "metadata": {
      "product": "Router-Y",
      "category": "connectivity",
      "timestamp": datetime.now().strftime("%Y-%m-%d")
    }
  },
  {
    "id": "notes_001",
    "type": "agent_notes",
    "text": """
Case Notes:

Customer complained about frequent Wi-Fi drops.
Device: ZX-3000

Steps Taken:
- Checked firmware version (v1.0)
- Guided user to update firmware
- Restarted modem

Outcome:
Connection stabilized after update.

Agent Insight:
Issue likely caused by outdated firmware.
""",
    "metadata": {
      "product": "ZX-3000",
      "category": "connectivity",
      "timestamp": datetime.now().strftime("%Y-%m-%d")
    }
  },
  {
    "id": "notes_002",
    "type": "agent_notes",
    "text": """
Case Notes:

Customer unable to connect phone to Wi-Fi.

Steps Taken:
- Verified network visibility
- Reset Wi-Fi credentials
- Reconnected device

Outcome:
Issue resolved.

Agent Insight:
Authentication mismatch caused failure.
""",
    "metadata": {
      "product": "ZX-3000",
      "category": "setup",
      "timestamp": datetime.now().strftime("%Y-%m-%d")
    }
  },
  {
    "id": "guide_001",
    "type": "troubleshooting_guide",
    "text": """
Troubleshooting Guide: Connectivity Issues

Step 1: Restart your modem/router.
Step 2: Check firmware version and update if needed.
Step 3: Change Wi-Fi channel to reduce interference.
Step 4: Reset network settings if issues persist.

Common Causes:
- Outdated firmware
- Signal interference
- Network congestion
""",
    "metadata": {
      "product": "ZX-3000",
      "category": "setup",
      "timestamp": datetime.now().strftime("%Y-%m-%d")
    }
  },
  {
    "id": "guide_002",
    "type": "troubleshooting_guide",
    "text": """
Troubleshooting Guide: Billing Issues

Step 1: Review invoice details.
Step 2: Check for late payment fees.
Step 3: Contact support for clarification.

Common Causes:
- Late payments
- Tax adjustments
- Subscription changes
""",
    "metadata": {
      "product": "ZX-3000",
      "category": "billing",
      "timestamp": datetime.now().strftime("%Y-%m-%d")
    }
  }
]

with open("synthetic_dataset_extra.json", "w") as f:
    json.dump(dataset, f, indent=2)