import logging

import requests
import requests.exceptions

from flask import abort
from flask import request

from app import settings
from app.helpers.utils import get_image_format

logger = logging.getLogger(__name__)

req_session = requests.Session()
req_session.mount('http://', requests.adapters.HTTPAdapter(max_retries=0))


def get_backend(url, **kwargs):
    return req_session.get(url, **kwargs)


def get_wms_params(bbox, gutter, width=256, height=256):
    image_format = get_image_format(request.view_args['extension'])
    return {
        'SERVICE': 'WMS',
        'VERSION': '1.3.0',
        'REQUEST': 'GetMap',
        'FORMAT': f'image/{image_format}',
        'TRANSPARENT': 'true' if image_format == 'png' else 'false',
        'LAYERS': request.view_args["layer_id"],
        'WIDTH': f'{width + gutter * 2}',
        'HEIGHT': f'{height + gutter * 2}',
        'CRS': f'EPSG:{request.view_args["srid"]}',
        'STYLES': '',
        'TIME': request.view_args['time'],
        'BBOX': ','.join([str(b) for b in bbox])
    }


def get_wms_resource(bbox, gutter, width=256, height=256):
    params = get_wms_params(bbox, gutter, width, height)
    logger.info(
        'Fetching wms image: %s?%s',
        settings.WMS_BACKEND,
        '&'.join([f'{k}={v}' for k, v in params.items()])
    )
    return get_wms_image(settings.WMS_BACKEND, params)


def get_wms_image(wms_url, params):
    return get_backend(wms_url, params=params)


def get_wms_backend_readiness():
    try:
        response = get_backend(settings.WMS_BACKEND_READY)
    except (
        requests.exceptions.Timeout,
        requests.exceptions.SSLError,
        requests.exceptions.ConnectionError
    ) as error:
        logger.error(
            'Cannot connect to backend WMS %s: %s',
            settings.WMS_BACKEND_READY,
            error
        )
        abort(502, 'Cannot connect to backend WMS')
    return response.content


def get_wms_tile(bbox, gutter):
    try:
        response = get_wms_resource(bbox, gutter)
        content_type = response.headers.get('Content-Type', 'text/xml')
        logger.debug(
            'WMS response %s; content-type: %s, content: %s',
            response.status_code,
            content_type,
            response.content[:64]
        )
    except requests.exceptions.Timeout as error:
        logger.error(error, exc_info=True)
        abort(408, 'Proxied wms request timed out.')
    except requests.exceptions.SSLError as error:
        logger.error(error, exc_info=True)
        abort(502, 'Unable to verify SSL certificate')
    except requests.exceptions.ConnectionError as error:
        logger.error(error, exc_info=True)
        abort(502, 'Bad Gateway')

    # Detect/Create transparent images
    if 'text/xml' in content_type:
        logger.error(
            'Unable to process the request: '
            'Wms response content type is %s',
            content_type,
            extra={"wms_response": response.text}
        )
        abort(501, f'Unable to process the request: {response.content}')

    return response
