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

pm_comment = """
**Summit has found vulnerabilities that failed the severity threshold.**

**Job**: {}
**Scan time**: {} 

---

**The following issues must be looked at and dealt with, before the security steps will pass**:

{}

---

In total, there were {} failing issues and {} non-failing issues.

If any of the reported issues are a false-positive, create a `security.yml` file in the root of your project and whitelist those issues in the following format:
```
whitelist:
 - <issue_id_1>
 - <issue_id_2>
 - etc.
```

Future Summit scans will ignore those issues.

---

##### Boring comment metadata
<sub>
Comment hash: {}</br>
Time of comment creation: {}
</sub>
"""


class GitHubHandler:


    def __craft_table(self, issues):
        table = ""

        for counter, issue in enumerate(issues):

            # print(counter)

            description = issue["description"].split("\n")[0]

            if counter != 0:
                table += "\n"

            table += "**Title**: " + issue["title"] + "\n"
            table += "**Severity**: " + issue["severity"] + "\n"
            table += "**Description**: " + description + "\n"
            table += "**Location**: " + issue["location"] + "\n"
            table += "**Reported by**: " + issue["tool_name"] + "\n"
            table += "**Issue ID**: " + issue["uid"]

            if not counter + 1 == len(issues):
                table += "\n"

        return table


    def send_pm_comment(self, issues):
        print("\n[github][send_pm_comment] Crafting and sending comment")

        issue_payload = self.__craft_table(issues)

        # Create metadata to help come back to this specific comment in other function
        hash_string = self.salt + ":" + self.metadata["repository"] + ":" + str(self.comment_counter)
        hash_string = hash_string.encode("utf-8")
        information = {
            "hash": hashlib.sha1(hash_string).hexdigest()[1:10],
            "timestamp": time.time()
        }

        print("[github][send_pm_comment] > Hash: " + information["hash"])

        payload = pm_comment.format(
            self.metadata["job_name"],
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(self.metadata["timestamp"]))),
            issue_payload,
            self.metadata["failing_issue_count"],
            self.metadata["non_failing_issue_count"],
            information["hash"],
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(information["timestamp"]))),
        )
        # print(comment)

        self.pr.create_issue_comment(
            body=payload
        )

        # BE CAREFUL.
        self.pr.edit(status="closed")

        print("[github][send_pm_comment] > Message posted")

        return information


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
            print("[github][get_info] >>> Obtaining pull request information")

            # The latter check stops redundant code from running in case the PR number is obtained from the folder (which is the case when builds are triggered on PRs being opened).
            if self.metadata["pr_number"] == "N/A":
                self.__parse_pr()

            self.pr = self.repository.get_pull(int(self.metadata["pr_number"]))


    def __init__(self, metadata):
        print("\n[github][init] Instantiated")
        self.salt = "alltheseflavoursandyouchoosetobesalty"
        self.comment_counter = 1
        self.metadata = metadata
        if self.__authenticate():
            self.__get_info()

        if self.metadata["is_pr"]:
            print("\n[github][init] PR Number:", self.metadata["pr_number"])