# Explore Data

# Analyzer Configuration Summary: Text and Audio Analyzers

This document provides a summary of the `ckm-analyzer_config_text.json` and `ckm-analyzer_config_audio.json` files, which define configurations for analyzing both text-based and audio-based call center conversations. These analyzers extract actionable insights such as sentiment, satisfaction, topics, and more.

---

## **Text Analyzer: `ckm-analyzer_config_text.json`**

### **Overview**
- **Analyzer ID**: `ckm-analyzer-text`
- **Scenario**: `text` (processes textual data).
- **Description**: "Conversation analytics" — focuses on analyzing call center conversations.
- **Tags**:
  - `templateId`: `postCallAnalytics-2024-12-01` (template version for post-call analytics).

### **Configuration**
- **`returnDetails`**: `true`  
  Returns detailed results for each analysis.

### **Field Schema**
The text analyzer processes the following fields:

1. **`content`**: Full text of the conversation.
2. **`Duration`**: Duration of the conversation in seconds.
3. **`summary`**: Summarized version of the conversation.
4. **`satisfied`**: Whether the customer was satisfied (`Yes` or `No`).
5. **`sentiment`**: Overall sentiment (`Positive`, `Neutral`, `Negative`).
6. **`topic`**: Primary topic of the conversation in six words or less.
7. **`keyPhrases`**: Top 10 key phrases as a comma-separated string.
8. **`complaint`**: Primary complaint in three words or less.

---

## **Audio Analyzer: `ckm-analyzer_config_audio.json`**

### **Overview**
- **Analyzer ID**: `ckm-analyzer`
- **Scenario**: `conversation` (processes audio-based conversations).
- **Description**: "Conversation process" — focuses on analyzing call center conversations.
- **Tags**:
  - `templateId`: `postCallAnalytics-2024-12-01` (template version for post-call analytics).

### **Configuration**
- **`returnDetails`**: `false`  
  Returns summarized results only.
- **`locales`**: `["en-US"]`  
  Supports English (US) for analysis.

### **Field Schema**
The audio analyzer processes the same fields as the text analyzer:

1. **`content`**: Full text of the conversation.
2. **`Duration`**: Duration of the conversation in seconds.
3. **`summary`**: Summarized version of the conversation.
4. **`satisfied`**: Whether the customer was satisfied (`Yes` or `No`).
5. **`sentiment`**: Overall sentiment (`Positive`, `Neutral`, `Negative`).
6. **`topic`**: Primary topic of the conversation in six words or less.
7. **`keyPhrases`**: Top 10 key phrases as a comma-separated string.
8. **`complaint`**: Primary complaint in three words or less.

---

## **Use Cases**

### **Text Analyzer**
- **Purpose**: Processes text-based call center conversations to extract insights.
- **Use Case**: Analyze chat logs or transcribed conversations to identify trends, customer satisfaction, and key topics.

### **Audio Analyzer**
- **Purpose**: Processes audio-based call center conversations by converting them into text for analysis.
- **Use Case**: Analyze recorded calls to extract insights such as sentiment, satisfaction, and complaints.

---

## **How They Fit Into the Solution**

1. **Data Input**:
    - The text analyzer processes chat logs or transcribed conversations.
    - The audio analyzer processes recorded calls and converts them into text.

2. **Data Output**:
    - Both analyzers generate structured insights (e.g., sentiment, satisfaction, topics) for visualization.

3. **Integration**:
    - Outputs are consumed by the backend (`function_app.py`) to populate charts.
    - Insights are displayed in the frontend (`Chart.tsx`) as visualizations like Donut Charts, Word Clouds, and Tables.

---
