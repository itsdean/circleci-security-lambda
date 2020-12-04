import os

from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from slack import WebClient
from slack.errors import SlackApiError

MESSAGE = """
*Repository*: {}
*Branch*: {}
*Job*: {}

*Lambda triggered at {}*
"""

UPDATE = """
*Update*: {} - {}
"""

ISSUE_COUNT_TEMPLATE = """
*Issue Count*

Critical: {}
High : {}
Medium: {}
Low: {}
Informational: {}
"""

FINISH = """
*Lambda completed at {}*
"""

class SlackHandler:

    def __init__(self, metadata):
        print("[slack][__init__] initiated")
        self.m = metadata
        self.alerts_channel = os.getenv("SLACK_ALERT_CHANNEL")

        key = os.getenv("SLACK_API_TOKEN")
        try:
            self.client = WebClient(
                token = key
            )
            print("[slack][__init__] client created\n---\n")
            self.initiate()

        except SlackApiError:
            print("[slack][__init__] client creation failed\n---\n")
            self.client = None


    def initiate(self):    
        now = datetime.now()

        message = self.client.chat_postMessage(
            icon_emoji = ":circle-ci:",
            username = "CircleCI Security Alerts",
            channel = self.alerts_channel,
            text = MESSAGE.format(
                self.m["repository"],
                self.m["branch"],
                self.m["circleci_info"]["job"],
                now.strftime("%m/%d/%Y %H:%M:%S")
            )
        )
        self.thread = message


    def update(self, message):

        if self.client:
            now = datetime.now()

            # return self.client.chat_update(
            return self.client.chat_postMessage(
                icon_emoji = ":circle-ci:",
                username = "CircleCI Security Alerts",
                channel = self.alerts_channel,
                # ts = metadata["ts"],
                thread_ts = self.thread["ts"],
                text = UPDATE.format(
                    now.strftime("%m/%d/%Y %H:%M:%S"),
                    message
                )
            )


    def finish(self):
        if self.client:
            now = datetime.now()

            # return self.client.chat_update(
            self.client.chat_postMessage(
                icon_emoji = ":circle-ci:",
                username = "CircleCI Security Alerts",
                channel = self.alerts_channel,
                # ts = metadata["ts"],
                thread_ts = self.thread["ts"],
                text = "---"
            )
            return self.client.chat_postMessage(
                icon_emoji = ":circle-ci:",
                username = "CircleCI Security Alerts",
                channel = self.alerts_channel,
                # ts = metadata["ts"],
                thread_ts = self.thread["ts"],
                text = FINISH.format(
                    now.strftime("%m/%d/%Y %H:%M:%S")
                )
            )


    def send_issue_count(self, issue_count):
        if self.client:
            self.client.chat_postMessage(
                icon_emoji = ":circle-ci:",
                username = "CircleCI Security Alerts",
                channel = self.alerts_channel,
                # ts = metadata["ts"],
                thread_ts = self.thread["ts"],
                text = ISSUE_COUNT_TEMPLATE.format(
                    issue_count["critical"],
                    issue_count["high"],
                    issue_count["medium"],
                    issue_count["low"],
                    issue_count["informational"]
                )
            )
            self.client.chat_postMessage(
                icon_emoji = ":circle-ci:",
                username = "CircleCI Security Alerts",
                channel = self.alerts_channel,
                # ts = metadata["ts"],
                thread_ts = self.thread["ts"],
                text = "---"
            )
