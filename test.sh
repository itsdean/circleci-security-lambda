#!/bin/bash
SLACK_API_TOKEN=***REMOVED*** python-lambda-local -t 10 -f lambda_handler lambda_function.py test.json 