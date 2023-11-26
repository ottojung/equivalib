#! /bin/sh

set -e
set -x

pytest -s -v --cov=./src
mypy
pylint ./src/ ./tests/
