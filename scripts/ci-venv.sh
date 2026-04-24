#! /bin/sh

set -e
set -x

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

uv sync --all-extras
uv run python -c "import ortools; print(ortools.__version__)"

sh scripts/ci-check.sh
