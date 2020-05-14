#!/bin/bash

BUCKET="appsec-parser-test"
PACKAGE="lambda-package.zip"

./bin/docker-run.sh

# upload to an s3 bucket as numpy makes this b i g. fs.
# aws --profile personal-develop s3 cp ./ s3://$BUCKET_NAME/ --recursive --exclude "*" --include "lambda-package.zip" 
aws --profile personal-develop s3 cp $PACKAGE s3://$BUCKET/$PACKAGE

# upload to a lambda via the s3 bucket object. 
aws --profile personal-develop lambda update-function-code --function-name consume_parsed_output --s3-bucket $BUCKET --s3-key $PACKAGE

aws --profile personal-develop s3 rm s3://$BUCKET/$PACKAGE
rm $PACKAGE
