# Conversation Knowledge Mining Solution Accelerator: Hands-on Workshop

| [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator) | [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator) | 


### About the Conversation Knowledge Mining Solution Accelerator

Gain actionable insights from large volumes of conversational data by identifying key themes, patterns, and relationships. Using Azure AI Foundry, Azure AI Content Understanding, Azure OpenAI Service, and Azure AI Search, this solution analyzes unstructured dialogue and maps it to meaningful, structured insights.

Capabilities such as topic modeling, key phrase extraction, speech-to-text transcription, and interactive chat enable users to explore data naturally and make faster, more informed decisions.

Analysts working with large volumes of conversational data can use this solution to extract insights through natural language interaction. It supports tasks like identifying customer support trends, improving contact center quality, and uncovering operational intelligence—enabling teams to spot patterns, act on feedback, and make informed decisions faster.

### Solution architecture
![High-level architecture diagram for the solution](./docs/workshop/img/ReadMe/techkeyfeatures.png)

### Workshop Guide

The current repository is instrumented with a `workshop/docs` folder that contains the step-by-step lab guide for developers, covering the entire workflow from resource provisioning to ideation, evaluation, deployment, and usage.

 You can **preview and extend** the workshop directly from this source by running the [MKDocs](https://www.mkdocs.org/) pages locally:

1. Install the `mkdocs-material` package

    ```bash
    pip install mkdocs-material mkdocs-jupyter
    ```

2. Run the `mkdocs serve` command from the `workshop` folder

    ```bash
    cd docs/workshopcd
    mkdocs serve -a localhost:5000
    ```

This should run the dev server with a preview of the workshop guide on the specified local address. Simply open a browser and navigate to `http://localhost:5000` to view the content.

(Optional) If you want to deploy the workshop guide to a live site, you can use the `mkdocs gh-deploy` command to push the content to a GitHub Pages site.
