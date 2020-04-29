import boto3
import json
import os
import pandas as pd
import time
import urllib.parse

from io import StringIO
from slack import WebClient
from slack.errors import SlackApiError

s3 = boto3.client('s3')

message_block = [
    {
        "type": "divider"
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "The parser was invoked by a CircleCI build:"
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": ">Time of trigger: " + payload["pretty_timestamp"] +
            "\n>Repository: " + payload["repository_name"] +
            "\n>Pull request number: " + payload["pull_request"] + 
            "\n>Commit hash: " + payload["commit"] + 
            "\n>"
        }
    },
    {
        "type": "actions",
        "block_id": "options_block",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "View Pull Request"
                },
                "url": "https://github.com/newsuk/" +
                payload["repository_name"] + 
                "/pull/" +
                payload["pull_request"] 
            }
        ]
    },
    {
        "type": "divider"
    },
]

def add_to_block(blob):



def parse_output(csv):

    print("\nlooking for failing issues")

    for index, row in csv.iterrows():
        if row["fails"]:
            print("- found a failing issue.")
            print("  - severity: " + row["severity"].lower())


def slack_ping(payload):
    slack_token = os.environ["SLACK_API_TOKEN"]
    client = WebClient(token=slack_token)

    current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())



    try:
        print("\nsending output to slack")
        response = client.chat_postMessage(
            username="CircleCI Security Parser",
            channel="GR4SVGG6A",
            text="hey",
            blocks=message_block
        )
        print("- output sent\n")
    except SlackApiError as e:
        # You will get a SlackApiError if "ok" is False
        assert e.response["error"]  # str like 'invalid_auth', 'channel_not_found'

def lambda_handler(event, context):

    # Create a JSON payload to pass around
    payload = {}

    # Use a defaut value, in case they don't exist when we get to parsing.
    payload["pull_request"] = "N/A"

    print("\n\n-----")

    # Get the name of the bucket
    payload["bucket"] = event['Records'][0]['s3']['bucket']['name']

    # Get the full name of the object to request from s3.
    payload["key"] = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    # Extract the file name from the key
    # <repo> / <commit_hash> / <job> / ... / output.etc
    options = payload["key"].split('/')

    payload["filename"] = options[-1]

    if payload["filename"].startswith("output") and payload["filename"].endswith(".csv"):
        print("captured file to consume: " + payload["filename"])

        # split filename
        filename_options = payload["filename"].split("_")
        payload["username"] = filename_options[1]
        print("username: " + payload["username"])

        payload["repository_name"] = options[0]
        print("- repo: " + payload["repository_name"])
        payload["commit"] = options[1]
        
        # check if there is a pull request
        if "_" in payload["commit"]:
            payload["pull_request"] = payload["commit"].split("_")[1]
            payload["commit"] = payload["commit"].split("_")[0]
        print("- commit: " + payload["commit"])
        print("- pull_request: " + payload["pull_request"])

        payload["timestamp"] = options[2]
        payload["pretty_timestamp"] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(payload["timestamp"])))
        print("- timestamp: " + payload["timestamp"] + " (" + payload["pretty_timestamp"] + ")")
    
        slack_ping(payload)

        try:
            print("opening csv")
            parsed_output_file = s3.get_object(
                                    Bucket=payload["bucket"],
                                    Key=payload["key"]
                                )


            csv_body = parsed_output_file["Body"].read().decode("utf-8")

            csv = pd.read_csv(StringIO(csv_body))
            # print(csv)

            parse_output(csv)

        except Exception as ex:
            # print("\n" + str(ex) + "\n")
            print()
            raise ex

    print("-----\n\n")

    return 0
