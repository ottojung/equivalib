
[![Build Status](https://ci.codeberg.org/api/badges/12810/status.svg)](https://codeberg.org/otto/equivalib)
[![Code coverage](https://codecov.io/gh/ottojung/equivalib/graph/badge.svg?token=ZN8KJRF40O)](https://codecov.io/gh/ottojung/equivalib)

# Equivalib

This is a Python library that provides testers and developers with a
systematic approach to generate problem instances. The library
facilitates the creation of test inputs based on defined equivalence
classes, which is an essential technique in equivalence partitioning
within software testing. This tool is designed to support the complex
task of identifying and delineating equivalence classes and their
corresponding test cases in a rigorous yet intuitive manner.

The current core generation engine is specified in [docs/spec1.md](docs/spec1.md).

## Setup

`ortools` is a required runtime dependency (including for test execution).
Set up a project environment with all extras installed:

```bash
uv sync --all-extras
uv run python -c "import ortools; print(ortools.__version__)"
```

Run checks:

```bash
uv run mypy src/equivalib tests
uv run ruff check src tests
uv run pytest -v
```

# Licensing

The distribution of Equivalib falls under the GNU General Public
License v3 (GPLv3). For details regarding licensing, users should
refer to the [COPYING](COPYING) file that accompanies the source code.
