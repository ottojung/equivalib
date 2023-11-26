#! /bin/sh

set -e

set -x
python3 -m venv venv

set +x
. venv/bin/activate
set -x

pip3 install .[dev,test]

sh scripts/ci-check.sh
