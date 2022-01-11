import logging
import platform
import time as _time

import requests.exceptions

from flask import Response
from flask import abort
from flask import g
from flask import jsonify
from flask import make_response
from flask import request

from app import app
from app import settings
from app.helpers.s3 import get_s3_file
from app.helpers.wms import get_wms_backend_root
from app.helpers.wmts import prepare_wmts_cached_response
from app.helpers.wmts import prepare_wmts_response
from app.helpers.wmts import validate_wmts_mode
from app.version import APP_VERSION
from app.views import GetCapabilities

logger = logging.getLogger(__name__)


# Log each requests
@app.before_request
def log_request():
    g.setdefault('started', _time.time())
    logger.debug("%s %s", request.method, request.path)


@app.after_request
def log_response(response):
    logger.info(
        "%s %s - %s",
        request.method,
        request.path,
        response.status,
        extra={
            'response': {
                "status_code": response.status_code,
                "headers": dict(response.headers.items())
            },
            "duration": _time.time() - g.get('started', _time.time())
        }
    )
    return response


@app.route('/checker', methods=['GET'])
def check():
    response = make_response(
        jsonify({
            'success': True, 'message': 'OK', 'version': APP_VERSION
        })
    )
    response.headers['Cache-Control'] = settings.CHECKER_DEFAULT_CACHE
    return response


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
    mode = validate_wmts_mode()
    etag = request.headers.get('If-None-Match', None)

    s3_resp = None
    if settings.ENABLE_S3_CACHING and mode != 'preview':
        s3_resp, content = get_s3_file(request.path, etag)

    on_close = None
    if s3_resp:
        logger.debug('Preparing image response from S3...')
        status_code, headers = prepare_wmts_cached_response(s3_resp)
    else:
        logger.debug('Returning image from the WMS server')
        status_code, content, headers, on_close = prepare_wmts_response(
            mode,
            etag
        )

    # Determine if the image is returned in the response
    if request.args.get('nodata', None) == 'true':
        response = Response(
            'OK', status=200, headers=headers, mimetype='text/plain'
        )
    else:
        response = Response(content, headers=headers, status=status_code)

    if on_close:
        response.call_on_close(on_close)
    return response


view_get_capabilities = GetCapabilities.as_view('get_capabilities')
app.add_url_rule(
    '/EPSG/<int:epsg>/<string:lang>/<string:version>/WMTSCapabilities.xml',
    endpoint='get_capabilities_1',
    view_func=view_get_capabilities
)
app.add_url_rule(
    '/EPSG/<int:epsg>/<string:version>/WMTSCapabilities.xml',
    endpoint='get_capabilities_2',
    view_func=view_get_capabilities
)
app.add_url_rule(
    '/<string:version>/WMTSCapabilities.EPSG.<int:epsg>.xml',
    endpoint='get_capabilities_3',
    view_func=view_get_capabilities
)
app.add_url_rule(
    '/<string:version>/WMTSCapabilities.xml',
    endpoint='get_capabilities_4',
    view_func=view_get_capabilities,
)
