# How To Create Azure AI Service
1. Navigate to https://portal.azure.com/#create/Microsoft.CognitiveServicesAIServices .
2. Select your Azure subscription.
3. Select the available Resource group.
4. Choose the region which support Content Understanding service from below tables.
   | Geography | Region         | Region Identifier|
   | --------- | -------------- | ---------------- |
   | US        | West US        | westus           |
   | Europe    | Sweden Central | swedencentral    |
   | Australia | Australia East | australiaeast    |
5. Enter a name for your resource.
6. Choose a price plan.  
    <img src="./create_srv_1.png" width="600" />
7. Configure other settings for your resource as needed, read, and accept the conditions (as applicable), and then select Review + create.  
    <img src="./create_srv_2.png" width="600" />
8. Azure will run a quick validation check, after a few seconds you should see a green banner that says Validation Passed.
9. Once the validation banner appears, select the Create button from the bottom-left corner.
10. After you select create, you'll be redirected to a new page that says Deployment in progress. After a few seconds, you'll see a message that says, Your deployment is complete.
11. Navigate to the resouce. In the left navigation menu, select "Keys and Endpoint", then get the **key** and **endpoint**.   
    <img src="./create_srv_3.png" width="600" />  
Now，you could start with these information to run the samples.