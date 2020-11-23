#!/bin/bash

yum install -y python3-pip zip libyaml-devel libffi-devel openssl-devel

cd /lambda && pip3 install  -t ./package -r requirements.txt
cd /lambda/package && zip -r9 /lambda/lambda-package.zip .
cd /lambda && zip -g lambda-package.zip lambda_function.py pkey.pem github_handler.py slack_handler.py jira_handler.py

rm -r /lambda/package
