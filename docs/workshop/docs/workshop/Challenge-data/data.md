# 🧠 Understanding the Data in the Conversation Knowledge Mining Solution Accelerator

This document is a comprehensive walkthrough of the **data** used and generated in the [Conversation Knowledge Mining Solution Accelerator](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator) by Microsoft. This guide is designed to help you understand **how conversational data flows**, is **processed**, and is **transformed into insights** using Azure services.

---

## 1. Raw Data Input

### Audio Files
- Format: `.wav`
- Location: Uploaded to Azure Blob Storage (`<resource-group-name>-sa`)
- file: `data/audio/sample-call.wav`

**Purpose**: Represents real-world customer interactions (e.g., support calls).

---

## 📝 2. Transcription (Speech-to-Text)

### ✅ Service Used: Azure Cognitive Services – Speech

- Converts `.wav` audio files into **text transcripts**
- Output: JSON with text and metadata (timestamps, speaker info)
- Example Output:
```json
{
  "DisplayText": "Thank you for calling customer support...",
  "Offset": 12300000,
  "Duration": 5500000
}
Location: Saved in Blob Storage and later processed by the pipeline


## 📝 2. Transcription (Speech-to-Text)

### ✅ Service Used: Azure Cognitive Services – Speech

## 3. Text Processing and Insight Generation

### ✅ Service Used: Azure OpenAI (via Azure AI Foundry Pipelines)
This step uses LLMs to process raw transcript and extract insights:
- Key Phrase Extraction – Main themes or terms
- Summarization – Condensed version of the conversation
- Topic Modeling – High-level categorization

Sentiment Analysis (optional)
- Converts `.wav` audio files into **text transcripts**
- Output: JSON with text and metadata (timestamps, speaker info)
- Example Output:
```json
{
  "conversation_id": "12345",
  "key_phrases": ["billing issue", "account cancellation"],
  "summary": "Customer called to cancel due to a billing issue.",
  "topics": ["Billing", "Account Management"]
}
