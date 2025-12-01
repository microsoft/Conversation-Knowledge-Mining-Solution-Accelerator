
<!-- ## Backend Overview -->

**Folder**: `src\App\backend`

The backend is a **Python Quart app** that processes queries, generates insights, and communicates with databases and AI services.

### Features

1. **Azure OpenAI Integration**

    - Handles natural language queries from users.
    - Calls Azure OpenAI for understanding and response generation.

2. **Semantic Kernel Plugin**: 

    - Powers natural language interactions via custom kernel functions

2. **Data Access**

    - SQL for structured data.
    - Azure Cognitive Search for transcripts.

3. **Chat History**

    - Cosmos DB for storing user conversations.

4. **Chart Processing**

    - Converts results to chart-ready JSON that is then used to diplay chart on the frontend.

### Semantic Kernel Plugin Breakdown

Located in `ChatWithDataPlugin`:

**greeting()**

    - Responds to simple greetings or general questions

    - Uses either Azure AI Project or direct OpenAI client

**get_SQL_Response()**

    - Converts natural language questions into valid SQL queries


**get_answers_from_calltranscripts()**

    - Performs Retrieval-Augmented Generation (RAG)

    - Uses semantic + vector hybrid search with Azure AI Search

    - Returns summarized or specific insights from indexed call data

###  Tools & Libraries

- **Quart**
- **Azure OpenAI**
- **CosmosDB SDK**
- **SQLAlchemy**
- **Semantic Kernel**
- **Azure AI Search**

---