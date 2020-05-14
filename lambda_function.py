import boto3
import csv
import io
import json
import os
# import time
import urllib.parse
import uuid

from github_handler import GitHubHandler
# from io import StringIO
# from slack import WebClient
# from slack.errors import SlackApiError
# from slacker import Slacker

s3 = boto3.client('s3')

def lambda_handler(event, context):
    # Make output clearer to read.
    print("\n---")

    metadata = {}
    # slacker = Slacker()

    # Store metadata relating to the bucket object.
    metadata["pr_number"] = "N/A"
    metadata["bucket_name"] = event["Records"][0]["s3"]["bucket"]["name"]
    metadata["key"] = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    # Fracture the key and obtain metadata from its elements
    key_options = metadata["key"].split("/")
    # print(key_options)
    metadata["repository"] = key_options[0]
    metadata["filename"] = key_options[-1]
    metadata["commit"] = key_options[1]

    # Reintroducing checks for the pull request value being inserted into the commit folder.
    if "_" in metadata["commit"]:
        commit_options = metadata["commit"].split("_")
        metadata["commit"] = commit_options[0]
        metadata["pr_number"] = commit_options[1]

    metadata["timestamp"] = key_options[2]
    metadata["job_name"] = key_options[3]

    print("[lambda] Filename: " + metadata["filename"])

    if not (metadata["filename"].startswith("output") and
        metadata["filename"].endswith(".csv")):
        return False
    else:
        print("[lambda] > File is parsed output")

    filename = metadata["filename"]

    # Fracture the filename and obtain metadata from its elements
    filename_options = filename.split(".")[0].split("_")
    metadata["username"] = filename_options[1]
    metadata["branch"] = filename_options[2]
    # metadata["timestamp"] = filename_options[3]

    metadata["full_repository"] = metadata["username"] + "/"
    metadata["full_repository"] += metadata["repository"]

    # Open the file, it's time to parse it
    try:
        # print("[lambda_handler] Temporarily saving " + filename)
        s3_object = s3.get_object(
            Bucket = metadata["bucket_name"],
            Key = metadata["key"]
        )

        random_filename = str(uuid.uuid4())
        filepath = "/tmp/" + random_filename

        with open(filepath, "wb") as tmp_file:
            s3.download_fileobj(
                metadata["bucket_name"],
                metadata["key"],
                tmp_file
            )

        metadata["failing_issues"] = []
        metadata["is_failing"] = False

        # Get the size of the .csv file.
        issue_count = len(open(filepath).readlines())

        # We will reduce the length by one for every failing issue.
        metadata["non_failing_issue_count"] = issue_count

        with open(filepath, "r") as csv_file:
            csv_reader = csv.DictReader(csv_file)

            for row in csv_reader:
                # print(row["fails"])

                # Look for failing issues.
                # If there are any, then add them to the metadata object and invoke github settings.
                if row["fails"] == "True":
                    metadata["is_failing"] = True
                    metadata["failing_issues"].append(row)
                    metadata["non_failing_issue_count"] -= 1

            metadata["failing_issue_count"] = len(metadata["failing_issues"])

        g = GitHubHandler(metadata)

        if metadata["is_failing"]:
            print("\n[lambda] The scan associated with the output failed.")
            print("[lambda] > There were {} failing issues and {} non-failing issues.".format(
                metadata["failing_issue_count"],
                metadata["non_failing_issue_count"]
            ))
            print("[lambda] > Preparing to report this.")

            g.send_pm_comment(metadata["failing_issues"])

        else:
            print("[lambda_handler] Scan had no failing issues. All gucci.")

    except Exception as ex:
        raise ex

    # Make output clearer to read.
    print("---\n")

    return True