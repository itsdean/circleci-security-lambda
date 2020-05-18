from cryptography.hazmat.backends import default_backend
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

pass_comment_template = """
:white_check_mark: **The parser did not find any vulnerabilities failing the severity threshold.**
:hash: In total, there were {} issues identified during this build.
"""

fail_comment_template = """
:x: **The parser has found vulnerabilities that failed the severity threshold.**
:hash: In total, there were {} failing issues and {} non-failing issues.

<details>
<summary><b>Security issues</b></summary><br>
{}
</details>
"""

metadata_header = """
**CircleCI Job**: {}
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
If any of the reported issues are a false-positive, create a <code>security.yml</code> file in the root of your project and whitelist those issues in the following format:
<pre><code>whitelist:
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
        print("\n[github][send_pm_comment] Sending comment to PR")

        # Create metadata to help come back to this specific comment in other functions
        timestamp = time.time()
        hash_string = self.salt + ":" + str(timestamp) + ":" + self.metadata["repository"] + ":" + str(self.comment_counter)
        hash_string = hash_string.encode("utf-8")
        information = {
            "hash": hashlib.sha1(hash_string).hexdigest()[1:10],
            "timestamp": timestamp
        }
        print("[github][send_pr_comment] > Hash: " + information["hash"])

        comment = metadata_header.format(
            self.metadata["job_name"],
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(self.metadata["timestamp"]))),
        )

        # Add the custom information from the invoker function.
        # The formatting is done beforehand, so all we need to do is
        # add the text to the string.
        comment += template

        comment += metadata_footer.format(
            information["hash"],
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(information["timestamp"])))
        )

        self.pr.create_issue_comment(
            body=comment
        )

        print("[github][send_pr_comment] > Message posted")


    def send_fail_comment(self, issues):
        print("\n[github][send_fail_comment] Crafting fail comment")

        issue_payload = self.__craft_table(issues)

        self.send_pr_comment(fail_comment_template.format(
            self.metadata["failing_issue_count"],
            self.metadata["non_failing_issue_count"],
            issue_payload
        ))


        # BE CAREFUL.
        self.__close_pr()


    def send_pass_comment(self):

        self.send_pr_comment(pass_comment_template.format(
            self.metadata["non_failing_issue_count"]
        ))

    def __authenticate(self):
        print("\n[github][authenticate] Authenticating")

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
            "https://api.github.com/installations/{}/access_tokens".format(installation_id),
            headers = headers
        )
        print("[github][authenticate] > Authentication token creation response code:", res.status_code)

        if str(res.status_code) != "201":
            print("incoming error, brace\n")
            print(res.body)

        self.authentication_token = res.json()["token"]

        self.g = Github(self.authentication_token)
        print("[github][authenticate] > Authenticated")
        return True


    def __check_pr(self):

        self.metadata["is_pr"] = False

        if self.metadata["pr_number"] != "N/A" or self.metadata["title"].startswith("Merge"):
            self.metadata["is_pr"] = True
            return True

        return False


    def __parse_pr(self):

            print("\n[github][parse_pr] Parsing commit title")

            pr_number_regex = r"(?P<title>Merge pull request #(?P<pr>[0-9]+) from .+)"
            self.metadata["pr_number"] = int(re.search(pr_number_regex, self.metadata["title"]).group("pr"))


    def __get_info(self):
        """
        Get further metadata from GitHub on the project.
        """
        # print("[github] Obtaining repository metadata")
        print("\n[github][get_info] Acquiring context")

        # Get the repository object
        self.repository = self.g.get_repo(self.metadata["full_repository"])

        # Get the GitCommit object via the hash
        commit = self.repository.get_commit(sha=self.metadata["commit"]).commit

        # Get the commit message title.
        title = commit.message.split("\n")[0]
        print("[github][get_info] Commit title: \"" + title + "\"")
        self.metadata["title"] = title

        self.__check_pr()

        if self.metadata["is_pr"]:

            print("[github][get_info] > Commit is part of a pull request")
            print("[github][get_info] >> Obtaining pull request information")

            # The latter check stops redundant code from running in case the PR number is obtained from the folder (which is the case when builds are triggered on PRs being opened).
            if self.metadata["pr_number"] == "N/A":
                self.__parse_pr()

            print("[github][get_info] >> PR mumber:", self.metadata["pr_number"])

            self.pr = self.repository.get_pull(int(self.metadata["pr_number"]))


    def __init__(self, metadata):
        print("\n[github][init] Instantiated")
        self.salt = "alltheseflavoursandyouchoosetobesalty"
        self.comment_counter = 1
        self.metadata = metadata
        if self.__authenticate():
            self.__get_info()