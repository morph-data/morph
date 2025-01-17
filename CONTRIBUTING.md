# Contributing to Morph

Thank you for your interest in helping Morph! ❤️

🔍 If you're looking for Morph's documentation, you can find it [here](https://docs.morph-data.io).

This guide is for people who want to contribute code to Morph. There are also other ways to contribute, such as [reporting bugs](https://github.com/morph-data/morph/issues/new/choose), creating [feature requests](https://github.com/morph-data/morph/issues/new/choose), helping other users [in our discussion board](https://github.com/morph-data/morph/discussions/new), Stack Overflow, etc., or just being an awesome member of the community!

## Contents

- [Report an Issue](#report-an-issue)
- [Request a Feature](#request-a-feature)
- [Contribute Code](#contribute-code)
- [Branch Types](#branch-types)

## Report an Issue

Open issues for bugs, docs improvements or errors.

[Create an issue here](https://github.com/morph-data/morph/issues/new/choose)

### Private information

If your problem relates to sensitive or private information, please don't post any of your data in an issue. We suggest creating a small test dataset that can reproduce the problem without revealing any private info, and posting that data in the issue. If that's not possible, please reach out to morph@queue-inc.com.

## Request a Feature

To request a feature, a new data source, or ask for help, create a GitHub discussion.

[Create a discussion here](https://github.com/morph-data/morph/discussions/new)

## Contribute Code

### Getting Started

#### Prerequisites

- Python v3.9.0+
- Node.js v18+

#### Setting up a python environment

Morph uses [Poetry](https://python-poetry.org/) for Python dependency management.
In the root of the repository, run the following command to install the dependencies for the Python code.

```
poetry install
```

#### Test the code before committing

`pre-commit` takes care of running all code-checks for formatting and linting. By the following command, `pre-commit` will be installed and ensure your changes are formatted and linted automatically when you commit your changes.

```
pre-commit install
```

### Running the code locally

Run the following command to install the package in editable mode so you can make changes to the code and test them immediately.

```
pip install --editable .'[morph-data]'
```

### Pull Requests

Pull requests are welcome! We review pull requests as they are submitted and will reach out to you with any questions or comments.

Follow these steps to submit a pull request for your changes:

1. Create a fork of the morph repo
2. Before committing your changes, please run `pre-commit install` to automatically format your code and help prevent linting errors.
3. Commit your changes to your fork
4. Test your changes to make sure all results are as expected
5. Open a pull request againt the develop branch of the morph repo

## Branch Types

This project follows a **GitFlow-inspired** branching model adapted to accommodate **weekly patch releases** and **monthly minor releases**. **All new branches are created by the maintainers.**

- **Weekly patch releases (patch)**: Small, frequent updates to fix critical bugs or minor issues.
- **Monthly minor releases (minor)**: Bundles of new features and improvements.

Our adaptions to GitFlow:

- **`develop`** holds the code for the **next monthly minor release**.
- **Weekly patch** branches (e.g., `release/v0.0.x`) are branched off from **`main`** to quickly address bugs.
- **Release** branches for the monthly minor (e.g., `release/v0.1.0`) are branched off **`develop`** when we finalize which features/fixes go into that release. By the time it merges into `main`, the release branch should be tested and ready to be released.

### 1. Main (or Master)

- **Contains**: The production-ready code of the latest official release.
- **Weekly patches** (urgent bug fixes) branch off here.
- **Merged into**: When a release (patch or minor) is finalized, it merges back into `main` with an associated tag.

### 2. Develop

- **Contains**: The next monthly minor release in active development.
- **Merged into**: Feature branches get merged back into `develop`.
- **Branched from**: A release branch (e.g., `release/v0.1.0`) is created from `develop` when we’re ready for final QA and testing.

### 3. Release Branches

We have two kinds of release branches:

1. **Monthly Minor Release**
   - Named like `release/v0.1.0`.
   - Created from `develop`.
   - Final testing/bugfixes happen here.
   - Once ready, merged into `main` (release goes live), then back into `develop`.
   - If you find any bugs during testing, please create a new PR to merge into release branch to fix the bug.

2. **Weekly Patch Release**
   - Named like `release/v0.0.x`.
   - Created from `main`.
   - Used to quickly fix bugs in the currently released version.
   - Once merged into `main`, also merged into `develop` to ensure the patch carries forward.

### 4. Working Branches

These branches are where developers actually write and commit their changes. **All of them branch off from `develop` or `release/<version>`**, and once the work is complete, they are merged back into them via pull requests. Each branch type automatically triggers the creation of release notes from the PR, so **please adhere to these naming conventions**:

1. **`feature/<name>`**
   - **Purpose**: Introduce a completely new functionality or a significant feature.
   - **Examples**: `feature/user-auth`, `feature/payment-integration`.

2. **`fix/<name>`**
   - **Purpose**: Resolve bugs or errors discovered in the codebase.
   - **Examples**: `fix/login-crash`, `fix/cart-update-error`.

3. **`enhancement/<name>`**
   - **Purpose**: Improve or extend existing functionality without introducing entirely new features.
   - **Examples**: `enhancement/profile-page-ui`, `enhancement/api-responses`.

4. **`optimization/<name>`**
   - **Purpose**: Improve performance, memory usage, or efficiency of existing code without changing functionality.
   - **Examples**: `optimization/query-speed`, `optimization/asset-loading`.

5. **`refactor/<name>`**
   - **Purpose**: Restructure or reorganize code (improving readability, maintainability, etc.) without changing external behavior.
   - **Examples**: `refactor/order-service`, `refactor/database-layer`.

6. **`chore/<name>`**
   - **Purpose**: Maintenance tasks, project cleanup, and changes that do not impact the code’s behavior (e.g., updating dependencies, adjusting configurations).
   - **Examples**: `chore/dependency-updates`, `chore/ci-setup`.

## Join Our Team

If you're passionate about what we're building at Morph and want to join our team, reach out to us at morph@queue-inc.com.
