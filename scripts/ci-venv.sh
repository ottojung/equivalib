#! /bin/sh

set -e
set -x

python3 -m venv venv

. venv/bin/activate
pip3 install .[dev,test]

pytest -v --cov=./src
mypy
pylint ./src/ ./tests/
