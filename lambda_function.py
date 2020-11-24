import boto3
import csv
import glob
import io
import json
import os
import tempfile
import urllib.parse
import uuid

from github_handler import GitHubHandler
from jira_handler import JiraHandler
# from slack_handler import SlackHandler

s3 = boto3.resource('s3')
s3_client = boto3.client("s3")

def load_metadata(metadata_file, bucket_name):
    print(f"[lambda] retrieving metadata from {metadata_file}")

    with tempfile.TemporaryFile() as metadata_file_object:
        print("[lambda][load_metadata] > downloading metadata file")
        s3_client.download_fileobj(bucket_name, metadata_file, metadata_file_object)
        print("[lambda][load_metadata] > converting to json object")
        metadata_file_object.seek(0)
        metadata_json_object = json.loads(metadata_file_object.read().decode('utf-8'))
        print("[lambda][load_metadata] > loaded into json object\n")
        return metadata_json_object

    return None

def load_report(metadata, report_file, bucket_name):

    print("[lambda] creating GitHubHandler instance\n[lambda] ---")
    g = GitHubHandler(metadata)
    print("[lambda] ---\n[lambda] GitHubHandler instance configured")

    # print("[lambda] parsing report")

    from pprint import pprint
    print()
    pprint(metadata)
    print()

    # issue_count = 0

    all_issues = []
    failing_issues = []
    is_failing = False

    with tempfile.TemporaryFile() as report_file_object:
        print("[lambda][load_report] downloading report file")
        s3_client.download_fileobj(bucket_name, report_file, report_file_object)
        print("[lambda][load_report] > injecting into csv.DictReader")
        report_file_object.seek(0)
        report_string_object = report_file_object.read().decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(report_string_object))

        for row in csv_reader:
            all_issues.append(row)

        if metadata["jira"]:
            j = JiraHandler(metadata)
            j.create_jira_tickets(all_issues)
            j.prune(all_issues) # Look for isolated issues not present in this report
        else:
            print("\n[lambda][load_report] jira not enabled, skipping ticket checking")

        # Now that we've gone through jira, we will have to check if any of the failing issues
        # Have a JIRA status of "vulnerability accepted".
        # If they do, don't report them in the PR comment.
        print("\n[lambda][load_report] collecting failing issues")
        for issue in all_issues:
            if issue["fails"] == "True":
                is_failing = True
                failing_issues.append(issue)

        if metadata["is_pr"]:
            g.send_comment(all_issues)


def lambda_handler(event, context):
    metadata = None

    # Make output clearer to read.
    print("\n---")

    print("\n[lambda] instantiated")

    bucket_name = event["Records"][0]["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    directory = key.rsplit("/", 1)[0]
    print(f"[lambda] directory: {directory}\n")

    # List and get filepaths within "directory"
    filenames = []
    for parser_object in s3.Bucket(bucket_name).objects.filter(Prefix = directory):
        filenames.append(parser_object.key)

    for parser_output_file in filenames:
        # Deal with metadata
        if parser_output_file.endswith(".json"):
            metadata = load_metadata(parser_output_file, bucket_name)

    if metadata is None:
        print("[lambda] warning: metadata file not parsed. please check the s3 bucket!\n")
        return False

    # now that metadata's loaded, deal with the actual report
    load_report(metadata, key, bucket_name)

    # Make output clearer to read.
    print("---\n")

    return True