import io
import logging

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
req_session.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))


def get_wms_params(
    bbox, image_format, srid, layers, gutter, time, width=256, height=256
):
    return {
        'SERVICE': 'WMS',
        'VERSION': '1.3.0',
        'REQUEST': 'GetMap',
        'FORMAT': 'image/%s' % image_format,
        'TRANSPARENT': 'true' if image_format == 'png' else 'false',
        'LAYERS': layers,
        'WIDTH': '%s' % (width + gutter * 2),
        'HEIGHT': '%s' % (height + gutter * 2),
        'CRS': 'EPSG:%s' % srid,
        'STYLES': '',
        'TIME': time,
        'BBOX': ','.join([str(b) for b in bbox])
    }


def get_wms_resource(
    bbox, image_format, srid, layers, gutter, time, width=256, height=256
):
    params = get_wms_params(
        bbox, image_format, srid, layers, gutter, time, width, height
    )
    logger.info(
        'Fetching: %s?%s',
        settings.WMS_BACKEND,
        '&'.join(['%s=%s' % (k, v) for k, v in params.items()])
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


def prepare_wmts_response(bbox, extension, srid, layer_id, gutter, time):
    try:
        response = get_wms_resource(
            bbox, extension, srid, layer_id, gutter, time
        )
        logger.debug(
            'WMS response %s; content-type: %s, content: %s',
            response.status_code,
            response.headers['Content-Type'],
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
    r_headers = dict(response.headers)
    content_type = r_headers.get('Content-Type', 'text/xml')
    if 'text/xml' in content_type:
        logger.error(
            'Unable to process the request: %s. '
            'Wms response content type is %s',
            response.content,
            content_type
        )
        abort(501, 'Unable to process the request: %s' % response.content)
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
    etag = r_headers.get('Etag', digest(content))
    headers['Etag'] = '"{}"'.format(etag)
    return response.status_code, content, headers
