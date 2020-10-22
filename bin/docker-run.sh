#!/bin/bash

docker run -v "$PWD:/lambda" -it --rm "amazonlinux" bash /lambda/bin/prepare-packages.sh
