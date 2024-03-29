import io
import logging
from time import perf_counter

from gatilegrid import getTileGrid
from PIL import Image

from flask import abort
from flask import request

from app import settings
from app.helpers.s3 import put_s3_file
from app.helpers.utils import crop_image
from app.helpers.utils import digest
from app.helpers.utils import extend_bbox
from app.helpers.utils import set_cache_control
from app.helpers.wms import get_wms_tile
from app.helpers.wmts_config import get_wmts_config_by_layer

logger = logging.getLogger(__name__)


def validate_version():
    if request.view_args['version'] != '1.0.0':
        version = request.view_args['version']
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


def prepare_wmts_cached_response(s3_resp):
    headers = dict(s3_resp.getheaders())
    headers['X-Tiles-S3-Cache'] = 'hit'

    return s3_resp.status, headers


def validate_wmts_mode():
    mode = request.args.get('mode', settings.DEFAULT_MODE)
    supported_modes = ('default', 'preview')
    if mode not in supported_modes:
        msg = 'Unsupported mode: %s. Only "%s" are supported.'
        logger.error(msg, mode, ", ".join(supported_modes))
        abort(400, msg % (mode, ", ".join(supported_modes)))
    return mode


def validate_wmts_request():
    validate_version()

    time_value = request.view_args['time']
    if not (time_value.isdigit() or time_value in ('default', 'current')):
        msg = 'Invalid time format: %s. Must be "current", "default" ' \
              'or an integer'
        logger.error(msg, time_value)
        abort(400, msg % (time_value))

    if request.view_args['style_name'] != 'default':
        msg = 'Unsupported style name: %s. Only "default" is supported.'
        logger.error(msg, request.view_args['style_name'])
        abort(400, msg % (request.view_args['style_name']))

    supported_image_formats = ('png', 'jpeg')
    if request.view_args['extension'] not in supported_image_formats:
        msg = 'Unsupported image format: %s. Only "%s" are supported.'
        logger.error(
            msg,
            request.view_args['extension'],
            ", ".join(supported_image_formats)
        )
        abort(
            400,
            msg % (
                request.view_args['extension'],
                ", ".join(supported_image_formats)
            )
        )

    srid = request.view_args['srid']
    col = request.view_args['col']
    row = request.view_args['row']
    if srid == 21781:
        row, col = col, row

    try:
        gagrid = getTileGrid(srid)()
    except AssertionError as error:
        logger.error('Unsupported srid %s: %s', srid, error)
        abort(400, f'Unsupported srid {srid}')

    try:
        bbox = gagrid.tileBounds(request.view_args['zoom'], col, row)
    except AssertionError as error:
        zoom = request.view_args['zoom']
        logger.error(
            'Unsupported zoom level %s for srid %s: %s', zoom, srid, error
        )
        abort(400, f'Unsupported zoom level {zoom} for srid {srid}')

    if not gagrid.intersectsExtent(bbox):
        zoom = request.view_args['zoom']
        logger.error('Tile %d/%d/%d out of bbox %s', zoom, row, col, bbox)
        abort(400, f'Tile out of bounds {zoom}/{row}/{col}')

    return gagrid, bbox


def validate_restriction(gagrid):
    layer_id = request.view_args['layer_id']
    # restriction checks based on bod values / getcap values go here
    restriction = get_wmts_config_by_layer(layer_id)
    write_s3 = None
    if restriction:
        # timestamp
        if request.view_args['time'] not in restriction['timestamps']:
            time_value = request.view_args['time']
            msg = 'Unsupported timestamp %s, ' \
                  'supported timestamps are %s'
            logger.error(msg, time_value, ", ".join(restriction["timestamps"]))
            abort(400, msg % (time_value, ", ".join(restriction["timestamps"])))

        # format/extension
        if request.view_args['extension'] not in restriction['formats']:
            extension = request.view_args['extension']
            msg = 'Unsupported image format %s,' \
                  'supported format is %s'
            logger.error(msg, extension, restriction["formats"])
            abort(400, msg % (extension, restriction["formats"]))

        zoom = request.view_args['zoom']
        resolution = gagrid.getResolution(zoom)
        resolution_max = restriction['resolution_max']
        s3_resolution_max = restriction['s3_resolution_max']
        # convert according to base unit
        if request.view_args['srid'] == 4326:
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
        gutter = int(gutter) if gutter else restriction.get('wms_gutter', 0)
    except ValueError as error:
        logger.error(
            'Invalid gutter value %s: %s. Must be an integer', gutter, error
        )
        abort(400, 'Gutter value must be an integer')

    return restriction, gutter, write_s3


def optimize_image(content, gutter):
    logger.debug('Cropping tile to gutter %d', gutter)
    with Image.open(io.BytesIO(content)) as img:
        img = crop_image(img, gutter)
        out = io.BytesIO()
        img.save(out, format='PNG')
        content = out.getvalue()
    return content


def get_optimized_tile(bbox, gutter):
    start = perf_counter()
    response = get_wms_tile(bbox, gutter)

    # Optimize images if needed
    content = response.content
    content_type = response.headers['Content-Type']
    if (
        response.ok and response.content and content_type == 'image/png' and
        request.view_args['extension'] == 'png' and gutter > 0
    ):
        content = optimize_image(content, gutter)
    tile_generation_time = perf_counter() - start
    return (
        response.status_code,
        content,
        response.headers,
        response.elapsed.total_seconds(),
        tile_generation_time
    )


def prepare_wmts_headers(
    content, headers, wms_time, tile_generation_time, restriction
):
    _headers = {'X-Tiles-S3-Cache': 'miss'}
    _headers['Content-Type'] = headers['Content-Type']
    etag = headers.get('Etag', None)
    if etag is None:
        etag = digest(content)
    _headers['Etag'] = f'"{etag}"'
    _headers['X-WMS-Time'] = wms_time
    _headers['X-Tile-Generation-Time'] = f'{tile_generation_time:.6f}'
    set_cache_control(_headers, restriction)
    return _headers


def handle_2nd_level_cache(write_s3, mode, headers, content):
    on_close = None
    ctype_ok = headers.get('Content-Type') in ('image/png', 'image/jpeg')
    if write_s3 and mode != "preview" and ctype_ok:
        # cache layer in s3
        # add a custom header to track request that performed a write to S3
        # this will be useful for performance tests
        headers['X-Tiles-S3-Cache-Write'] = 'write tile to S3 cache'

        wmts_path = request.path.lstrip('/')

        def on_close_handler():
            put_s3_file(content, wmts_path, headers)

        on_close = on_close_handler
    else:
        logger.debug('Skipping insert')

    return on_close


def prepare_wmts_response(mode, etag):
    gagrid, bbox = validate_wmts_request()
    restriction, gutter, write_s3 = validate_restriction(gagrid)

    shift = gagrid.RESOLUTIONS[request.view_args['zoom']] * gutter
    bbox = extend_bbox(bbox, shift)
    if request.view_args['srid'] == 4326:
        bbox = [bbox[1], bbox[0], bbox[3], bbox[2]]

    (status_code, content, headers, wms_time,
     tile_generation_time) = get_optimized_tile(bbox, gutter)
    headers = prepare_wmts_headers(
        content, headers, wms_time, tile_generation_time, restriction
    )

    on_close = handle_2nd_level_cache(write_s3, mode, headers, content)

    if etag == headers.get('Etag'):
        return 304, None, headers, None

    return status_code, content, headers, on_close
