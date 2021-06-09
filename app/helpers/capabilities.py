import logging

from app.helpers.utils import get_closest_zoom

logger = logging.getLogger(__name__)


def get_layers_zoom_level_set(epsg, layers_capabilities):
    zoom_levels = set()
    for layer in layers_capabilities:
        zoom = get_closest_zoom(layer.resolution_max, epsg)
        zoom_levels.add(zoom)
    return zoom_levels
