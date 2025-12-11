# Contributing to Confit

We welcome contributions ! There are many ways to help. For example, you can:

1. Help us track bugs by filing issues
2. Suggest and help prioritise new functionalities
3. Help us make the library as straightforward as possible, by simply asking questions on whatever does not seem clear to you.

## Development installation

To be able to run the test suite and develop your own pipeline, you should clone the repo and install it locally. You will need to have [uv](https://docs.astral.sh/uv/) installed.

```bash { data-md-color-scheme="slate" }
# Clone the repository and change directory
git clone ssh://git@github.com/aphp/confit.git

cd confit

# Install the library with its dev dependencies
uv sync --group dev --group docs

# Activate the virtual environment
source .venv/bin/activate
```

To make sure the pipeline will not fail because of formatting errors, we added pre-commit hooks using the `pre-commit` Python library. To use it, simply install it:

```bash { data-md-color-scheme="slate" }
pre-commit install
```

The pre-commit hooks defined in the [configuration](https://github.com/aphp/confit/blob/master/.pre-commit-config.yaml) will automatically run when you commit your changes, letting you know if something went wrong.

The hooks only run on staged changes. To force-run it on all files, run:

```bash { data-md-color-scheme="slate" }
uv run pre-commit run --all-files
```

## Proposing a merge request

Ideally, your changes should :

- Be well-documented
- Pass every tests, and preferably implement their own
- Follow the style guide.

### Testing your code

We use the Pytest test suite.

The following command will run the test suite. Writing your own tests is encouraged !

```bash { data-md-color-scheme="slate" }
uv run pytest
```

Should your contribution propose a bug fix, we require the bug be thoroughly tested.

### Style Guide

We use [Ruff](https://github.com/charliermarsh/ruff) to reformat the code.

Moreover, the CI/CD pipeline enforces a number of checks on the "quality" of the code. To wit, non ruff-formatted code will make the test pipeline fail. We use `pre-commit` to keep our codebase clean.

Refer to the [development install tutorial](#development-installation) for tips on how to format your files automatically.
Most modern editors propose extensions that will format files on save.

### Documentation

Make sure to document your improvements, both within the code with comprehensive docstrings,
as well as in the documentation itself if need be.

We use `MkDocs` for Confit's documentation. You can checkout the changes you make with:

```bash { data-md-color-scheme="slate" }
uv run mkdocs serve
```

Go to [`localhost:8000`](http://localhost:8000) to see your changes. MkDocs watches for changes in the documentation folder
and automatically reloads the page.
