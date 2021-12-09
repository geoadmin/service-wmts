# TODO CLEAN_UP: remove it if S3 cache is not needed anymore
import http
import logging
from datetime import datetime

import boto3
from botocore.client import Config
from celery.utils.log import get_task_logger

from app import celery
from app import settings
from app.helpers.utils import is_still_valid_tile

logger = logging.getLogger(__name__)
task_logger = get_task_logger(__name__)


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


def get_s3_img(wmts_path, check_expiration=False):
    '''Get an image from S3

    Args:
        wmts_path: str
            WMTS path correspond to the S3 key
        check_expiration: bool
            Check image cache expiration

    Returns:
        Image or None if the image is expired or not found
    '''
    http_client = None
    response = None
    content = None
    logger.debug('Get tile %s from S3', wmts_path)
    try:
        http_client = http.client.HTTPConnection(settings.AWS_BUCKET_HOST)
        http_client.request("GET", "/" + wmts_path)
        response = http_client.getresponse()
        if int(response.status) in (200, 304):
            content = response.read()
            h_exp = response.getheader('x-amz-expiration')
            if check_expiration and h_exp is not None:
                if not is_still_valid_tile(h_exp, datetime.now()):
                    logger.info(
                        'Tile %s on S3 has expired on %s !', wmts_path, h_exp
                    )
                    return None
        else:
            logger.debug('No tile %s on S3 found', wmts_path)
            return None
    except http.client.HTTPException as error:
        logger.error(
            'Failed to retrieved tile %s from S3: %s',
            wmts_path,
            error,
            exc_info=True
        )
        return None
    finally:
        if http_client:
            http_client.close()
    return (response, content)


def put_s3_img(content, wmts_path, headers):
    logger.debug('Inserting tile %s in S3 asynchronously', wmts_path)
    put_s3_img_async.apply_async(
        args=[
            wmts_path,
            content,
            headers.get('Cache-Control', settings.GET_TILE_DEFAULT_CACHE),
            headers.get('Content-Type', '')
        ]
    )


'''
S3 client used by the async task.
'''
s3_client = get_s3_client()


@celery.task(ignore_result=True)
def put_s3_img_async(wmts_path, content, cache_control, content_type):
    task_logger.info(
        'Adding tile %s to S3 with Cache-control="%s" and Content-Type="%s"',
        wmts_path
    )
    try:
        s3_client.put_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Body=content,
            Key=wmts_path,
            CacheControl=cache_control,
            ContentLength=len(content),
            ContentType=content_type
        )
    except BaseException as error:
        task_logger.critical(
            'Failed to save tile %s on S3: %s', wmts_path, error, exc_info=True
        )
        raise
