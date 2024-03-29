import hashlib
import logging
import math
import re
from datetime import datetime

from gatilegrid import getTileGrid
from pyproj import Proj
from pyproj import transform

from flask import jsonify
from flask import make_response

from app.settings import GET_TILE_BROWSER_CACHE_MAX_TTL
from app.settings import GET_TILE_CACHE_TEMPLATE

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
    srid_in = Proj(f'+init=EPSG:{srid_from}')
    srid_out = Proj(f'+init=EPSG:{srid_to}')
    p_left = transform(srid_in, srid_out, bbox[0], bbox[1])
    p_right = transform(srid_in, srid_out, bbox[2], bbox[3])
    return p_left + p_right


def digest(data):
    return hashlib.md5(data).hexdigest()


dateRe = re.compile(r'expiry-date="(.*)GMT"')


def is_still_valid_tile(exp_header, current_time):
    expiration = dateRe.match(exp_header).groups()[0].split(',')[1].strip()
    return current_time < datetime.strptime(expiration, '%d %b %Y %H:%M:%S')


def set_cache_control(headers, restriction):
    cache_ttl = restriction.get('cache_ttl')
    if cache_ttl:
        headers['Cache-Control'] = GET_TILE_CACHE_TEMPLATE.format(
            cf_cache_ttl=cache_ttl,
            browser_cache_ttl=(
                cache_ttl if cache_ttl < GET_TILE_BROWSER_CACHE_MAX_TTL else
                GET_TILE_BROWSER_CACHE_MAX_TTL
            )
        )
    return headers


def resolution_factor_at_latitude(latitude):
    return math.cos(latitude * (math.pi / 180.0))


# Zoom is defined at the Equator for WebMercator, layer defined at the
# latitude of Switzerland have to be corrected.
def get_closest_zoom(resolution, epsg, latitude=0.0):
    if int(epsg) == 3857:
        resolution /= resolution_factor_at_latitude(latitude)
    tilegrid = getTileGrid(int(epsg))()
    return tilegrid.getClosestZoom(float(resolution))


def get_default_tile_matrix_set(epsg):
    tilematrix_set = {}

    tilegrid_class = getTileGrid(int(epsg))
    gagrid = tilegrid_class(useSwissExtent=epsg in ['2056', '21781'])
    for zoom in range(0, len(gagrid.RESOLUTIONS)):
        tilematrix_set[zoom] = [
            gagrid.getResolution(zoom),
            gagrid.numberOfXTilesAtZoom(zoom),
            gagrid.numberOfYTilesAtZoom(zoom),
            gagrid.getScale(zoom)
        ]
    # Reversing the axis order for 'EPSG:4326' is needed for now. If we switch
    # to CRS84, the axis order will be (lng, lat) the other projected CRS
    # (see commit message for a backround information). Between the two systems,
    # the tiles are fully compatible.
    # The variable names (minx, maxy) is very unfortunate though.
    tilematrix_set['MAXY'] = gagrid.MAXY if int(epsg) == 4326 else gagrid.MINX
    tilematrix_set['MINX'] = gagrid.MINX if int(epsg) == 4326 else gagrid.MAXY
    return tilematrix_set
