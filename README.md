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
  - [Unittesting](#unittesting)
  - [Docker helpers](#docker-helpers)
  - [Linting and formatting your work](#linting-and-formatting-your-work)
- [Service configuration](#service-configuration)
  - [General configuration](#general-configuration)
  - [Cache Configuration](#cache-configuration)
  - [WMS configuration](#wms-configuration)
  - [S3 2nd level caching settings](#s3-2nd-level-caching-settings)
  - [Get Capabilities settings](#get-capabilities-settings)
- [GetTile](#gettile)
  - [WMTS Config Cache](#wmts-config-cache)
  - [Query Parameters](#query-parameters)
    - [`mode` - Operation Mode](#mode---operation-mode)
      - [default](#default)
      - [debug](#debug)
      - [preview](#preview)
    - [`nodata`](#nodata)
  - [S3 2nd level caching](#s3-2nd-level-caching)
- [GetCapabilities](#getcapabilities)
- [OpenAPI](#openapi)
  - [Redoc Renderer](#redoc-renderer)
  - [Swagger UI Renderer](#swagger-ui-renderer)
  - [Spec linting](#spec-linting)

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

This mode is the default mode for the WMS proxy. It is meant to be integrated with the full stack.

The steps are:

1. Request the WMS server image
2. Puts the image in S3 in the background (Only if `ENABLE_S3_CACHING=1`)
3. Return the WMS image to the client

##### debug

`mode=debug`

This mode should be used when debugging the app (requires `ENABLE_S3_CACHING=1`).

The steps are:

1. Check if the image has already been created in S3
2. Return the image from S3

If the image doesn't exist it follows the `default` mode.

##### preview

`mode=preview`

This mode is meant to be used to test the configuration of the wms server.

The steps are:

1. Request the WMS Server image
2. Return the WMS image to the client

#### `nodata`

No data parameter can be used for tile creation.

`nodata=true`

Returns `OK` if the image was successfully fetched and created. Can be used for tile generation.

### S3 2nd level caching

On the old infrastructure in AWS Ireland, we had a second level caching done by S3, where each request
where cached by the service in a S3 bucket and then Varnish was first checking the 2nd level cache on S3 before
redirecting the request to the service. This was done because the CloudFront cache rate was quite low and we
needed a better caching to improve performance.

This should not be needed anymore with the new infrastructure in AWS Frankfurt. However the whole logic has
been migrated just in case this is needed to further improved performance.

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
