# Workshop challenge: run each function in the notebooks to see how they work

1. Open the [knowledge_mining_api notebook](./knowledge_mining_api.ipynb) from the Challenge-3-and-4 folder
2. Run the first cell to import the requirements  
3. Run the second cell to define a function to connect to the Azure SQL database.
4. The third cell defines a class that is used to define the plugin for the Azure AI Agent. This contains the various functions that power different behaviors such as greeting, query Azure SQL database and query Azure AI Search. Run cell 3 and 4 to see the results when a user says Hello. The next result will show when a user asks a question and runs the Azure SQL query function. Finally we will see a result when the user asks questions that runs the Azure AI Search function. 
5. Finally, you could update the `user_inputs` in cell 3 to try out more questions. 

```shell
user_inputs = [
                "Hello",
                "Give a summary of billing issues"
                "Total number of calls by date for the last 7 days",
                "Show average handling time by topics in minutes",
                "What are the top 7 challenges users reported?",
                "When customers call in about unexpected charges, what types of charges are they seeing?",
            ]
```
