# This file contains all application settings
import os
from distutils.util import strtobool
from pathlib import Path

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
APP_STAGING = os.getenv('APP_STAGING', 'prod')
WMTS_PUBLIC_HOST = os.getenv('WMTS_PUBLIC_HOST', 'wmts.geo.admin.ch')
REFERER_URL = os.getenv('PROXYWMS_REFERER_URL', 'https://proxywms.geo.admin.ch')
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
NO_CACHE = 'public, must-revalidate, proxy-revalidate, max-age=0'
DEFAULT_CACHE = 'public, max-age=1800'
DEFAULT_MODE = os.getenv('DEFAULT_MODE', 'default')

# TODO CLEAN_UP: remove S3 second level caching if not needed
ENABLE_S3_CACHING = strtobool(os.getenv('ENABLE_S3_CACHING', 'False'))
# Celery and Rabbitmq settings
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
CELERY_TASK_SERIALIZER = 'pickle'
CELERY_RESULT_SERIALIZER = 'pickle'
CELERY_ACCEPT_CONTENT = ['pickle']

# AWS Settings
# this endpoint url is only used for local development
AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL', None)
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME')
AWS_S3_BUCKET_NAME = os.getenv('AWS_S3_BUCKET_NAME')

AWS_BUCKET_HOST = f'{AWS_S3_BUCKET_NAME}.s3-{AWS_S3_REGION_NAME}.amazonaws.com'
if AWS_S3_ENDPOINT_URL is not None:
    AWS_BUCKET_HOST = AWS_S3_ENDPOINT_URL

# SQL Alchemy
# pylint: disable=line-too-long
SQLALCHEMY_DATABASE_URI = \
    f"postgresql://{BOD_DB_USER}:{BOD_DB_PASSWD}@{BOD_DB_HOST}:{BOD_DB_PORT}/{BOD_DB_NAME}"

# SQL Alchemy settings
SQLALCHEMY_TRACK_MODIFICATIONS = strtobool(
    os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS', 'False')
)

LEGENDS_BASE_URL = "https://api3.geo.admin.ch/static/images/legends"

# Unittest configuration
UNITTEST_SKIP_XML_VALIDATION = strtobool(
    os.getenv('UNITTEST_SKIP_XML_VALIDATION', 'False')
)
