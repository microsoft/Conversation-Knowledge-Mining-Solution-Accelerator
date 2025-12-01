
<!-- ## Frontend Overview -->

**Folder**: `src/App/Frontend`

The frontend is a **React-based web interface** that allows users to explore insights from conversations, interact with an AI-powered chatbot, and view dynamic visualizations.


![image](../../img/ReadMe/ckm-ui.png)


### Features

1. **Dynamic Chart Rendering**

    - Renders charts like Donut, Bar, and Word Cloud using **Chart.js**.
    - Visualizes insights such as sentiment, topics, and keywords.

2. **Chatbot Interface**

    - Allows users to query via natural language.
    - Auto-generates insights and charts.

3. **Filter Management**

    - Filters such as **Date**, **Sentiment**, **Topic**.
    - Updates chart views dynamically.


### Workflow (Frontend)

| Step | Description | Maps to Architecture |
|------|-------------|----------------------|
| 1. **Initial Load** | Fetch chart/filter data. |  API Layer |
| 2. **Chatbot Queries** | Send messages to backend. |  Azure OpenAI + Semantic Kernel|
| 3. **Chart Rendering** | Render chart components. |  Web Front-end |
| 4. **History Sync** | Display chat history. |  Cosmos DB |

###  Tools & Libraries

- **React**
- **Chart.js**
- **Axios**

---
