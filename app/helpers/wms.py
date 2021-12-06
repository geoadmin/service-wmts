import io
import logging
from time import perf_counter

import requests
import requests.exceptions
from PIL import Image

from flask import abort

from app import settings
from app.helpers.utils import crop_image
from app.helpers.utils import digest

logger = logging.getLogger(__name__)

req_session = requests.Session()
req_session.mount('http://', requests.adapters.HTTPAdapter(max_retries=0))
# TODO CLEAN_UP remove the https session which might not be needed if only
# internally served.
req_session.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))


def get_wms_params(
    bbox, image_format, srid, layers, gutter, timestamp, width=256, height=256
):
    return {
        'SERVICE': 'WMS',
        'VERSION': '1.3.0',
        'REQUEST': 'GetMap',
        'FORMAT': f'image/{image_format}',
        'TRANSPARENT': 'true' if image_format == 'png' else 'false',
        'LAYERS': layers,
        'WIDTH': f'{width + gutter * 2}',
        'HEIGHT': f'{height + gutter * 2}',
        'CRS': f'EPSG:{srid}',
        'STYLES': '',
        'TIME': timestamp,
        'BBOX': ','.join([str(b) for b in bbox])
    }


def get_wms_resource(
    bbox, image_format, srid, layers, gutter, timestamp, width=256, height=256
):
    params = get_wms_params(
        bbox, image_format, srid, layers, gutter, timestamp, width, height
    )
    logger.info(
        'Fetching wms image: %s?%s',
        settings.WMS_BACKEND,
        '&'.join([f'{k}={v}' for k, v in params.items()])
    )
    return get_wms_image(settings.WMS_BACKEND, params)


def get_wms_image(wms_url, params):
    my_headers = {'Referer': settings.REFERER_URL}
    return req_session.get(
        wms_url, params=params, headers=my_headers, verify=False
    )


def get_wms_backend_root():
    response = req_session.get(
        settings.WMS_BACKEND,
        headers={'Referer': settings.REFERER_URL},
        verify=False
    )
    return response.content


def prepare_wmts_response(bbox, extension, srid, layer_id, gutter, timestamp):
    try:
        start = perf_counter()
        response = get_wms_resource(
            bbox, extension, srid, layer_id, gutter, timestamp
        )
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

    # Optimize images
    # Detect/Create transparent images
    if 'text/xml' in content_type:
        logger.error(
            'Unable to process the request: '
            'Wms response content type is %s',
            content_type,
            extra={"wms_response": response.text}
        )
        abort(501, f'Unable to process the request: {response.content}')
    headers = {}
    content = response.content
    if (
        response.ok and response.content and content_type == 'image/png' and
        extension == 'png' and gutter > 0
    ):
        with Image.open(io.BytesIO(content)) as img:
            img = crop_image(img, gutter)
            out = io.BytesIO()
            img.save(out, format='PNG')
            content = out.getvalue()
    headers['Content-Type'] = content_type
    etag = response.headers.get('Etag', digest(content))
    headers['Etag'] = f'"{etag}"'
    headers['X-WMS-Time'] = response.elapsed.total_seconds()
    headers['X-Tile-Generation-Time'] = f'{perf_counter() - start:.6f}'
    return response.status_code, content, headers
