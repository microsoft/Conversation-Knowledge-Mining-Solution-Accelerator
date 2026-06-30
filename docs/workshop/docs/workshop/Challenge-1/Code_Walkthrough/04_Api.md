<!-- ##  API Overview -->

 **Folder**: [`src/api`](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/tree/main/src/api)

###  Key Endpoints

####  Chart & Filters

- `GET /api/fetchChartData`
    - Loads default chart data

- `POST /api/fetchChartDataWithFilters`
    - Applies filters and regenerates chart based on user input

- `GET /api/fetchFilterData`
    - Loads values for filter dropdowns (sentiment, topics, dates)

####  Chatbot

- `POST /api/chat`
    - Sends user’s question and filters to AI engine
    - Returns streamed natural language answer

####  Conversation History

- `POST /history/generate`
    - Starts a new conversation thread, returns conversation_id

- `POST /history/update`
    - Updates chat history with question and answer

- `GET /history/list`
    - Lists all conversation histories

- `POST /history/read`
    - Loads full Q&A history for a specific thread

- `DELETE /history/delete`
    - Deletes a conversation by ID



---

<!-- ##  Architecture to Code Mapping

| Component                          | Location                        |
|-----------------------------------|----------------------------------|
| Web Front-End                     | `src/web-app`                    |
| API Layer                         | `src/api`                        |
| Azure OpenAI + Semantic Kernel    | `src/api/conversationInsightsProcessor` |
| Chart Data Processing             | `src/api/chartProcessor/`        |
| Vector Search + SQL               | `src/api/vectorIndexer/`        |
| Cosmos DB for History             | Handled in `history` endpoints   |

--- -->