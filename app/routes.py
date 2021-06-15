import logging
import platform

import requests.exceptions

from flask import Response
from flask import abort
from flask import jsonify
from flask import make_response
from flask import request

from app import app
from app import settings
from app.helpers.s3 import put_s3_img
from app.helpers.utils import extend_bbox
from app.helpers.utils import get_image_format
from app.helpers.utils import set_cache_control
from app.helpers.utils import tile_address
from app.helpers.wms import get_wms_backend_root
from app.helpers.wms import prepare_wmts_response
from app.helpers.wmts import get_wmts_path
from app.helpers.wmts import handle_wmts_modes
from app.helpers.wmts import prepare_wmts_cached_response
from app.helpers.wmts import validate_restriction
from app.helpers.wmts import validate_wmts_request
from app.version import APP_VERSION
from app.views import GetCapabilities

logger = logging.getLogger(__name__)


# Log each requests
@app.before_request
def log_route():
    logger.info("%s %s", request.method, request.path)


@app.route('/checker', methods=['GET'])
def check():
    return make_response(
        jsonify({
            'success': True, 'message': 'OK', 'version': APP_VERSION
        })
    )


@app.route('/info.json')
def info_json():
    return make_response(
        jsonify({
            'python_version': platform.python_version(),
            'app_version': APP_VERSION
        })
    )


@app.route('/wms_checker')
def wms_checker():
    # Mapserver only
    wms_ok_string = 'No query information to decode. ' + \
                    'QUERY_STRING is set, but empty.\n'
    try:
        content = get_wms_backend_root()
    except (
        requests.exceptions.Timeout,
        requests.exceptions.SSLError,
        requests.exceptions.ConnectionError
    ) as error:
        logger.error(
            'Cannot connect to backend WMS %s: %s', settings.WMS_BACKEND, error
        )
        abort(502, 'Cannot connect to backend WMS')

    if content.decode('ascii') != wms_ok_string:
        logger.error(
            'Incomprehensible WMS backend %s answer: %s. '
            'WMS is probably not ready yet.',
            settings.WMS_BACKEND,
            content.decode('ascii')
        )
        abort(503, 'Incomprehensible answer. WMS is probably not ready yet.')
    return Response('OK', status=200, mimetype='text/plain')


@app.route(
    '/<string:version>/<string:layer_id>/<string:style_name>/<string:time>/'
    '<int:srid>/<int:zoom>/<int:col>/<int:row>.<string:extension>',
    methods=['GET']
)
def get_tile(
    version, layer_id, style_name, time, srid, zoom, col, row, extension
):
    # pylint: disable=too-many-locals
    mode, gagrid, bbox = validate_wmts_request(
        version, style_name, time, srid, zoom, col, row, extension
    )
    restriction, gutter, write_s3 = validate_restriction(
        layer_id, time, extension, gagrid, zoom, srid
    )
    image_format = get_image_format(extension)

    etag_to_check = request.headers.get('If-None-Match')
    # Determine if the image is returned in the response
    nodata = request.args.get('nodata')

    address = tile_address(gagrid, zoom, col, row)
    wmts_path = get_wmts_path(
        version, layer_id, style_name, time, srid, address, extension
    )

    s3_object = handle_wmts_modes(mode, wmts_path)

    if s3_object:
        logger.debug('Preparing image response from S3...')
        s3_resp, content = s3_object
        status_code, headers = prepare_wmts_cached_response(s3_resp, content)
        set_cache_control(headers, restriction)
    else:
        logger.debug('Returning image from the WMS server')

        shift = gagrid.RESOLUTIONS[zoom] * gutter
        bbox = extend_bbox(bbox, shift)
        if srid == 4326:
            bbox = [bbox[1], bbox[0], bbox[3], bbox[2]]

        status_code, content, headers = prepare_wmts_response(
            bbox, image_format, srid, layer_id, gutter, time
        )
        set_cache_control(headers, restriction)

        ctype_ok = headers.get('Content-Type') in ('image/png', 'image/jpeg')
        if mode != "preview" and ctype_ok and write_s3:
            # cache layer in s3
            if settings.ENABLE_S3_CACHING:
                put_s3_img(content, wmts_path, headers)
            else:
                logger.info('S3 caching is disabled')
        else:
            logger.info('Skipping insert')

        if etag_to_check == headers.get('Etag'):
            content, status_code = ('', 304)

    if nodata == 'true':
        return Response('OK', status=200, mimetype='text/plain')
    return Response(content, headers=headers, status=status_code)


view_get_capabilities = GetCapabilities.as_view('get_capabilities')
app.add_url_rule(
    '/EPSG/<int:epsg>/<string:lang>/<string:version>/WMTSCapabilities.xml',
    view_func=view_get_capabilities
)
app.add_url_rule(
    '/EPSG/<int:epsg>/<string:version>/WMTSCapabilities.xml',
    defaults={'lang': 'de'},
    view_func=view_get_capabilities
)
app.add_url_rule(
    '/<string:version>/WMTSCapabilities.EPSG.<int:epsg>.xml',
    defaults={'lang': 'de'},
    view_func=view_get_capabilities
)
app.add_url_rule(
    '/<string:version>/WMTSCapabilities.xml',
    defaults={
        'epsg': None, 'lang': None
    },
    view_func=view_get_capabilities
)
