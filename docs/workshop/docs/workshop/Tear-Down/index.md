# Cleanup Resources

## Give us a ⭐️ on GitHub

!!! question "FOUND THIS WORKSHOP AND SAMPLE USEFUL? MAKE SURE YOU GET UPDATES."

The **[Conversation Knowledge Mining Solution Accelerator](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator)** sample is an actively updated project that will reflect the latest features and best practices for code-first development of RAG-based copilots on the Azure AI platform. **[Visit the repo](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator)** or click the button below, to give us a ⭐️.

<!-- Place this tag where you want the button to render. -->
<a class="github-button" href="https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator" data-color-scheme="no-preference: light; light: light; dark: dark;" data-size="large" data-show-count="true" aria-label="Star Conversation Knowledge Mining on GitHub"> Give the Conversation Knowledge Mining Solution Accelerator a Star!</a>

## Provide Feedback

Have feedback that can help us make this lab better for others? [Open an issue](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/issues) and let us know.

## Clean-up

Once you have completed this workshop, delete the Azure resources you created. You are charged for the configured capacity, not how much the resources are used. Follow these instructions to delete your resource group and all resources you created for this solution accelerator.

1. In VS Code, open a new integrated terminal prompt.

2. At the terminal prompt, execute the following command to delete the resources created by the deployment script:

    !!! danger "Execute the following Azure Developer CLI command to delete resources!"

    ```bash title=""
    azd down --purge
    ```

    !!! tip "The `--purge` flag purges the resources that provide soft-delete functionality in Azure, including Azure KeyVault and Azure OpenAI. This flag is required to remove all resources completely."

3. In the terminal window, you will be shown a list of the resources that will be deleted and prompted about continuing. Enter "y" at the prompt to being the resource deletion.

## Persist changes to GitHub

If you want to save any changes you have made to files, use the Source Control tool in VS Code to commit and push your changes to your fork of the GitHub repo.
