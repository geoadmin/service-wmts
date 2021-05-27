import logging
import time

from flask import render_template
from flask import request
from flask.views import View

from app import app
from app.helpers.capabilities import get_layers_zoom_level_set
from app.helpers.utils import get_default_tile_matrix_set
from app.helpers.wmts import validate_epsg
from app.helpers.wmts import validate_lang
from app.helpers.wmts import validate_version
from app.models import GetCapThemes
from app.models import ServiceMetadata
from app.models import localized_models

logger = logging.getLogger(__name__)


class GetCapabilities(View):
    methods = ['GET', 'HEAD', 'OPTIONS']

    def dispatch_request(self, epsg, lang, version):  # pylint: disable=arguments-differ
        epsg, lang, version = self.get_and_validate_args(epsg, lang, version)

        scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
        url_base = f'{scheme}://{app.config["WMTS_PUBLIC_HOST"]}/'

        models = self.get_models(lang)
        context = self.get_context(models, epsg, lang, url_base, scheme)
        return (
            render_template(
                ['WmtsCapabilities.xml.jinja', 'StandardHeader.xml.jinja'],
                **context,
            ),
            {
                'Content-Type': 'text/xml; charset=UTF-8'
            },
        )

    @classmethod
    def get_and_validate_args(cls, epsg, lang, version):
        # If no epsg and/or lang argument in path is given, take it
        # from the query arguments.
        if epsg is None:
            epsg = request.args.get('epsg', 21781)
        if lang is None:
            lang = request.args.get('lang', 'de')

        validate_epsg(epsg)
        validate_lang(lang)
        validate_version(version)

        return epsg, lang, version

    @classmethod
    def get_models(cls, lang):
        return localized_models[lang]

    @classmethod
    def get_context(cls, models, epsg, lang, url_base, scheme):
        start = time.time()
        layers_capabilities = models['GetCap'].query.filter_by_staging(
            app.config['APP_STAGING']
        )
        logger.debug('GetCap query done in %fs', time.time() - start)
        start_int = time.time()
        zoom_levels = get_layers_zoom_level_set(epsg, layers_capabilities)
        logger.debug('get layers zoom done in %fs', time.time() - start_int)
        start_int = time.time()
        themes = models['GetCapThemes'].query.order_by(
            GetCapThemes.upper_theme_id
        ).all()
        logger.debug('get cap themes in %fs', time.time() - start_int)
        start_int = time.time()
        metadata = models['ServiceMetadata'].query.filter(
            ServiceMetadata.pk_map_name.like('%wmts-bgdi%')
        ).first()
        logger.debug('get metadata done in %fs', time.time() - start_int)
        logger.debug('Zoom levels: %s', zoom_levels)
        context = {
            'layers': layers_capabilities,
            'zoom_levels': zoom_levels,
            'themes': themes,
            'metadata': metadata,
            'scheme': scheme,
            'url_base': url_base,
            'epsg': epsg,
            'default_tile_matrix_set': get_default_tile_matrix_set(epsg),
            'legend_base_url': app.config["LEGENDS_BASE_URL"],
            'language': lang
        }
        logger.debug('Data context created in %fs', time.time() - start)
        return context
