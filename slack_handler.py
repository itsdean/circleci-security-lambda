import os

from dotenv import load_dotenv
load_dotenv()

# from slack import WebClient
# from slack.errors import SlackApiError

class SlackHandler:

    def __init__(self):
        print("\n[slack] Initiated")
        key = os.getenv("SLACK_API_TOKEN")