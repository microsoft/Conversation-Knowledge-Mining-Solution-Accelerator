from config.constants import *
import requests
import json
from dotenv import load_dotenv
import os
import uuid

class BasePage:
    def __init__(self, page):
        self.page = page

    def scroll_into_view(self,locator):
        reference_list = locator
        locator.nth(reference_list.count()-1).scroll_into_view_if_needed()

    def is_visible(self,locator):
        locator.is_visible()

    def validate_response_status(self,questions):
        load_dotenv()
        WEB_URL = os.getenv("web_url")
        
        url = f"{API_URL}/api/chat"
       

        user_message_id = str(uuid.uuid4())
        assistant_message_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())

        payload = {
            "messages": [{"role": "user", "content": questions,
                            "id": user_message_id}],
            "conversation_id": conversation_id,
        }
        # Serialize the payload to JSON
        payload_json = json.dumps(payload)
        headers = {
            "Content-Type": "application/json-lines",
            "Accept": "*/*"
        }
        response = self.page.request.post(url, headers=headers, data=payload_json)
        # Check the response status code
        assert response.status == 200, "response code is " + str(response.status)

        self.page.wait_for_timeout(10000)

