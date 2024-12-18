# Morph

## How to Contribute

### Setting up the development environment

This project uses [pre-commit](https://pre-commit.com/) to enforce code quality and consistency. To install the pre-commit hooks, run the following command:

```shell
pre-commit install
```

### Run poetry install

```shell
poetry cache clear --all pypi

poetry update

poetry install --all-extras
```

### Contributing code

You can install your CLI tool locally to test it:

```shell
pip install --editable ‘.[morph-project]’
```

This command installs the package in editable mode, which means changes to the source files will immediately affect the installed package without needing a reinstallation.

## How to Publish

This project uses [poetry](https://python-poetry.org/) to manage dependencies and packaging. To publish a new version of the package, run the following command:

First, update the version in `pyproject.toml` file.

```shell
poetry version patch
git commit -am "Bump version"
git push origin main
```

If you want to update the version of morph-lib, you can do it by editing the template file:

```shell
vim core/morph/task/template/pyproject.toml
git commit -am "Update template file"
git push origin main
```

Publish the package:

```shell
poetry publish --build
```

## How to Install the package

First, create a virtual environment and activate it:

```shell
python -m venv venv
source venv/bin/activate
```

Install the dependencies:

```shell
pip install morph-lib
pip install 'morph-lib[morph-project]'
```

Import the package:

```shell
❯ python
Python 3.11.8 (main, Jun 11 2024, 14:34:56) [Clang 15.0.0 (clang-1500.3.9.4)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>>
>>> from morph import MorphGlobalContext
```
