import hashlib
import logging
import re
from datetime import datetime

from pyproj import Proj
from pyproj import transform

from flask import jsonify
from flask import make_response

logger = logging.getLogger(__name__)


def make_error_msg(code, msg):
    return make_response(
        jsonify({
            'success': False, 'error': {
                'code': code, 'message': msg
            }
        }),
        code
    )


def crop_image(img, gutter):
    return img.crop(
        (gutter, gutter, int(img.size[0]) - gutter, int(img.size[1]) - gutter)
    )


def extend_bbox(bbox, shift):
    return [bbox[0] - shift, bbox[1] - shift, bbox[2] + shift, bbox[3] + shift]


def re_project_bbox(bbox, srid_to, srid_from=2056):
    srid_in = Proj('+init=EPSG:%s' % srid_from)
    srid_out = Proj('+init=EPSG:%s' % srid_to)
    p_left = transform(srid_in, srid_out, bbox[0], bbox[1])
    p_right = transform(srid_in, srid_out, bbox[2], bbox[3])
    return p_left + p_right


def tile_address(grid, zoom, col, row):
    return grid.tileAddressTemplate \
        .replace('{zoom}', str(zoom)) \
        .replace('{tileCol}', str(col)) \
        .replace('{tileRow}', str(row))


def digest(data):
    return hashlib.md5(data).hexdigest()


dateRe = re.compile(r'expiry-date="(.*)GMT"')


def is_still_valid_tile(exp_header, current_time):
    expiration = dateRe.match(exp_header).groups()[0].split(',')[1].strip()
    return current_time < datetime.strptime(expiration, '%d %b %Y %H:%M:%S')


def set_cache_control(headers, restriction):
    cache_ttl = restriction.get('cache_ttl')
    if cache_ttl:
        headers['Cache-Control'] = f'public, max-age={cache_ttl}'
    return headers


def get_image_format(extension):
    image_format = extension
    # TODO CLEAN_UP: if the pngjpeg hack is not needed anymore we should
    # remove it
    if extension == 'pngjpeg':
        image_format = 'png'
    return image_format
