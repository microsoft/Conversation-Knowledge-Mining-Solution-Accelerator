<!-- # Explore the code -->
<!-- ## Overview -->
The Conversation Knowledge Mining Solution Accelerator is a robust application designed to extract actionable insights from conversational data. It leverages Azure AI services and provides an interactive user interface for querying and visualizing data. The solution is built with a modular architecture, combining a React-based frontend, a FastAPI backend, and Azure services for data processing and storage.


![image](../img/ReadMe/ckm-sol-arch.png)


The solution extracts insights from call audio files or transcripts and enables users to interact with the data via a chatbot and dynamic charts:

1. **Ingest**: Audio/transcripts are stored.

2. **Understand**: Azure AI extracts conversation details.

3. **Index & Store**: Data is vectorized and stored in SQL + Azure AI Search.

4. **Orchestrate**: Chatbot + chart logic handled by APIs.

5. **Frontend**: Displays insights using charts and chat interface.

## Key Features

### Data Processing and Analysis:

- Processes conversational data using Azure AI Foundry, Azure AI Content Understanding, and Azure OpenAI Service.
- Extracts insights such as sentiment, key phrases, and topics from conversations.
- Supports speech-to-text transcription for audio data.

### Dynamic Dashboard:

- Visualizes insights through various chart types (e.g., Donut Chart, Bar Chart, Word Cloud).
- Enables filtering and customization of data views.
- Provides a responsive layout for seamless user experience.


### Interactive Chat Interface:

- Allows users to query data in natural language and receive real-time responses.
- Supports both text-based and chart-based responses.
- Integrates with Azure OpenAI and Azure Cognitive Search for generating responses and retrieving relevant data.

### Backend API:

- Built with FastAPI for handling requests and integrating with Azure services.
- Includes modular routes for backend operations and conversation history management.
- Provides a health check endpoint for monitoring service status.

### Scalable Deployment:

- Supports deployment via GitHub Codespaces, VS Code Dev Containers, or local environments.
- Includes configurable deployment settings for regions, models, and resource capacities.