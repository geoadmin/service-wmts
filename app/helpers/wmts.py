import io
import logging
from time import perf_counter

from gatilegrid import getTileGrid
from PIL import Image

from flask import abort
from flask import request

from app import settings
from app.helpers.s3 import put_s3_file
from app.helpers.s3 import put_s3_file_async
from app.helpers.utils import crop_image
from app.helpers.utils import digest
from app.helpers.utils import extend_bbox
from app.helpers.utils import get_image_format
from app.helpers.utils import set_cache_control
from app.helpers.wms import get_wms_tile
from app.helpers.wmts_config import get_wmts_config_by_layer

logger = logging.getLogger(__name__)


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


def prepare_wmts_cached_response(s3_resp):
    headers = dict(s3_resp.getheaders())
    headers['X-2nd-Cache'] = 'hit'

    return s3_resp.status, headers


def validate_wmts_mode():
    mode = request.args.get('mode', settings.DEFAULT_MODE)
    supported_modes = ('default', 'preview')
    if mode not in supported_modes:
        msg = 'Unsupported mode: %s. Only "%s" are supported.'
        logger.error(msg, mode, ", ".join(supported_modes))
        abort(400, msg % (mode, ", ".join(supported_modes)))
    return mode


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

    return gagrid, bbox


def validate_restriction(layer_id, time, extension, gagrid, zoom, srid):
    # restriction checks based on bod values / getcap values go here
    restriction = get_wmts_config_by_layer(layer_id)
    write_s3 = None
    if restriction:
        # timestamp
        if time not in restriction['timestamps']:
            msg = 'Unsupported timestamp %s, ' \
                  'supported timestamps are %s'
            logger.error(msg, time, ", ".join(restriction["timestamps"]))
            abort(400, msg % (time, ", ".join(restriction["timestamps"])))

        # format/extension
        if extension not in restriction['formats']:
            msg = 'Unsupported image format %s,' \
                  'supported format is %s'
            logger.error(msg, extension, restriction["formats"])
            abort(400, msg % (extension, restriction["formats"]))

        resolution = gagrid.getResolution(zoom)
        resolution_max = restriction['resolution_max']
        s3_resolution_max = restriction['s3_resolution_max']
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
        gutter = int(gutter) if gutter else restriction.get('wms_gutter', 0)
    except ValueError as error:
        logger.error(
            'Invalid gutter value %s: %s. Must be an integer', gutter, error
        )
        abort(400, 'Gutter value must be an integer')

    return restriction, gutter, write_s3


def get_optmize_tile(bbox, extension, srid, layer_id, gutter, timestamp):
    start = perf_counter()
    response = get_wms_tile(bbox, extension, srid, layer_id, gutter, timestamp)
    content_type = response.headers['Content-Type']

    # Optimize images
    content = response.content
    if (
        response.ok and response.content and content_type == 'image/png' and
        extension == 'png' and gutter > 0
    ):
        logger.debug('Cropping tile to gutter %d', gutter)
        with Image.open(io.BytesIO(content)) as img:
            img = crop_image(img, gutter)
            out = io.BytesIO()
            img.save(out, format='PNG')
            content = out.getvalue()
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
    _headers = {'X-2nd-Cache': 'miss'}
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
    # TODO remove the S3_WRITE_MODE when the migration has been done.
    on_close = None
    ctype_ok = headers.get('Content-Type') in ('image/png', 'image/jpeg')
    if (
        write_s3 and mode != "preview" and ctype_ok and
        settings.ENABLE_S3_CACHING
    ):
        # cache layer in s3
        if settings.S3_WRITE_MODE == 'async':
            put_s3_file_async(content, request.path, headers)
        if settings.S3_WRITE_MODE == 'on_close':
            wmts_path = request.path

            def on_close_handler():
                put_s3_file(content, wmts_path, headers)

            on_close = on_close_handler
        else:
            put_s3_file(content, request.path, headers)

    elif not settings.ENABLE_S3_CACHING:
        logger.debug('S3 caching is disabled')
    else:
        logger.debug('Skipping insert')

    return on_close


def prepare_wmts_response(
    version,
    layer_id,
    style_name,
    time,
    srid,
    zoom,
    col,
    row,
    extension,
    mode,
    etag
):
    # pylint: disable=too-many-locals
    gagrid, bbox = validate_wmts_request(
        version, style_name, time, srid, zoom, col, row, extension
    )
    restriction, gutter, write_s3 = validate_restriction(
        layer_id, time, extension, gagrid, zoom, srid
    )
    image_format = get_image_format(extension)

    shift = gagrid.RESOLUTIONS[zoom] * gutter
    bbox = extend_bbox(bbox, shift)
    if srid == 4326:
        bbox = [bbox[1], bbox[0], bbox[3], bbox[2]]

    (status_code, content, headers, wms_time, tile_generation_time
    ) = get_optmize_tile(bbox, image_format, srid, layer_id, gutter, time)
    headers = prepare_wmts_headers(
        content, headers, wms_time, tile_generation_time, restriction
    )

    on_close = handle_2nd_level_cache(write_s3, mode, headers, content)

    if etag == headers.get('Etag'):
        return 304, None, headers, None

    return status_code, content, headers, on_close
