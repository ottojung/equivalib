#! /bin/sh

set -e
set -x

mypy
pytest -s -v --cov=./src --cov-branch
pylint ./src/ ./tests/
