# This file contains all application settings
import os
from distutils.util import strtobool
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent
ENV_FILE = os.getenv('ENV_FILE', f'{BASE_DIR}/.env.local')
if ENV_FILE and Path(ENV_FILE).exists():
    from dotenv import load_dotenv

    print(f"Running locally hence injecting env vars from {ENV_FILE}")
    load_dotenv(ENV_FILE, override=True, verbose=True)

# General settings
# Loggings settings are directly imported in their module
# LOGGING_CFG = os.getenv('LOGGING_CFG')
# LOGS_DIR = os.getenv('LOGS_DIR')
TRAP_HTTP_EXCEPTIONS = True
WMTS_PORT = str(os.environ.get('WMTS_PORT', "9000"))
FORWARED_ALLOW_IPS = os.getenv('FORWARED_ALLOW_IPS', '*')
FORWARDED_PROTO_HEADER_NAME = os.getenv(
    'FORWARDED_PROTO_HEADER_NAME', 'X-Forwarded-Proto'
).upper()
WMTS_WORKERS = int(os.getenv('WORKERS', '0'))
if WMTS_WORKERS <= 0:
    from multiprocessing import cpu_count
    WMTS_WORKERS = (cpu_count() * 2) + 1
WSGI_TIMEOUT = int(os.getenv('WSGI_TIMEOUT', '45'))
APP_STAGING = os.getenv('APP_STAGING', 'prod')
WMS_PORT = os.getenv('WMS_PORT', None)
WMS_HOST = os.getenv('WMS_HOST', 'localhost')
WMS_BACKEND = f'http://{WMS_HOST}{":" + WMS_PORT if WMS_PORT else ""}/mapserv'
BOD_DB_NAME = os.environ['BOD_DB_NAME']
BOD_DB_HOST = os.environ['BOD_DB_HOST']
BOD_DB_PORT = int(os.getenv('BOD_DB_PORT', '5432'))
BOD_DB_USER = os.environ['BOD_DB_USER']
BOD_DB_PASSWD = os.environ['BOD_DB_PASSWD']
BOD_DB_CONNECT_TIMEOUT = int(os.getenv('BOD_DB_CONNECT_TIMEOUT', '10'))
BOD_DB_CONNECT_RETRIES = int(os.getenv('BOD_DB_CONNECT_RETRIES', '3'))

# Cache settings
NO_CACHE = 'public, must-revalidate, proxy-revalidate, max-age=0'
GET_TILE_BROWSER_CACHE_MAX_TTL = int(
    os.getenv('GET_TILE_BROWSER_CACHE_MAX_TTL', '3600')
)
GET_TILE_DEFAULT_CACHE = os.getenv(
    'GET_TILE_DEFAULT_CACHE',
    'public, max-age={browser_cache_ttl}, s-maxage=5184000'
).format(browser_cache_ttl=GET_TILE_BROWSER_CACHE_MAX_TTL)
GET_TILE_ERROR_DEFAULT_CACHE = os.getenv(
    'GET_TILE_DEFAULT_CACHE', 'public, max-age=3600'
)
ERROR_5XX_DEFAULT_CACHE = os.getenv(
    'ERROR_5XX_DEFAULT_CACHE', 'public, max-age=5'
)
GET_TILE_CACHE_TEMPLATE = os.getenv(
    'GET_TILE_CACHE_TEMPLATE',
    'public, max-age={browser_cache_ttl}, s-maxage={cf_cache_ttl}'
)
GET_CAP_DEFAULT_CACHE = os.getenv(
    'GET_CAP_DEFAULT_CACHE', 'public, max-age=3600, s-maxage=5184000'
)
CHECKER_DEFAULT_CACHE = os.getenv(
    'CHECKER_DEFAULT_CACHE', 'public, max-age=120'
)

DEFAULT_MODE = os.getenv('DEFAULT_MODE', 'default')

# AWS Settings
# this endpoint url is only used for local development
AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL', None)
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME')
AWS_S3_BUCKET_NAME = os.getenv('AWS_S3_BUCKET_NAME', 'service-wmts-cache')

AWS_BUCKET_HOST = f'{AWS_S3_BUCKET_NAME}.s3-{AWS_S3_REGION_NAME}.amazonaws.com'
if AWS_S3_ENDPOINT_URL is not None:
    AWS_BUCKET_HOST = urlparse(AWS_S3_ENDPOINT_URL).netloc

# HTTP Client Timeout to access S3 bucket [seconds]
HTTP_CLIENT_TIMEOUT = int(os.getenv('HTTP_CLIENT_TIMEOUT', '1'))

# SQL Alchemy
# pylint: disable=line-too-long
SQLALCHEMY_DATABASE_URI = \
    f"postgresql://{BOD_DB_USER}:{BOD_DB_PASSWD}@{BOD_DB_HOST}:{BOD_DB_PORT}/{BOD_DB_NAME}"

# SQL Alchemy settings
SQLALCHEMY_TRACK_MODIFICATIONS = strtobool(
    os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS', 'False')
)

LEGENDS_BASE_URL = os.getenv(
    "LEGENDS_BASE_URL", "https://api3.geo.admin.ch/static/images/legends"
)

# Unittest configuration
UNITTEST_SKIP_XML_VALIDATION = strtobool(
    os.getenv('UNITTEST_SKIP_XML_VALIDATION', 'False')
)
