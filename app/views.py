import logging
import time

from flask import abort
from flask import render_template
from flask import request
from flask.views import View

from app import app
from app.helpers.utils import get_closest_zoom
from app.helpers.utils import get_default_tile_matrix_set
from app.helpers.wmts import validate_epsg
from app.helpers.wmts import validate_lang
from app.helpers.wmts import validate_version
from app.models import GetCapThemes
from app.models import ServiceMetadata
from app.models import localized_models

logger = logging.getLogger(__name__)


class GetCapabilities(View):
    methods = ['GET']

    # pylint: disable=arguments-differ
    def dispatch_request(self, version, epsg=None, lang=None):
        validate_version()
        epsg, lang = self.get_and_validate_args(epsg, lang)

        context = self.get_context(self.get_models(lang), epsg, lang)
        return (
            render_template(
                'WmtsCapabilities.xml.jinja',
                **context,
            ),
            {
                'Content-Type': 'text/xml; charset=UTF-8'
            },
        )

    @classmethod
    def get_and_validate_args(cls, epsg, lang):
        # If no epsg and/or lang argument in path is given, take it
        # from the query arguments.
        if epsg is None:
            try:
                epsg = request.args.get('epsg', '21781')
                epsg = int(epsg)
            except ValueError as error:
                logger.error('Invalid epsg=%s, must be an int: %s', epsg, error)
                abort(400, f'Invalid epsg "{epsg}", must be an integer')
        if lang is None:
            lang = request.args.get('lang', 'de')

        validate_epsg(epsg)
        validate_lang(lang)

        return epsg, lang

    @classmethod
    def get_models(cls, lang):
        return localized_models[lang]

    @classmethod
    def get_layers_capabilities(cls, model):
        return model.query.filter_by_staging(app.config['APP_STAGING'])

    @classmethod
    def get_layers_zoom_level_set(cls, epsg, layers_capabilities):
        zoom_levels = set()
        for layer in layers_capabilities:
            zoom = get_closest_zoom(layer.resolution_max, epsg)
            zoom_levels.add(zoom)
        return zoom_levels

    @classmethod
    def get_themes(cls, model):
        return model.query.order_by(GetCapThemes.inspire_upper_theme_id).all()

    @classmethod
    def get_metadata(cls, model):
        return model.query.filter(
            ServiceMetadata.pk_map_name.like('%wmts-bgdi%')
        ).first()

    @classmethod
    def get_context(cls, models, epsg, lang):
        start = time.time()
        layers_capabilities = cls.get_layers_capabilities(models['GetCap'])
        logger.debug('GetCap query done in %fs', time.time() - start)
        start_int = time.time()
        zoom_levels = cls.get_layers_zoom_level_set(epsg, layers_capabilities)
        logger.debug('get layers zoom done in %fs', time.time() - start_int)
        start_int = time.time()
        themes = cls.get_themes(models['GetCapThemes'])
        logger.debug('get cap themes in %fs', time.time() - start_int)
        start_int = time.time()
        metadata = cls.get_metadata(models['ServiceMetadata'])
        logger.debug('get metadata done in %fs', time.time() - start_int)
        logger.debug('Zoom levels: %s', zoom_levels)
        context = {
            'layers': layers_capabilities,
            'zoom_levels': zoom_levels,
            'themes': themes,
            'metadata': metadata,
            'url_base': request.url_root,
            'epsg': epsg,
            'default_tile_matrix_set': get_default_tile_matrix_set(epsg),
            'legend_base_url': app.config["LEGENDS_BASE_URL"],
            'language': lang
        }
        logger.debug('Data context created in %fs', time.time() - start)
        return context
