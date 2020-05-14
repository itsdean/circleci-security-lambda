import os

class SlackHandler:

    def __init__(self):
        print("[slack_handler] Initiated")
        key = os.getenv("SLACK_API_TOKEN")