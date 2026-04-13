#! /bin/sh

set -e
set -x

uv run mypy
uv run pytest -s -v --cov=./src --cov-branch
uv run ruff check ./src/ ./tests/
