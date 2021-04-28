SHELL = /bin/bash

.DEFAULT_GOAL := help

SERVICE_NAME := service-wmts

CURRENT_DIR := $(shell pwd)

# general targets timestamps
TIMESTAMPS = .timestamps
VOLUMES_MINIO = .volumes/minio
LOGS_DIR = $(PWD)/logs
REQUIREMENTS_TIMESTAMP = $(TIMESTAMPS)/.requirements.timestamp
DEV_REQUIREMENTS_TIMESTAMP = $(TIMESTAMPS)/.dev-requirements.timestamps

# Docker variables
DOCKER_IMG_LOCAL_TAG = swisstopo/$(SERVICE_NAME):local

# Find all python files that are not inside a hidden directory (directory starting with .)
PYTHON_FILES := $(shell find ./* -type f -name "*.py" -print)

# PIPENV files
PIP_FILE = Pipfile
PIP_FILE_LOCK = Pipfile.lock

# default configuration
WMTS_PORT ?= 9000

# Commands
PIPENV_RUN := pipenv run
PYTHON := $(PIPENV_RUN) python3
PIP := $(PIPENV_RUN) pip3
FLASK := $(PIPENV_RUN) flask
YAPF := $(PIPENV_RUN) yapf
ISORT := $(PIPENV_RUN) isort
NOSE := $(PIPENV_RUN) nose2
PYLINT := $(PIPENV_RUN) pylint

# Docker metadata
GIT_HASH := `git rev-parse HEAD`
GIT_BRANCH := `git symbolic-ref HEAD --short 2>/dev/null`
GIT_DIRTY := `git status --porcelain`
GIT_TAG := `git describe --tags || echo "no version info"`
AUTHOR := $(USER)

all: help


.PHONY: help
help:
	@echo "Usage: make <target>"
	@echo
	@echo "Possible targets:"
	@echo -e " \033[1mSetup TARGETS\033[0m "
	@echo "- setup              Create the python virtual environment and activate it"
	@echo "- dev                Create the python virtual environment with developper tools and activate it"
	@echo "- ci                 Create the python virtual environment and install requirements based on the Pipfile.lock"
	@echo -e " \033[1mFORMATING, LINTING AND TESTING TOOLS TARGETS\033[0m "
	@echo "- format             Format the python source code"
	@echo "- lint               Lint the python source code"
	@echo "- format-lint        Format and lint the python source code"
	@echo "- test               Run the tests"
	@echo -e " \033[1mLOCAL SERVER TARGETS\033[0m "
	@echo "- serve              Run the project using the flask debug server. Port can be set by Env variable WMTS_PORT (default: 5000)"
	@echo "- gunicornserve      Run the project using the gunicorn WSGI server. Port can be set by Env variable DEBUG_WMTS_PORT (default: 5000)"
	@echo -e " \033[1mDocker TARGETS\033[0m "
	@echo "- dockerbuild        Build the project localy (with tag := $(DOCKER_IMG_LOCAL_TAG)) using the gunicorn WSGI server inside a container"
	@echo "- dockerpush         Build and push the project localy (with tag := $(DOCKER_IMG_LOCAL_TAG))"
	@echo "- dockerrun          Run the project using the gunicorn WSGI server inside a container (exposed port: 5000)"
	@echo "- shutdown           Stop the aforementioned container"
	@echo -e " \033[1mCLEANING TARGETS\033[0m "
	@echo "- clean              Clean genereated files"
	@echo "- clean_venv         Clean python venv"


# Build targets. Calling setup is all that is needed for the local files to be installed as needed.

.PHONY: dev
dev: $(DEV_REQUIREMENTS_TIMESTAMP)
	docker-compose up -d
	pipenv shell


.PHONY: setup
setup: $(REQUIREMENTS_TIMESTAMP)
	docker-compose up -d
	pipenv shell

.PHONY: ci
ci: $(TIMESTAMPS) $(PIP_FILE) $(PIP_FILE_LOCK)
	# Create virtual env with all packages for development using the Pipfile.lock
	pipenv sync --dev

# linting target, calls upon yapf to make sure your code is easier to read and respects some conventions.

.PHONY: format
format: $(DEV_REQUIREMENTS_TIMESTAMP)
	$(YAPF) -p -i --style .style.yapf $(PYTHON_FILES)
	$(ISORT) $(PYTHON_FILES)



.PHONY: lint
lint: $(DEV_REQUIREMENTS_TIMESTAMP)
	$(PYLINT) $(PYTHON_FILES)


.PHONY: format-lint
format-lint: format lint


# Test target

.PHONY: test
test: $(DEV_REQUIREMENTS_TIMESTAMP)
	$(NOSE) -c tests/unittest.cfg --verbose -s tests/


# Serve targets. Using these will run the application on your local machine. You can either serve with a wsgi front (like it would be within the container), or without.

.PHONY: serve
serve: clean_logs $(REQUIREMENTS_TIMESTAMP) $(LOGS_DIR)
	LOGS_DIR=$(LOGS_DIR) FLASK_APP=$(subst -,_,$(SERVICE_NAME)) FLASK_DEBUG=1 $(FLASK) run --host=0.0.0.0 --port=$(WMTS_PORT)


.PHONY: gunicornserve
gunicornserve: clean_logs $(REQUIREMENTS_TIMESTAMP) $(LOGS_DIR)
	LOGS_DIR=$(LOGS_DIR) $(PYTHON) wsgi.py


# Docker related functions.

.PHONY: dockerbuild
dockerbuild: $(VOLUMES_MINIO)
	docker build \
		--build-arg GIT_HASH="$(GIT_HASH)" \
		--build-arg GIT_BRANCH="$(GIT_BRANCH)" \
		--build-arg GIT_DIRTY="$(GIT_DIRTY)" \
		--build-arg VERSION="$(GIT_TAG)" \
		--build-arg AUTHOR="$(AUTHOR)" -t $(DOCKER_IMG_LOCAL_TAG) .


.PHONY: dockerpush
dockerpush: dockerbuild
	docker push $(DOCKER_IMG_LOCAL_TAG)


.PHONY: dockerrun
dockerrun: clean_logs dockerbuild $(LOGS_DIR)
	LOGS_DIR=/logs docker run \
		-it --rm --net=host \
		--env LOGS_DIR=/logs \
		--mount type=bind,source="$$(pwd)"/logs,target=/logs \
		$(DOCKER_IMG_LOCAL_TAG)


.PHONY: shutdown
shutdown:
	docker-compose down


.PHONY: clean_logs
clean_logs:
	rm -rf $(LOGS_DIR)

.PHONY: clean_venv
clean_venv:
	pipenv --rm


.PHONY: clean
clean: clean_venv
	docker-compose down --rmi local
	@# clean python cache files
	find . -name __pycache__ -type d -print0 | xargs -I {} -0 rm -rf "{}"
	rm -rf $(TIMESTAMPS)
	rm -rf $(LOGS_DIR)


# Actual builds targets with dependencies

$(TIMESTAMPS):
	mkdir -p $(TIMESTAMPS)


$(VOLUMES_MINIO):
	mkdir -p $(VOLUMES_MINIO)


$(LOGS_DIR):
	mkdir -p -m=777 $(LOGS_DIR)


$(REQUIREMENTS_TIMESTAMP): $(TIMESTAMPS) ${VOLUMES_MINIO} $(PIP_FILE) $(PIP_FILE_LOCK)
	pipenv install
	@touch $(REQUIREMENTS_TIMESTAMP)


$(DEV_REQUIREMENTS_TIMESTAMP): $(TIMESTAMPS) ${VOLUMES_MINIO} $(PIP_FILE) $(PIP_FILE_LOCK)
	pipenv install --dev
	@touch $(DEV_REQUIREMENTS_TIMESTAMP)