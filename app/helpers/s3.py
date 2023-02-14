import hashlib
import http.client
import logging
import socket
from base64 import b64encode
from socket import timeout as socket_timeout
from time import perf_counter

import boto3
import botocore.exceptions
from botocore.client import Config

from app import settings

logger = logging.getLogger(__name__)


def _get_s3_base_path():
    if settings.AWS_S3_ENDPOINT_URL:
        # When working locally with minio as S3, the bucket name must be part
        # of the path.
        return f'/{settings.AWS_S3_BUCKET_NAME}'
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
        config=Config(signature_version='s3v4')
    )


def get_s3_file(wmts_path, etag=None):
    '''Get a file from S3

    Args:
        wmts_path: str
            Path correspond to the S3 key (without leading '/')
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
        path = f"{_get_s3_base_path()}/{wmts_path}"
        logger.debug('Get file from S3: %s%s', settings.AWS_BUCKET_HOST, path)
        http_client = http.client.HTTPConnection(
            settings.AWS_BUCKET_HOST, timeout=settings.HTTP_CLIENT_TIMEOUT
        )
        orig_connect = http.client.HTTPConnection.connect

        def monkey_connect(self):
            orig_connect(self)
            # Set the following socket options
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, 120)
            self.sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL, 120)
            return self

        http_client.connect = monkey_connect(http_client)
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
    except (http.client.HTTPException, socket_timeout) as error:
        logger.error('Failed to get S3 file %s: %s', wmts_path, error)
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


'''
S3 client used by write the Tile on S3.
'''
s3_client = get_s3_client()


def put_s3_file(content, wmts_path, headers):
    '''Put a file on S3 synchronously

    This method upload the file to S3

    Args:
        content: str
            File content
        wmts_path: str
            S3 key to use (usually the wmts path without leading '/')
        headers: dict
            header to set with the S3 object
    '''
    logger.debug('Inserting tile %s in S3', wmts_path)
    md5 = b64encode(hashlib.md5(content).digest()).decode('utf-8')
    try:
        started = perf_counter()
        s3_client.put_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Body=content,
            Key=wmts_path,
            CacheControl=headers.get(
                'Cache-Control', settings.GET_TILE_DEFAULT_CACHE
            ),
            ContentLength=len(content),
            ContentType=headers['Content-Type'],
            ContentMD5=md5
        )
        logger.debug(
            'Written file to S3 in %.2f ms', (perf_counter() - started) * 1000
        )
    except (
        botocore.exceptions.ConnectionError,
        botocore.exceptions.HTTPClientError,
        botocore.exceptions.ChecksumError
    ) as error:
        logger.error(
            'Failed to write file %s on S3: %s',
            wmts_path,
            error,
            exc_info=True
        )
