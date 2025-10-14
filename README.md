# Service WMTS

| Branch | Status |
|--------|-----------|
| develop | ![Build Status](https://codebuild.eu-central-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiNnlvcWRXS3lyZkY1NHlvTDVhbjQ5c0lvbHJjK3JhQ0FpUVJreGwxZVgzZk9UR1NnK0pIWUkzdkdDak1uKzFsc0kveFNhcFpuYTJmaTZMMFpwdHFWMmY4PSIsIml2UGFyYW1ldGVyU3BlYyI6IkYrS3prZFl1c2RtQ0VPTXAiLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=develop) |
| master | ![Build Status](https://codebuild.eu-central-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiNnlvcWRXS3lyZkY1NHlvTDVhbjQ5c0lvbHJjK3JhQ0FpUVJreGwxZVgzZk9UR1NnK0pIWUkzdkdDak1uKzFsc0kveFNhcFpuYTJmaTZMMFpwdHFWMmY4PSIsIml2UGFyYW1ldGVyU3BlYyI6IkYrS3prZFl1c2RtQ0VPTXAiLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=master) |

## Table of content

- [Table of content](#table-of-content)
- [Summary of the project](#summary-of-the-project)
- [How to run locally](#how-to-run-locally)
  - [dependencies](#dependencies)
  - [Setting up to work](#setting-up-to-work)
  - [Running the server locally](#running-the-server-locally)
  - [Unittesting](#unittesting)
  - [Testing locally](#testing-locally)
  - [Docker helpers](#docker-helpers)
  - [Linting and formatting your work](#linting-and-formatting-your-work)
- [Service configuration](#service-configuration)
  - [General configuration](#general-configuration)
  - [Cache Configuration](#cache-configuration)
  - [WMS configuration](#wms-configuration)
    - [WMS Backend Connection settings](#wms-backend-connection-settings)
  - [S3 2nd level caching settings](#s3-2nd-level-caching-settings)
  - [Get Capabilities settings](#get-capabilities-settings)
- [GetTile](#gettile)
  - [WMTS Config Cache](#wmts-config-cache)
  - [Query Parameters](#query-parameters)
    - [`mode` - Operation Mode](#mode---operation-mode)
      - [default](#default)
      - [preview](#preview)
    - [`nodata`](#nodata)
  - [S3 2nd level caching](#s3-2nd-level-caching)
- [GetCapabilities](#getcapabilities)
- [OpenAPI](#openapi)
  - [Redoc Renderer](#redoc-renderer)
  - [Swagger UI Renderer](#swagger-ui-renderer)
  - [Spec linting](#spec-linting)
- [Updating Packages](#updating-packages)

## Summary of the project

This application translates WMTS requests into WMS requests and optionally caches the responses in S3
(by default this second level caching is disable).
It uses [gatilegrid](https://github.com/geoadmin/lib-gatilegrid) module to perform this translation.
It also serve the WMTS GetCapabilities as defined in the [OGC Standard](https://www.ogc.org/standards/wmts).

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
- **docker-compose-plugin**

installed.

### Setting up to work

First, you'll need to clone the repo

```bash
git clone git@github.com:geoadmin/service-wmts
```

Then, you can run the `setup` target to ensure you have everything needed to develop, test and serve locally

```bash
make setup
```

Then you need to run some local containers (DB, WMS-BOD)

```bash
docker compose up
```

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

### Unittesting

To run the unittest enter:

```bash
make test
```

To run only a single test module/class/method enter:

```bash
pipenv shell # activate the virtual environment
nose2 -c tests/unittest.cfg -t ${PWD} tests.unit_tests.test_functional
```

### Testing locally

To test the localhost server you can use

```bash
curl http://localhost:5000/1.0.0/inline_points/default/current/4326/15/34136/7882.png
```

You can then check with the minio browser that a file has been saved on the S3 cache; http://localhost:9001 (use the credentials from [minio.env](minio.env))

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

All settings can be found in [app/settings.py](app/settings.py) but here below you have the most important one described.

### General configuration

| Variable | Default | Description |
|---|---|---|
| ENV_FILE |  | Configuration environment file. Note that environment variable will overwrite values from environment file. This is especially used for local development |
| WMTS_PORT | `9000` | Port of the service |
| LOGGING_CFG | `./config/logging-cfg-local.yml` | Logging configuration file |
| LOGS_DIR | `./logs` | Logging output directory. Only used by local logging configuration file. |
| DEFAULT_MODE | `default` | Default operation mode see [Operation Mode](#mode---operation-mode) |
| UNITTEST_SKIP_XML_VALIDATION | `False` | Validating Get Capabilities XML output in Unittest takes time (~32s), therefore with this variable you can skip this test. |
| FORWARED_ALLOW_IPS | `*` | Sets the gunicorn `forwarded_allow_ips`. See [Gunicorn Doc](https://docs.gunicorn.org/en/stable/settings.html#forwarded-allow-ips). This setting is required in order to `secure_scheme_headers` to work. |
| FORWARDED_PROTO_HEADER_NAME | `X-Forwarded-Proto` | Sets gunicorn `secure_scheme_headers` parameter to `{${FORWARDED_PROTO_HEADER_NAME}: 'https'}`. This settings is required in order to generate correct URLs in the service responses. See [Gunicorn Doc](https://docs.gunicorn.org/en/stable/settings.html#secure-scheme-headers). |
| SCRIPT_NAME | `''` | If the service is behind a reverse proxy and not served at the root, the route prefix must be set in `SCRIPT_NAME`. |
| WMTS_WORKERS | `0` | WMTS service number of workers. 0 or negative value means that the number of worker are computed from the number of cpu. |
| WSGI_TIMEOUT | `45`| WSGI timeout. |
| SQLALCHEMY_POOL_PRE_PING | False | True will enable the connection pool “pre-ping” feature that tests connections for liveness upon each checkout. This will trigger a recycle of outdated, stale connections. Activating this option will help to get rid of `idle connection timeout` errors but has a slight influence on the performance. |
| SQLALCHEMY_ISOLTATION_LEVEL | `READ COMMITTED` | affects the transaction isolation level of the database connection. |
| SQLALCHEMY_POOL_RECYCLE | 20 | this setting causes the pool to recycle connections after the given number of seconds has passed |
| SQLALCHEMY_POOL_SIZE | 20 |  the number of connections to keep open inside the connection pool |
| SQLALCHEMY_MAX_OVERFLOW | -1 | the number of connections to allow in connection pool “overflow”, -1 will disable overflow. |
| GUNICORN_WORKER_TMP_DIR | `None` | This should be set to an tmpfs file system for better performance. See https://docs.gunicorn.org/en/stable/settings.html#worker-tmp-dir. |
| GUNICORN_KEEPALIVE | `2` | The [`keepalive`](https://docs.gunicorn.org/en/stable/settings.html#keepalive) setting passed to gunicorn. |

### Cache Configuration

NOTE: `max-age` is usually used by the Browser, while `s-maxage` by the server cache (e.g. CloudFront cache, see [CloudFront - Managing how long content stays in the cache (expiration)](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Expiration.html)).

| Variable | Default | Description |
|---|---|---|
| GET_TILE_DEFAULT_CACHE | `'public, max-age={browser_cache_ttl}, s-maxage=5184000'` | Default cache settings for GetTile requests (default to 2 months). `browser_cache_ttl` is set to `GET_TILE_BROWSER_CACHE_MAX_TTL`. Note the `s-maxage` directive is usually overridden by the `cache_ttl` value from BOD. |
| GET_TILE_ERROR_DEFAULT_CACHE | `'public, max-age=3600'` | Default cache settings for GetTile error responses (default to 1 hour). |
| ERROR_5XX_DEFAULT_CACHE | `public, max-age=5` | Default cache settings for 5xx HTTP errors |
| GET_TILE_CACHE_TEMPLATE | `'public, max-age={browser_cache_ttl}, s-maxage={cf_cache_ttl}'` | GetTile `cache-control` header template used with the `cache_ttl` value if present for the layer in the BOD. The `browser_cache_ttl` value will be set `cache_ttl` or to the `GET_TILE_BROWSER_CACHE_MAX_TTL` value if the later is bigger. |
| GET_TILE_BROWSER_CACHE_MAX_TTL | `3600` | Maximum value used for the GetTile Cache-Control max-age header in case of `cache_ttl` configured in BOD. |
| GET_CAP_DEFAULT_CACHE | `'public, max-age=3600, s-maxage=5184000'` | GetCapabilities `cache-control` header value (default to 2 months). |
| CHECKER_DEFAULT_CACHE | `'public, max-age=120'` | Checker `cache-control` header value (default to 2 minutes) |

### WMS configuration

| Variable | Default | Description |
|---|---|---|
| WMS_HOST  | `localhost` | Host name of the WMS service |
| WMS_PORT  | `80`   | Port of the WMS service |
| BOD_DB_HOST | | WMS Postgresql database hostname |
| BOD_DB_PORT | `5432` | WMS Postgresql database port |
| BOD_DB_NAME | | WMS database name |
| BOD_DB_USER | | WMS database user name |
| BOD_DB_PASSWD | | WMS database user password |

#### WMS Backend Connection settings

See https://requests.readthedocs.io/en/latest/api/#requests.adapters.HTTPAdapter for description of
the following variables.

| Variable | Default |
|---|---|
| WMS_BACKEND_POOL_CONNECTION | `10` |
| WMS_BACKEND_POOL_MAXSIZE | `10`|
| WMS_BACKEND_POOL_BLOCK | `False` |
| WMS_BACKEND_CONNECTION_MAX_RETRY | `0` |

### S3 2nd level caching settings

| Variable | Default | Description |
|---|---|---|
| AWS_ACCESS_KEY_ID | | AWS access key for S3 |
| AWS_SECRET_ACCESS_KEY | | AWS access secret for S3 |
| AWS_S3_BUCKET_NAME | `service-wmts-cache` | S3 bucket name used for 2nd level caching |
| AWS_S3_REGION_NAME | | AWS Region |
| AWS_S3_ENDPOINT_URL | | AWS endpoint url if not standard. This allow to use a local S3 instance with minio |
| HTTP_CLIENT_TIMEOUT | `1` | HTTP client timeout in seconds for AWS S3 GetTile requests |

### Get Capabilities settings

| Variable | Default | Description |
|---|---|---|
| APP_STAGING | `'prod'` | Filter the capabilities for this staging |
| LEGENDS_BASE_URL | `"https://api3.geo.admin.ch/static/images/legends"` | Legend base url used in GetCapabilities |

## GetTile

Get Tile endpoint; `/1.0.0/{layer_id}/default/{time}/{srid}/{zoom}/{col}/{row}.{extension}`, returns a Web Map Tile. It uses a WMTS Configuration taken from BOD that is cached upon service starts.

### WMTS Config Cache

For performance reason the WMTS Config needed to return a Web Map Tile, is cached once locally in Memory during the startup of the service. To update this cache, you need to restart the service.

### Query Parameters

#### `mode` - Operation Mode

##### default

`mode=default`

This mode is the default mode for the WMTS service. It is meant to be integrated with the full stack.

The steps are:

1. Check if the tile is present on S3
2. If yes return the S3 tile to the client
3. Otherwise request the tile from the WMS server image
4. If needed puts the tile in S3 after closing the TCP connection with client
5. Return the WMS image to the client

##### preview

`mode=preview`

This mode is meant to be used to test the configuration of the wms server (skipping caching in S3).

The steps are:

1. Request the WMS Server image
2. Return the WMS image to the client

#### `nodata`

No data parameter can be used for tile creation.

`nodata=true`

Returns `OK` if the image was successfully fetched and created. Can be used for tile generation.

Note the Tile will be put into 2nd level S3 cache if needed.

### S3 2nd level caching

Because some tiles are very slow to generates; up to 30 seconds, those ones are also cached into a 2nd level cache on S3. Tiles are saved on S3 based on the BOD configuration; `s3_resolution_max`.
This cache is more deterministic as any other CDN cache (e.g. CloudFront cache).

## GetCapabilities

The following endpoint alias for GetCapabilities are implemented:

- `/EPSG/<int:epsg>/<string:lang>/1.0.0/WMTSCapabilities.xml`
- `/EPSG/<int:epsg>/1.0.0/WMTSCapabilities.xml` (lang=de)
- `/1.0.0/WMTSCapabilities.EPSG.<int:epsg>.xml` (lang=de)
- `/1.0.0/WMTSCapabilities.xml?lang=<string:lang>&epsg=<int:epsg>` (default query: `lan=de&epsg=21781`)

Those endpoints are using the view from the BOD `service-wmts` schema.

## OpenAPI

The service uses [OpenAPI Specification](https://swagger.io/specification/) to document its endpoints. This documentation is
in the [openapi.yml](openapi.yml) file. This file can be used with either Redoc or Swagger UI renderer.

### Redoc Renderer

To render the spec using [Redoc](https://github.com/Redocly/redoc) do as follow

```bash
make serve-spec-redoc
```

Then open `localhost:8080` in your Browser.

### Swagger UI Renderer

To render the spec using [Swagger UI](https://swagger.io/tools/swagger-ui/) do as follow

```bash
make serve-spec-swagger
```

Then open `localhost:8080/swagger` in your Browser.

See also [Swagger UI Installation](https://swagger.io/docs/open-source-tools/swagger-ui/usage/installation/) for more info on the Swagger UI docker image.

### Spec linting

The OpenAPI follow some rules and must be validated using `make lint-spec`

## Updating Packages

All packages used in production are pinned to a major version. Automatically updating these packages
will use the latest minor (or patch) version available. Packages used for development, on the other
hand, are not pinned unless they need to be used with a specific version of a production package
(for example, boto3-stubs for boto3).

To update the packages to the latest minor/compatible versions, run:

```bash
pipenv update --dev
```

To see what major/incompatible releases would be available, run:

```bash
pipenv update --dev --outdated
```

To update packages to a new major release, run:

```bash
pipenv install logging-utilities~=5.0
```
