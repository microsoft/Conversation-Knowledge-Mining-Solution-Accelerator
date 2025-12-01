# Evaluation

## Content Safety Evaluation

This notebook demonstrates how to evaluate content safety using Azure AI's evaluation tools. It includes steps to:

* Simulate content safety and grounded scenarios.
* Evaluate content for safety metrics such as violence, sexual content, hate/unfairness, and self-harm.
* Generate evaluation reports in JSON format.

### Prerequisites
- Azure AI project credentials.
- [Python 3.9+](https://www.python.org/downloads/)
- Python environment with required libraries installed (`azure-ai-evaluation`, `pandas`, etc.).
- Access to the Azure API endpoint.
- Completed [Challenge 3](../Challenge-3-and-4/Challenge-3.md)


If you did not create a virtual environment during the Challenge 3, please follow the steps [here](../Challenge-3-and-4/Challenge-3.md)
1. Navigate to the `workshop/docs/workshop` folder in the terminal in your local repository and run the following commands 
2. In the terminal run the following command 

* Install the requirements
```shell
pip install -r requirements.txt
```
3. Open the `.env` in the `workshop/docs/workshop` folder to validate the variables were updated with the details of your solution. 
4. Open the [Content_safety_evaluation notebook](./Content_safety_evaluation.ipynb) 
5. Run the first cell to create a folder for the output file of the evaluations.
6. Run cells 2-4 to initialize your Azure AI Project, the call streaming function and callback function. 
7. Cell 5 run the Adversarial Scenario to generate questions, run the questions against your AI solution and write these results to a local file. Cell 6 will format the output of the results.  
    - The Adversarial Scenario will run content safety evaluation tests on your AI solution 
8. Cell 7 and 8 initialize the model configuration and the Groundedness Evaluator. The groundedness measure assesses the correspondence between claims in an AI-generated answer and the source context, making sure that these claims are substantiated by the context. 
    - Learn more about the groundedness evaluator [here](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/evaluate-sdk#performance-and-quality-evaluator-usage)
