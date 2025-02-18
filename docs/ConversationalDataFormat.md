## Data upload format

### Audio File Format
Azure AI Speech Service is utilized for transcription of conversation audio files. The code is currently configured to support WAV files only, but the code can be modified to support other formats supported by Azure Speech Service. Full details can be found [here](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/).

We have seen successful transcription of files up to 15MB in size but some very large files may experience processing challenges.

Contact center conversations may be uploaded directly as audio to the `cu_audio_files_all` folder in the Fabric lakehouse. o ensure proper processing, all audio files must follow the specified naming convention. Below is an example of the required format:

```
convo_03b0e193-5b55-42d3-a258-b0ff9336ae18_2024-12-05 18_00_00.wav
```
#### Naming Convention Breakdown

1. **`convo`**: The prefix that indicates the file contains a contact center conversation.
2. **Conversation ID (GUID)**: A unique identifier for the conversation, represented as a globally unique identifier (GUID).
3. **Date and Timestamp**: The date and time of the conversation, formatted as `YYYY-MM-DD HH_MM_SS`.


### JSON File Format
Below is a sample structure of a conversation file. Each sentence or phrase is an individual node followed by summary information for the entire call. These formatted conversation files are smaller size, less costly to process, and faster to process.
```json
{
    "ClientId": "10003",
    "ConversationId": "0a7b112e-3e59-4132-82a9-b399f782e859",
    "StartTime": "2024-11-22 03:00:00",
    "EndTime": "2024-11-22 03:14:00",
    "Content": " Agent: Good day, thank you for calling Contoso Inc. This is Chris speaking, how can I assist you today?\n\nCustomer (Susan): Hi Chris, I've been having some network coverage and connectivity issues lately. It's been a bit frustrating.\n\nAgent: I'm sorry to hear that, Susan. I understand how frustrating it can be when you have connectivity issues. Can you tell me more about the issue you are facing and when it first started?\n\nCustomer (Susan): Sure. It's been happening for about a week now. I mostly experience lose of signal when I'm at home. However, the issue doesn't affect my mobile data.\n\nAgent: Thank you for sharing that information, Susan. Just to confirm, this issue only occurs when you are at home, correct?\n\nCustomer (Susan): Yes, that's correct.\n\nAgent: Alright, let's try and see if we can find a resolution for you. Firstly, can you tell me if you have checked your router and modem? Sometimes, network issues can be due to router configuration or problems with the modem.\n\nCustomer (Susan): I haven't really checked on that. I'm not really tech-savvy, to be honest.\n\nAgent: No problem at all, Susan. I'll guide you through the steps to check your router and modem. Firstly, could you please ensure that your router and modem are properly plugged in and switched on?\n\nCustomer (Susan): Just a moment... Okay, everything seems to be plugged in properly, and both the modem and the router are turned on.\n\nAgent: Great! Now, could you try unplugging both the modem and router for 10 seconds and then plugging them back in? This process is called power cycling, and it can help reset your devices.\n\nCustomer (Susan): Alright, I've done that. Let me check if the internet is working... No, unfortunately, the situation hasn't improved.\n\nAgent: Thank you for trying that. Since the issue still persists, I will schedule a technician visit for you. Can you please provide your address?\n\nCustomer (Susan): My address is 123 Elm Street.\n\nAgent: Thank you, Susan. I have scheduled a technician to visit your location tomorrow between 9am and 11am. They will contact you 15 minutes before arrival.\n\nCustomer (Susan): Thank you for arranging that quickly, Chris.\n\nAgent: You're welcome, Susan. I apologize for the inconvenience caused. Is there anything else I can assist you with today?\n\nCustomer (Susan): No, that covers it. Thank you for your help, Chris.\n\nAgent: It's been a pleasure assisting you, Susan. We at Contoso Inc. value your satisfaction and apologize again for the inconvenience. Feel free to call us again if you need any more help. Have a great day!\n\nCustomer (Susan): Thank you, you too!\n\nAgent: This call is now complete. Thank you for choosing Contoso Inc. Goodbye, Susan!"
}

```
