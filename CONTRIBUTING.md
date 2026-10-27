# Contributing to Kapowarr

This guide describes the contribution process and the expectations for anyone wishing to contribute to Kapowarr. Please read it before starting any work.

## General Process

Contributing to Kapowarr normally follows these steps:

1. Open a [contribution request](https://github.com/Casvt/Kapowarr/issues/new?template=3_contribute_request.yml) describing the change you want to make. This is mandatory and must be approved before you start working on the implementation.
2. Once approved, implement the change locally and test it thoroughly.
3. When the work is ready, open a pull request against the development branch. Include a short summary of the changes and a link to the original contribution request issue.
4. The pull request will be reviewed. Changes may be requested before it is merged.
5. Once the changes have been approved and merged, the contribution is complete.

The contribution request is important. It allows maintainers to assess whether a proposed change is wanted, discuss the intended behaviour and implementation, avoid duplicate work and it offers a place for questions to be asked during development. **Do not skip this step simply because you believe your proposed change would be useful or straightforward.**

### If you have already completed the work

If you have already implemented a change without first opening and obtaining approval for a contribution request, do not open a contribution request retroactively. Open a pull request directly instead. At that point, the implementation already exists, so a separate request to approve work that has already been done serves little purpose. However, this does not mean that the contribution request is optional or that skipping it is an acceptable alternative to following the guidelines. You were expected to read and follow this guide before starting work.

By starting development without an approved contribution request, you accept the risk that your work may be rejected instantly due to problems in the PR that could've been avoided by creating a contribution request.

**If you have not started development yet, there is no exception: open a contribution request and wait for approval first.**

## Local Development

After a contribution request has been accepted, you can start working locally.

There are Python requirements in the requirements.txt and requirements-dev.txt files that you should have installed. You can install them with the following command:

```bash
python3 -m pip install -r requirements.txt -r requirements-dev.txt
```

As for development tools, there are four:
    1. Mypy for type checking, on top of Pylance
    2. autopep8 for formatting
    3. isort for management of import statements
    4. unittest for running the unit tests

You can run the tools with the following commands:

1. **Mypy**:
```bash
mypy --explicit-package-bases .
```
2. **autopep8**:
```bash
autopep8 --recursive --in-place .
```
3. **isort**:
```bash
isort .
```
4. **unittest**
```bash
python3 -m unittest discover -s ./tests -p '*.py'
```

Visual Studio Code is the editor used mostly for this project, but it is not a requirement to use it. A VSC Workspace settings file is included to help with setting up the usage of these tools with integration into VSC, assuming the accompanying extensions of these tools are installed. There is also a .pre-commit-config.yaml file that configures pre-commit hooks, if you have that installed and want to use it. It runs the four tools before a commit.

## Strict Rules

The following rules should always be respected:

1. Kapowarr should support Python 3.8 and newer.
2. The application should remain compatible with Linux, macOS, Windows, and the Docker container.
3. The relevant tests should pass before a change is submitted.
4. Changes should stay focused on the issue or feature being worked on and should not introduce unrelated behaviour changes.

## Styling Guide

The backend styling guide is not enforced as a hard rule in every case, but contributors should try to follow it as much as possible. Running autopep8 and isort usually covers most of the mechanical formatting concerns.

The main conventions are:

1. Indentation is done with 4 spaces. Not using tabs.
2. Use type hints as much as possible. If you encounter an import loop because something needs to be imported for type hinting, utilise [`typing.TYPE_CHECKING`](https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING).
3. Give backend functions docstrings that describe what they do, what inputs they expect, which errors they may raise, and what they return.
4. Keep imports sorted and grouped consistently.
5. Keep lines reasonably short and readable, with the project’s existing style in mind.

## Backend Folder Structure

A useful mental model for the backend is that the code is organized from generic utilities toward higher-level workflows:

1. base: low-level shared utilities, definitions, helpers, file parsing, and exceptions.
2. internals: database access, migrations, settings, server lifecycle, and other internal infrastructure.
3. implementations: concrete integrations and managers such as indexer clients, download clients, naming logic, matching logic, and other domain-specific implementations.
4. features: higher-level workflows that compose the lower-level pieces, such as searching, library import, post-processing, tasks, and mass editing.

In other words, the general flow is base -> internals -> implementations -> features.

## Abbreviations and Terminology

Below is a table with abbreviations commonly used throughout the codebase and
git commit messages:

| Abbreviation | Meaning |
|---|---|
| SV | SpecialVersion |
| VAI | Volume-as-Issue SpecialVersion ("VAS" was erroneously sometimes used) |
| EF(D) | The `file_extraction.extract_filename_data()` function and the data it returns |
| RF | Root folder |
| PP / Post-Processing | Post-download processing |
| LI | Library Import |
| EC | External (download) client |
| SAP | Search Action Planner |
| CF | CloudFlare |
| FS | FlareSolverr |
| CV | ComicVine |
| GC | GetComics |
| PD | Pixeldrain |
| WT | WeTransfer |
| MF | MediaFire |

## Explanations of Various Systems

This section has high-level explanations of various systems in the codebase. 

### Searching System

This subsection covers the search pipeline, starting from a search for downloads for a specific volume or issue and ending at having a list of search results. The searching system consists of three parts:

1. Search Coordinator: In general, the searching system will issue one query per indexer per "iteration". It will then process the search results from those queries and evaluate whether the search needs to continue. It does this based on whether there are any issues left for which there haven't been any search results. If it does need to continue, another iteration is performed where all indexers perform one query. This keeps going until there is a download for each issue, or the system gives up. Keeping track of what issues are covered, and triggering iterations is what the Search Coordinator does. It also holds the indexers, SAPs and query builders.
2. Search Action Planner (SAP): Each iteration, a decision needs to be made on what query is performed. The SAP looks at what query it previously made, how that went (it gets statistics on how the query went from the Search Coordinator), what options for queries it has left and based on that information makes a decision on what the next query should be. It is effectively a state machine, handling volume-phase versus issue-phase searches, title aliases, retries, pagination, and query format variations.
3. Query Builder: The SAP determines what the next query should be (e.g. "next query variation"), but this still needs to be turned into a query string. The Query Builder converts the current search state into a concrete query string for a given download type.

The general flow is:

1. The coordinator starts an iteration.
2. The planner decides whether the next step is a volume search, an issue search, a pagination fetch, a variation change, etc.
3. The query builder turns those decisions into a concrete query.
4. The indexer client executes the query and returns results.
5. The coordinator ranks and filters the results and decides whether to run another iteration.
