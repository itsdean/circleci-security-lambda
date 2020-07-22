import os

from dotenv import load_dotenv
load_dotenv()

from slack import WebClient
from slack.errors import SlackApiError

class SlackHandler:

    def __init__(self):
        print("\n[slack][init] Initiated")
        key = os.getenv("SLACK_API_TOKEN")
        client = WebClient(
            token = key
        )


    def send_message(self, channel, message):
        print("[slack][send_message] Sending")
        result = client.chat_postMessage(
            channel = channel,
            text = message
        )


    def send_error(self, message):
        print("[slack][send_error] Preparing message")
        alerts_channel = os.getenv("SLACK_ERROR_CHANNEL")
