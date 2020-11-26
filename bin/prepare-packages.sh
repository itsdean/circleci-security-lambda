#!/bin/bash

yum install -y python3-pip zip libyaml-devel libffi-devel openssl-devel

# jump into an empty directory and install pip requirements into a "/package/" folder
cd /lambda && pip3 install  -t ./package -r requirements.txt

# zip up the /package/ folder into lambda-package.zip
cd /lambda/package && zip -r9 /lambda/lambda-package.zip .

# in the root of that zip, add the other lambda files.
# the tree of that zip should be:
# - package/
# -     <all the pip3 packages>
# - lambda_function.py
# - pkey.pem
# - etc/
cd /lambda && zip -g lambda-package.zip lambda_function.py pkey.pem github_handler.py slack_handler.py jira_handler.py

rm -r /lambda/package
