# TODO CLEAN_UP: remove it if S3 cache is not needed anymore
import http.client
import logging
from time import perf_counter

import boto3
from botocore.client import Config
import botocore.exceptions
from celery.utils.log import get_task_logger

from app import celery
from app import settings

logger = logging.getLogger(__name__)
task_logger = get_task_logger(__name__)


def _get_s3_base_path():
    if settings.AWS_S3_ENDPOINT_URL:
        # When working locally with minio as S3, the bucket name must be part
        # of the path.
        return f'{settings.AWS_S3_BUCKET_NAME}/'
    return ''


def get_s3_client():
    '''Return a S3 client

    NOTE: Authentication is done via the following environment variables:
        - AWS_ACCESS_KEY_ID
        - AWS_SECRET_ACCESS_KEY
    '''
    return boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(signature_version='s3')
    )


def get_s3_file(wmts_path, etag=None):
    '''Get a file from S3

    Args:
        wmts_path: str
            Path correspond to the S3 key
        etag: str | None
            ETag to pass as If-None-Match header

    Returns:
        S3 object or None if the file is not found or any other errors happened
    '''
    http_client = None
    response = None
    headers = {}
    if etag:
        headers['If-None-Match'] = etag

    try:
        path = f"/{_get_s3_base_path()}{wmts_path}"
        logger.debug('Get file from S3: %s/%s', settings.AWS_BUCKET_HOST, path)
        http_client = http.client.HTTPConnection(
            settings.AWS_BUCKET_HOST, timeout=0.5
        )
        http_client.request("GET", path, headers=headers)
        response = http_client.getresponse()
        if response.status in (200, 304):
            logger.debug('File %s found on S3', wmts_path)
            return response, response.read()
        if response.status in (404, 403):
            # Note depending on S3 configuration, it might return a 403 when an
            # object is not found. Also in this case we don't read the content
            # as we don't need it.
            logger.debug(
                'S3 file %s not found: status_code=%d %s',
                wmts_path,
                response.status,
                response.reason
            )
            return None, None
    except http.client.HTTPException as error:
        logger.error(
            'Failed to get S3 file %s: %s', wmts_path, error, exc_info=True
        )
        return None, None
    finally:
        if http_client:
            http_client.close()
    logger.error(
        'Failed to get S3 file %s: status_code=%d %s, headers=%s, body=%s',
        wmts_path,
        response.status,
        response.reason,
        response.getheaders(),
        response.read()
    )
    return None, None


def put_s3_file_async(content, wmts_path, headers):
    '''Put a file on S3 asynchronously

    This method returns directly an the file is uploaded to S3 in an
    asyncrhone Celery task

    Args:
        content: str
            File content
        wmts_path: str
            S3 key to use (usually the wmts path)
        headers: dict
            header to set with the S3 object
    '''
    logger.debug('Inserting tile %s in S3 asynchronously', wmts_path)
    started = perf_counter()
    put_s3_file_async_task.apply_async(
        args=[
            wmts_path,
            content,
            headers.get('Cache-Control', settings.GET_TILE_DEFAULT_CACHE),
            headers['Content-Type']
        ]
    )
    logger.debug(
        'Put tile async task in %.2f ms', (perf_counter() - started) * 1000
    )


def put_s3_file(content, wmts_path, headers):
    '''Put a file on S3 synchronously

    This method upload the file to S3

    Args:
        content: str
            File content
        wmts_path: str
            S3 key to use (usually the wmts path)
        headers: dict
            header to set with the S3 object
    '''
    logger.debug('Inserting tile %s in S3 synchronously', wmts_path)
    started = perf_counter()
    _write_to_s3(
        logger,
        wmts_path,
        content,
        headers.get('Cache-Control', settings.GET_TILE_DEFAULT_CACHE),
        headers['Content-Type']
    )
    logger.debug(
        'Put tile sync task in %.2f ms', (perf_counter() - started) * 1000
    )


def _write_to_s3(
    _logger, key, content, cache_control, content_type, raise_error=False
):
    try:
        started = perf_counter()
        s3_client.put_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Body=content,
            Key=key,
            CacheControl=cache_control,
            ContentLength=len(content),
            ContentType=content_type
        )
        _logger.debug(
            'Written file to S3 in %.2f ms', (perf_counter() - started) * 1000
        )
    except (
        botocore.exceptions.ConnectionError,
        botocore.exceptions.HTTPClientError
    ) as error:
        _logger.error(
            'Failed to write file %s on S3: %s', key, error, exc_info=True
        )
        if raise_error:
            raise error


'''
S3 client used by the async task.
'''
s3_client = get_s3_client()


@celery.task()
def put_s3_file_async_task(wmts_path, content, cache_control, content_type):
    task_logger.info(
        'Adding tile %s to S3 with Cache-control="%s" and Content-Type="%s"',
        wmts_path,
        cache_control,
        content_type
    )
    try:
        _write_to_s3(
            task_logger,
            wmts_path,
            content,
            cache_control,
            content_type,
            raise_error=True
        )
    except BaseException as error:
        task_logger.critical(
            'Failed to save tile %s on S3: %s', wmts_path, error, exc_info=True
        )
        raise error
