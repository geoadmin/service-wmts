# Service WMTS

| Branch | Status |
|--------|-----------|
| develop | ![Build Status](<codebuild-badge>) |
| master | ![Build Status](<codebuild-badge>) |

## Summary of the project

A simple description of the service should go here

## How to run locally

### dependencies

The **Make** targets assume you have **bash**, **curl**, **tar**, **docker** and **docker-compose** installed.

### Setting up to work

First, you'll need to clone the repo

    git clone git@github.com:geoadmin/service-wmts

Then, you can run the dev target to ensure you have everything needed to develop, test and serve locally

    make dev

That's it, you're ready to work.

### Linting and formatting your work

In order to have a consistent code style the code should be formatted using `yapf`. Also to avoid syntax errors and non
pythonic idioms code, the project uses the `pylint` linter. Both formatting and linter can be manually run using the
following command:

    make format-lint

**Formatting and linting should be at best integrated inside the IDE, for this look at
[Integrate yapf and pylint into IDE](https://github.com/geoadmin/doc-guidelines/blob/master/PYTHON.md#yapf-and-pylint-ide-integration)**
