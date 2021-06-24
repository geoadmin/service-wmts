# Service WMTS

| Branch | Status |
|--------|-----------|
| develop | ![Build Status](<codebuild-badge>) |
| master | ![Build Status](<codebuild-badge>) |

## Table of content

- [Table of content](#table-of-content)
- [Summary of the project](#summary-of-the-project)
- [How to run locally](#how-to-run-locally)
  - [dependencies](#dependencies)
  - [Setting up to work](#setting-up-to-work)
  - [Running the server locally](#running-the-server-locally)
  - [Docker helpers](#docker-helpers)
  - [Linting and formatting your work](#linting-and-formatting-your-work)
- [Service configuration](#service-configuration)
  - [General configuration](#general-configuration)
  - [WMS configuration](#wms-configuration)
  - [S3 2nd level caching settings](#s3-2nd-level-caching-settings)
- [Query Parameters](#query-parameters)
  - [`mode` - Operation Mode](#mode---operation-mode)
    - [default](#default)
    - [debug](#debug)
  - [preview](#preview)
  - [`nodata`](#nodata)
    - [true](#true)
- [S3 2nd level caching](#s3-2nd-level-caching)

## Summary of the project

This application translates WMTS requests into WMS requests and optionally caches the responses in S3
(by default this second level caching is disable).
It uses [gatilegrid](https://github.com/geoadmin/lib-gatilegrid) module to perform this translation.

## How to run locally

### dependencies

The **Make** targets assume you have

- **bash**
- **python3.7**
- **python3.7-venv**
- **python3.7-dev**
- **pipenv**
- **gcc**
- **libpq-dev**
- **curl**
- **docker**
- **docker-compose**
  
installed.

### Setting up to work

First, you'll need to clone the repo

```bash
git clone git@github.com:geoadmin/service-wmts
```

Then, you can run the dev target to ensure you have everything needed to develop, test and serve locally

```bash
make dev
```

Then you need to run some local containers (DB, WMS-BOD)

```bash
docker-compose up
```

If you want to enable and test the S3 2nd level caching (`ENABLE_S3_CACHING=1`) you need instead
to run:

```bash
docker-compose -f docker-compose-celery.yml up --build
```

*NOTE: the `--build` argument is to make sure that the Celery container gets rebuild with your code.
Each time that you changes code related to the async tasks, then the containers needs to be restarted respectively rebuilt.*

That's it, you're ready to work.

### Running the server locally

To run locally enter

```bash
make serve
```

or the following to use gunicorn as web server:

```bash
make gunicornserve
```

or the following to run the service in a docker image locally:

```bash
make dockerrun
```

### Docker helpers

To build a local docker image tagged as `service-wmts:local-${USER}-${GIT_HASH_SHORT}` you can
use

```bash
make dockerbuild
```

To push the image on the ECR repository use the following two commands

```bash
make dockerlogin
make dockerpush
```

### Linting and formatting your work

In order to have a consistent code style the code should be formatted using `yapf`. Also to avoid syntax errors and non
pythonic idioms code, the project uses the `pylint` linter. Both formatting and linter can be manually run using the
following command:

```bash
make format-lint
```

The openapi spec has also a linter, and the CI will check for spec errors.

```bash
make lint-spec
```

**Formatting and linting should be at best integrated inside the IDE, for this look at
[Integrate yapf and pylint into IDE](https://github.com/geoadmin/doc-guidelines/blob/master/PYTHON.md#yapf-and-pylint-ide-integration)**

*NOTE: CI will failed if the code is not properly formatted*

## Service configuration

### General configuration

| Variable | Default | Description |
|---|---|---|
| ENV_FILE |  | Configuration environment file. Note that environment variable will overwrite values from environment file. |
| WMTS_PORT | `9000` | Port of the service |
| LOGGING_CFG | `./config/logging-cfg-local.yml` | Logging configuration file |
| LOGS_DIR | `./logs` | Logging output directory. Only used by local logging configuration file. |
| DEFAULT_MODE | `default` | Default operation mode see [Operation Mode](#mode---operation-mode) |
| UNITTEST_SKIP_XML_VALIDATION | `False` | Validating Get Capabilities XML output in Unittest takes time (~32s), therefore with this variable you can skip this test. |

### WMS configuration

| Variable | Default | Description |
|---|---|---|
| WMS_HOST  | `localhost` | Host name of the WMS service |
| WMS_PORT  | `80`   | Port of the WMS service |
| REFERER_URL | `https://proxywms.geo.admin.ch` | Referer header to use with the WMS backend |
| BOD_DB_HOST | | WMS Postgresql database hostname |
| BOD_DB_PORT | `5432` | WMS Postgresql database port |
| BOD_DB_NAME | | WMS database name |
| BOD_DB_USER | | WMS database user name |
| BOD_DB_PASSWD | | WMS database user password |

### S3 2nd level caching settings

| Variable | Default | Description |
|---|---|---|
| ENABLE_S3_CACHING | `0` | Enable S3 2nd level caching |
| RABBITMQ_PORT | `localhost` | Rabbitmq host name used by Celery for async level tasks |
| RABBITMQ_PORT | `5672` | Rabbitmq host name used by Celery for async level tasks |
| AWS_ACCESS_KEY_ID | | AWS access key for S3 |
| AWS_SECRET_ACCESS_KEY | | AWS access secret for S3 |
| AWS_S3_BUCKET_NAME | | S3 bucket name used for 2nd level caching |
| AWS_S3_REGION_NAME | | AWS Region |
| AWS_S3_ENDPOINT_URL | | AWS endpoint url if not standard. This allow to use a local S3 instance with minio |

## Query Parameters

### `mode` - Operation Mode

#### default

`mode=default`

This mode is the default mode for the WMS proxy. It is meant to be integrated with the full stack.

The steps are:

1. Request the WMS server image
2. Puts the image in S3 in the background (Only if `ENABLE_S3_CACHING=1`)
3. Return the WMS image to the client

#### debug

`mode=debug`

This mode should be used when debugging the app (requires `ENABLE_S3_CACHING=1`).

The steps are:

1. Check if the image has already been created in S3
2. Return the image from S3

If the image doesn't exist it follows the `default` mode.

### preview

`mode=preview`

This mode is meant to be used to test the configuration of the wms server.

The steps are:

1. Request the WMS Server image
2. Return the WMS image to the client

### `nodata`

No data parameter can be used for tile creation.

#### true

`nodata=true`

Returns `OK` if the image was successfully fetched and created. Can be used for tile generation.

## S3 2nd level caching

On the old infrastructure in AWS Ireland, we had a second level caching done by S3, where each request
where cached by the service in a S3 bucket and then Varnish was first checking the 2nd level cache on S3 before
redirecting the request to the service. This was done because the CloudFront cache rate was quite low and we 
needed a better caching to improve performance.

This should not be needed anymore with the new infrastructure in AWS Frankfurt. However the whole logic has
been migrated just in case this is needed to further improved performance.
