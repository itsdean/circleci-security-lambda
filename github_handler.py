from cryptography.hazmat.backends import default_backend
import base64
import hashlib
import jwt
import os
import re
import requests
import time

from github import Github
from pprint import pprint

from dotenv import load_dotenv
load_dotenv()

forced_comment_template = """
:warning: | **The fail threshold was explicitly turned off for this scan!**
"""

pass_comment_template = """
:white_check_mark:  | **The parser did not find any vulnerabilities failing the severity threshold.**
:hash:  | In total, there were {} issues identified during this build.
"""

fail_comment_template = """
:x:  | **The parser has found vulnerabilities that failed the severity threshold.**
:hash:  | In total, there were {} failing issues.

<details>
<summary><b>Security issues</b></summary><br>
{}
</details>
"""

metadata_header = """
{}
**Scan time**: {}

---

"""

metadata_footer = """

---
To look at the entire report, please view the job's artifacts on CircleCI.
There will be a <code>parsed_output/*.csv</code> file containing all reported issues.

<details>
<summary><i>Need to mark issues as false positives?</i></summary>

<sub>
If any of the reported issues are a false-positive, create a <code>.security</code> folder, with a <code>parser.yml</code> file inside, allowing the issues in the following format:
<pre><code>allowlist:
 ids:
  - &lt;issue_id_1&gt;
  - &lt;issue_id_2&gt;
  - etc.</code></pre>
Future reports will ignore those issues.
</sub>
</details>

---

<details>
    <summary><sub>Boring comment metadata</sub></summary>
    <sub>
    Comment hash: {}</br>
    Time of comment creation: {}
    </sub>
</details>
"""

minimizecomment_mutation = """
mutation MinimizeComment($commentId: ID!, $minimizeReason: ReportedContentClassifiers!) {
    minimizeComment(input: {subjectId: $commentId, classifier: $minimizeReason}) {
        clientMutationId
    }
}
"""


class GitHubHandler:


    def __craft_table(self, issues):
        table = ""

        for counter, issue in enumerate(issues):

            # print(counter)

            description = issue["description"].split("\n")[0]

            if counter != 0:
                table += "\n"

            table += "<b>Title</b>: " + issue["title"] + "<br>"
            table += "<b>Severity</b>: " + issue["severity"] + "</br>"
            table += "<b>Description</b>: " + description + "</br>"
            table += "<b>Location</b>: " + issue["location"] + "</br>"
            table += "<b>Reported by</b>: " + issue["tool_name"] + "</br>"
            table += "<b>Issue ID</b>: " + issue["uid"]

            if not counter + 1 == len(issues):
                table += "<br><br>"

        return table


    def __close_pr(self):
        self.pr.edit(state="closed")


    def send_pr_comment(self, template):
        print("[github][send_pr_comment] sending comment to pull request")

        # Create metadata to help come back to this specific comment in other functions
        timestamp = time.time()
        hash_string = self.salt + ":" + str(timestamp) + ":" + self.metadata["repository"] + ":" + str(self.comment_counter)
        hash_string = hash_string.encode("utf-8")
        information = {
            "hash": hashlib.sha1(hash_string).hexdigest()[1:10],
            "timestamp": timestamp
        }
        print("[github][send_pr_comment] > hash: " + information["hash"])

        if self.metadata["is_circleci"]:
            job = self.metadata["circleci_info"]["job"]
            job_comment = f"**CircleCI Job**: {job}"
        else:
            job_comment = "**I'm not sure what job was run!**"

        comment = metadata_header.format(
            job_comment,
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(self.metadata["timestamp"]))),
        )

        if self.metadata["fail_threshold"] == "off":
            comment += forced_comment_template

        # Add the custom information from the invoker function.
        # The formatting is done beforehand, so all we need to do is
        # add the text to the string.
        comment += template

        comment += metadata_footer.format(
            information["hash"],
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(information["timestamp"])))
        )

        # look for the last parser comment and hide it
        #####

        comments = []
        for pr_comment in self.pr.get_issue_comments():
            comments.append(pr_comment)

        # now flip it and reverse it
        for pr_comment in reversed(comments):
            if "circleci-security-parser" in pr_comment.user.login:

                print("[github][send_pr_comment] marking past comment (if any) as outdated")
                # wow we have to manually do this lmao
                comment_id = pr_comment.id
                print(f"[github][send_pr_comment] comment id: {comment_id}")
                print(f"[github][send_pr_comment] > converting to v4 node_id")
                comment_node_id = base64.b64encode(f"012:IssueComment{comment_id}".encode("utf-8"))
                print(f"[github][send_pr_comment] > v4 node id: {comment_node_id}")

                headers = {
                    "Authorization": "Bearer {}".format(self.authentication_token)
                }

                variables = {
                    "commentId": comment_node_id,
                    "minimizeReason": "OUTDATED"
                }

                request = requests.post(
                    'https://api.github.com/graphql',
                    json={
                        'query': minimizecomment_mutation,
                        'variables': variables
                    },
                    headers=headers
                )

                if request.status_code == 200:
                    print(f"[github][send_pr_comment] > past comment should now be outdated")
                else:
                    print("[github][send_pr_comment] > warning: unable to hide past comment")

                break

        self.pr.create_issue_comment(
            body=comment
        )

        print("[github][send_pr_comment] > comment posted")


    def send_fail_comment(self, issues):
        print("[github][send_fail_comment] crafting fail comment")

        issue_payload = self.__craft_table(issues)

        self.send_pr_comment(fail_comment_template.format(
            len(issues),
            issue_payload
        ))        

        # BE CAREFUL.
        # self.__close_pr()


    def send_pass_comment(self, issue_count):

        self.send_pr_comment(pass_comment_template.format(
            issue_count
        ))


    def __authenticate(self):
        print("[github][authenticate] authenticating")

        filename = "pkey.pem"
        cert_str = open(filename, "r").read()
        cert_bytes = cert_str.encode()

        private_key = default_backend().load_pem_private_key(cert_bytes, None)

        timestamp = int(time.time())

        payload = {
            "iat": timestamp,
            "exp": timestamp + (10 * 60),
            "iss": "58070"
        }

        gh_jwt = jwt.encode(payload, private_key, algorithm="RS256")

        headers = {
            "Authorization": "Bearer {}".format(gh_jwt.decode()),
            "Accept": "application/vnd.github.machine-man-preview+json"
        }

        res = requests.get(
            "https://api.github.com/app",
            headers = headers
        )

        # Okay, now that we are authenticated, lets get an access token
        installation_id = os.getenv("GITHUB_INSTALLATION_ID")

        res = requests.post(
            "https://api.github.com/app/installations/{}/access_tokens".format(installation_id),
            headers = headers
        )
        print("[github][authenticate] > authentication token creation response code:", res.status_code)

        if str(res.status_code) != "201":
            print("incoming error, brace\n")
            print(res.body)

        self.authentication_token = res.json()["token"]

        self.g = Github(self.authentication_token)
        print("[github][authenticate] > authenticated")
        return True


    def __get_info(self):
        """
        Get further metadata from GitHub on the project.
        """

        # Get the repository object
        print("[github][get_info] getting repository")
        project_username = self.metadata["project_username"]
        repository = self.metadata["repository"]
        repository_path = f"{project_username}/{repository}"
        self.repository = self.g.get_repo(repository_path)

        # Get the GitCommit object via the hash
        print("[github][get_info] getting commit")
        commit = self.repository.get_commit(sha=self.metadata["commit_hash"]).commit

        # Get the commit message title.
        title = commit.message.split("\n")[0]
        print("[github][get_info] Commit title: \"" + title + "\"")
        # self.metadata["title"] = title

        if self.metadata["is_pr"]:
            print("[github][get_info] > this is a pull request commit")
            print("[github][get_info] > getting pr information")
            print(f"[github][get_info] >> pr url: {self.metadata['pr_info']['pr_url']}")
            self.pr = self.repository.get_pull(int(self.metadata['pr_info']['pr_number']))


    def __init__(self, metadata):
        print("[github][__init__] instantiated")
        self.salt = "alltheseflavoursandyouchoosetobesalty"
        self.comment_counter = 1
        self.metadata = metadata
        if self.__authenticate():
            self.__get_info()