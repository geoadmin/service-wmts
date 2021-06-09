import logging

from gatilegrid import getTileGrid

from flask import abort
from flask import request

from app import settings
from app.helpers.s3 import get_s3_img
from app.helpers.wmts_config import get_wmts_config_by_layer

logger = logging.getLogger(__name__)


def get_wmts_path(version, layer_id, stylename, time, srid, address, extension):
    return '%s.%s' % (
        '/'.join([version, layer_id, stylename, time, str(srid), address]),
        extension
    )


def validate_version(version):
    if version != '1.0.0':
        msg = 'Unsupported version: %s. Only "1.0.0" is supported.'
        logger.error(msg, version)
        abort(400, msg % (version))


def validate_epsg(epsg):
    supported_epsg = [21781, 2056, 3857, 4326]
    try:
        getTileGrid(epsg)()
    except AssertionError as error:
        logger.error('Unsupported epsg %s: %s', epsg, error)
        abort(400, f'Unsupported epsg {epsg}, must be on of {supported_epsg}')


def validate_lang(lang):
    languages = ['de', 'fr', 'it', 'rm', 'en']
    if lang not in languages:
        logger.error('Unsupported lang %s', lang)
        abort(400, f'Unsupported lang {lang}, must be on of {languages}')


def prepare_wmts_cached_response(resp, content):
    headers = {}
    headers['Content-Type'] = resp.getheader('content-type')
    c_length = resp.getheader('content-length')
    if not c_length:
        c_length = len(content)
    headers['Content-Length'] = c_length
    c_encoding = resp.getheader('content-encoding')
    if c_encoding:
        headers['Content-Encoding'] = c_encoding

    return '200', headers


def validate_wmts_request(
    version, style_name, time, srid, zoom, col, row, extension
):
    validate_version(version)

    if not (time.isdigit() or time in ('default', 'current')):
        msg = 'Invalid time format: %s. Must be "current", "default" ' \
              'or an integer'
        logger.error(msg, time)
        abort(400, msg % (time))

    if style_name != 'default':
        msg = 'Unsupported style name: %s. Only "default" is supported.'
        logger.error(msg, style_name)
        abort(400, msg % (style_name))

    supported_image_formats = ('png', 'jpeg', 'pngjpeg')
    if extension not in supported_image_formats:
        msg = 'Unsupported image format: %s. Only "%s" are supported.'
        logger.error(msg, extension, ", ".join(supported_image_formats))
        abort(400, msg % (extension, ", ".join(supported_image_formats)))

    mode = request.args.get('mode', settings.DEFAULT_MODE)
    supported_modes = ('default', 'debug', 'preview', 'check_expiration')
    if mode not in supported_modes:
        msg = 'Unsupported mode: %s. Only "%s" are supported.'
        logger.error(msg, mode, ", ".join(supported_modes))
        abort(400, msg % (mode, ", ".join(supported_modes)))

    if srid == 21781:
        row, col = col, row

    try:
        gagrid = getTileGrid(srid)()
    except AssertionError as error:
        logger.error('Unsupported srid %s: %s', srid, error)
        abort(400, f'Unsupported srid {srid}')

    try:
        bbox = gagrid.tileBounds(zoom, col, row)
    except AssertionError as error:
        logger.error(
            'Unsupported zoom level %s for srid %s: %s', zoom, srid, error
        )
        abort(400, f'Unsupported zoom level {zoom} for srid {srid}')

    if not gagrid.intersectsExtent(bbox):
        logger.error('Tile %d/%d/%d out of bbox %s', zoom, row, col, bbox)
        abort(400, f'Tile out of bounds {zoom}/{row}/{col}')

    return mode, gagrid, bbox


def validate_restriction(layer_id, time, extension, gagrid, zoom, srid):
    # wmts_config checks based on bod values / getcap values go here
    wmts_config = get_wmts_config_by_layer(layer_id)
    write_s3 = None
    if wmts_config:
        # timestamp
        if time not in wmts_config.timestamps:
            msg = 'Unsupported timestamp %s, ' \
                  'supported timestamps are %s'
            logger.error(msg, time, ", ".join(wmts_config.timestamps))
            abort(400, msg % (time, ", ".join(wmts_config.timestamps)))

        # format/extension
        if extension not in wmts_config.formats:
            msg = 'Unsupported image format %s,' \
                  'supported format is %s'
            logger.error(msg, extension, wmts_config.formats)
            abort(400, msg % (extension, wmts_config.formats))

        resolution = gagrid.getResolution(zoom)
        resolution_max = wmts_config.resolution_max
        s3_resolution_max = wmts_config.s3_resolution_max
        # convert according to base unit
        if srid == 4326:
            resolution = resolution * gagrid.metersPerUnit
        # max resolution
        if resolution < resolution_max:
            logger.error(
                'Unsupported zoom level %s (resolution: %s), maxzoom is: %s',
                zoom,
                resolution,
                gagrid.getClosestZoom(resolution_max)
            )
            abort(
                400,
                f'Unsupported zoom level {zoom}, '
                f'maxzoom is: {gagrid.getClosestZoom(resolution_max)}'
            )
        # put tiles to s3
        write_s3 = resolution >= s3_resolution_max
    else:
        msg = 'Unsupported Layer %s'
        logger.error(msg, layer_id)
        abort(400, msg % (layer_id))

    try:
        gutter = request.args.get('gutter', 0)
        gutter = int(gutter) if gutter else wmts_config.wms_gutter
    except ValueError as error:
        logger.error(
            'Invalid gutter value %s: %s. Must be an integer', gutter, error
        )
        abort(400, 'Gutter value must be an integer')

    return wmts_config, gutter, write_s3


def handle_wmts_modes(mode, wmts_path):
    s3_object = None

    if mode == 'debug' and settings.ENABLE_S3_CACHING:
        logger.info('Fetching object from S3 %s...', wmts_path)
        s3_object = get_s3_img(wmts_path)
    elif mode == 'debug' and not settings.ENABLE_S3_CACHING:
        logger.error(
            'Debug mode is not available when ENABLE_S3_CACHING is disabled'
        )
    elif mode == 'check_expiration' and settings.ENABLE_S3_CACHING:
        logger.info('checking expiration of S3 object %s...', wmts_path)
        s3_object = get_s3_img(wmts_path, check_expiration=True)
    elif mode == 'check_expiration' and not settings.ENABLE_S3_CACHING:
        logger.error(
            'check_expiration mode is not available when ENABLE_S3_CACHING is '
            'disabled'
        )

    return s3_object
