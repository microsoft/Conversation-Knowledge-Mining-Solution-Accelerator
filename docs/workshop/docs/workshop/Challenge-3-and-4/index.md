# Chat With Your Data Using Azure AI

In these two challenges, you'll learn how to build an intelligent chat experience using data from earlier exercises — specifically audio and call transcript files that were processed using Content Understanding.

By the end of this challenge, you’ll know how to:
- Use structured and unstructured data together
- Create plugins to query SQL databases and Azure AI Search
- Build a simple AI agent that can answer user questions from your data

---

## What You Already Have

Up to this point, you've:

- Processed **unstructured audio or transcript files**
- Extracted structured data from them into an **Azure SQL Database**
- Stored the full transcript and embeddings in **Azure AI Search**

Now, you'll put this data to work by building an intelligent **chat API** using Semantic Kernel and Azure AI Agents.

---

## Challenge 3: Changing the Logo in the App

In this challenge, you’ll start by customizing the look and feel of your application by changing the app logo. This task introduces you to the basics of working with the app's front-end code.

## Challenge 4: Create Plugins for Chat

In this part, you’ll work in a notebook to explore how plugins are created. There are **three key functions** in the `ChatWithYourDataPlugin` that power different types of chat behavior:

### 1. Greeting Function
A simple function that returns a friendly greeting when the user says "hello".

### 2. Querying Azure SQL Database
This function takes a **natural language question**, converts it into a **SQL query**, runs the query against your database, and returns the result.

-  Example input: `"What were the top complaints in the last month?"`

### 3. Querying Azure AI Search
This function lets users ask questions that are better answered using full-text search.

- Example input: `"What did the customer say about billing?"`

---

## What You'll Do in the Notebook

1. **Run through each function** step-by-step to see how it works
2. The SQL and greeting functions will be **ready to run**
3. The Azure AI Search function will be **commented out at first**
4. As part of the challenge, you'll:

    - Ask questions that require the database
    - Then try questions that rely on search (and see them fail)
    - Then **uncomment the search function**, rerun, and watch it work!

> This simulates the real-world experience of developing a chat system that grows in capability.

---

### Prerequisites
- Azure AI project credentials.
- [Python 3.9+](https://www.python.org/downloads/)
- [Microsoft ODBC Driver 17](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver16#version-17)
- Python environment with required libraries installed (`azure-ai-evaluation`, `pandas`, etc.).
- Access to the Azure API endpoint.
- Completed [Challenge 3](./Challenge-3.md) 

If did not create a virtual environment during Challenge 3, please follow the steps [here](../Challenge-3-and-4/Challenge-3.md) 
1. Navigate to the `workshop/docs/workshop` folder in the terminal in your local repository and run the following command.
* Install the requirements
```shell
pip install -r requirements.txt
```
2. Open the `.env` in the `workshop/docs/workshop` folder to validate the variables were updated with the details of your solution. 
3. Follow the steps in [Challenge-4](./Challenge-4.md) to run the notebook. 

## Bonus: Responsible AI (RAI) Principles

Take a moment to review how the system prompt reflects **RAI principles**:

- What the assistant should or shouldn't say
- How it handles unknown or inappropriate questions
- How it maintains transparency and trust

Feel free to enhance the agent prompt with RAI-friendly language.

## Recap

In these two challenges, you:

- Built chat plugins to work with structured (SQL) and unstructured (search) data
- Integrated them into an AI agent with defined behavior
- Practiced testing and debugging the system step-by-step


