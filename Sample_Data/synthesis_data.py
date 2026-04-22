import json
import copy
from datetime import datetime

dataset = [
  {
    "id": "chat_001",
    "type": "chat_transcript",
    "text": "User: Hi, my internet keeps disconnecting.\nAgent: Sorry to hear that! Can you tell me your modem model?\nUser: ZX-3000\nAgent: Thanks. Have you tried restarting the modem?\nUser: Yes, still drops.\nAgent: Let's check your firmware version.\nUser: How do I check that?\nAgent: Open 192.168.1.1 and go to Firmware Update.\nUser: Okay, it says update available.\nAgent: Install it and restart your modem.\nUser: Done, connection is stable now.\nAgent: Great! Glad to help.",
    "metadata": {
      "product": "ZX-3000",
      "category": "connectivity",
      "timestamp": "2026-04-09"
    }
  },
  {
    "id": "chat_002",
    "type": "chat_transcript",
    "text": "User: Can I use this modem with fiber internet?\nAgent: ZX-3000 only supports cable internet. Recommend ZX-Fiber.\nUser: Okay, thanks for the info!\nAgent: You're welcome!",
    "metadata": {
      "product": "ZX-3000",
      "category": "setup",
      "timestamp": "2026-04-09"
    }
  },
  {
    "id": "chat_003",
    "type": "chat_transcript",
    "text": "User: My billing shows extra charges.\nAgent: Let’s check your invoice history.\nUser: I see 2 extra charges.\nAgent: One is late payment, the other is tax adjustment.\nUser: Got it, thanks!\nAgent: Happy to help.",
    "metadata": {
      "product": "ZX-3000",
      "category": "billing",
      "timestamp": "2026-04-09"
    }
  },
  {
    "id": "faq_001",
    "type": "faq_document",
    "text": "Q: How to reset my modem?\nA: Press and hold the reset button for 10 seconds until the lights blink.\n\nQ: How to update firmware?\nA: Login to 192.168.1.1 → Firmware Update → Check for Updates.\n\nQ: How to enable guest Wi-Fi?\nA: Admin panel → Wi-Fi Settings → Guest Network → Enable.",
    "metadata": {
      "product": "ZX-3000",
      "category": "setup",
      "timestamp": "2026-04-09"
    }
  },
  {
    "id": "faq_002",
    "type": "faq_document",
    "text": "Q: What speeds does ZX-3000 support?\nA: Up to 1 Gbps, dual-band Wi-Fi supported.\n\nQ: Can I use it internationally?\nA: Certified for US and Canada only.",
    "metadata": {
      "product": "ZX-3000",
      "category": "specs",
      "timestamp": "2026-04-09"
    }
  },
  {
    "id": "ticket_001",
    "type": "support_ticket",
    "text": "Ticket #1001: Customer reported slow Wi-Fi. Troubleshooting revealed interference on 5 GHz band. Guided customer to switch channels. Issue resolved.",
    "metadata": {
      "product": "ZX-3000",
      "category": "connectivity",
      "timestamp": "2026-04-09"
    }
  },
  {
    "id": "ticket_002",
    "type": "support_ticket",
    "text": "Ticket #1002: Customer unable to print documents. Identified driver issue. Guided to reinstall drivers. Issue resolved.",
    "metadata": {
      "product": "Printer-X",
      "category": "setup",
      "timestamp": "2026-04-09"
    }
  },
  {
    "id": "audio_001",
    "type": "audio_transcript",
    "text": [
      {"speaker": "User", "start_time": "00:00:01", "end_time": "00:00:05", "text": "Hi, my internet drops randomly."},
      {"speaker": "Agent", "start_time": "00:00:06", "end_time": "00:00:12", "text": "Let's check your modem model."},
      {"speaker": "User", "start_time": "00:00:13", "end_time": "00:00:15", "text": "ZX-3000"},
      {"speaker": "Agent", "start_time": "00:00:16", "end_time": "00:00:24", "text": "Your firmware is outdated. Please update it."}
    ],
    "metadata": {
      "product": "ZX-3000",
      "category": "connectivity",
      "timestamp": "2026-04-09"
    }
  },
  {
    "id": "audio_002",
    "type": "audio_transcript",
    "text": [
      {"speaker": "User", "start_time": "00:00:01", "end_time": "00:00:04", "text": "Hello, I can't connect my phone to Wi-Fi."},
      {"speaker": "Agent", "start_time": "00:00:05", "end_time": "00:00:10", "text": "Is your phone detecting the network?"},
      {"speaker": "User", "start_time": "00:00:11", "end_time": "00:00:15", "text": "Yes, but it fails to authenticate."},
      {"speaker": "Agent", "start_time": "00:00:16", "end_time": "00:00:22", "text": "Let's reset your Wi-Fi password and try again."}
    ],
    "metadata": {
      "product": "ZX-3000",
      "category": "connectivity",
      "timestamp": "2026-04-09"
    }
  }
]

products = ["ZX-3000", "ZX-Fiber", "Printer-X", "Router-Y"]
categories = ["connectivity", "setup", "billing", "specs", "firmware"]

new_entries = []
for i in range(50, 101):
    entry = copy.deepcopy(dataset[i % len(dataset)])
    entry["id"] = f"chat_{i:03d}"
    entry["metadata"]["product"] = products[i % len(products)]
    entry["metadata"]["category"] = categories[i % len(categories)]
    entry["metadata"]["timestamp"] = datetime.now().strftime("%Y-%m-%d")
    new_entries.append(entry)

dataset.extend(new_entries)

with open("synthetic_dataset.json", "w") as f:
    json.dump(dataset, f, indent=2)