# pylint: disable=c-extension-no-member
import unittest
from unittest.mock import patch
from uuid import uuid4

from lxml import etree

from flask import url_for

from app import app
from app import settings
from app.models import GetCapDe
from app.models import GetCapThemesDe
from app.models import ServiceMetadataDe


class GetCapabilitiesTest(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True
        self.ctx = app.test_request_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_get_capabilities_invalid_param(self):
        for url, url_args, error_msg in [(
            'get_capabilities_1',
            {'version': '1.0.0', 'epsg': 10, 'lang': 'de' },
            'Unsupported epsg 10, must be on of [21781, 2056, 3857, 4326]'
        ),(
            'get_capabilities_1',
            {'version': '1.0.0', 'epsg': 2056, 'lang': 'hg' },
            "Unsupported lang hg, must be on of ['de', 'fr', 'it', 'rm', 'en']"
        ),(
            'get_capabilities_1',
            {'version': '1.0.1', 'epsg': 2056, 'lang': 'de' },
            'Unsupported version: 1.0.1. Only "1.0.0" is supported.'
        )]:
            with self.subTest(url=url, url_args=url_args):
                response = self.client.get(url_for(url, **url_args))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.json,
                    {
                        'error': {
                            'code': 400, 'message': error_msg
                        },
                        'success': False
                    }
                )

    @patch('flask_sqlalchemy._QueryProperty.__get__')
    def test_get_capabilities_no_data_all_routes(self, query_mock):
        query_mock.return_value.all.return_value = []
        for url, url_args, url_params in [(
            'get_capabilities_1', {'epsg': 2056, 'lang': 'fr'}, {}
        ), (
            'get_capabilities_1', {'epsg': 4326, 'lang': 'it'}, {}
        ), (
            'get_capabilities_1', {'epsg': 21781, 'lang': 'en'}, {}
        ), (
            'get_capabilities_2', {'epsg': 3857}, {}
        ), (
            'get_capabilities_3', {'epsg': 4326}, {}
        ), (
            'get_capabilities_4', {}, {'epsg': '2056'}
        )]:
            with self.subTest(
                url=url, url_args=url_args, url_params=url_params
            ):
                response = self.client.get(
                    url_for(url, version='1.0.0', **url_args),
                    query_string=url_params
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.content_type, 'text/xml; charset=UTF-8'
                )

    @unittest.skipIf(
        settings.UNITTEST_SKIP_XML_VALIDATION,
        reason="XML validation is disabled by UNITTEST_SKIP_XML_VALIDATION"
    )
    @patch('app.views.GetCapabilities.get_layers_capabilities')
    @patch('app.views.GetCapabilities.get_themes')
    @patch('app.views.GetCapabilities.get_metadata')
    def test_get_capabilities(
        self,
        get_metadata_mock,
        get_themes_mock,
        get_layers_capabilities_mock,
    ):
        schema_file = f"{settings.BASE_DIR}/tests/wmts_schemas/1.0.1/" \
            "wmtsGetFeatureInfo_response.xsd"
        schema_doc = etree.parse(schema_file)
        print('Parsing XML schema, please wait this takes a while...')
        schema = etree.XMLSchema(schema_doc)
        parser = etree.XMLParser(schema=schema)
        capabilities = [
            GetCapDe(
                id='test-layer-1',
                id_geocat=str(uuid4()),
                staging='prod',
                short_description='This is a layer for unittest',
                abstract='Abstract of test layer',
                formats=['png', 'jpg'],
                timestamps=['current', '20090101'],
                resolution_max=0.5,
                topics=['api', 'ech'],
                has_legend=True
            ),
            GetCapDe(
                id='test-layer-2',
                id_geocat=str(uuid4()),
                staging='prod',
                short_description='This is a layer for unittest',
                abstract='Abstract of test layer',
                formats=['png', 'jpg'],
                timestamps=['current', '20090101'],
                resolution_max=0.5,
                topics=['api', 'ech'],
                has_legend=True
            ),
        ]
        get_layers_capabilities_mock.return_value = capabilities
        get_themes_mock.return_value = [
            GetCapThemesDe(
                id="1",
                inspire_name="Sub theme",
                inspire_abstract="Sub theme",
                inspire_upper_theme_name="Main theme",
                inspire_upper_theme_abstract="Main theme",
                inspire_upper_theme_id="dcf0cad08fc749baa39453bb22e1a6f4",
                fk_dataset_ids=['test-layer-1', 'test-layer-2']
            )
        ]
        get_metadata_mock.return_value = ServiceMetadataDe(
            id=1,
            pk_map_name="wmts-bgdi",
            title="WMTS BGDI",
            abstract=None,
            keywords="Switzerland,OGC,Web Map Service",
            fee="Open source",
            access_constraint="Sign up",
            name="swisstopo"
        )
        response = self.client.get(
            url_for('get_capabilities_4', version='1.0.0')
        )

        self.assertEqual(response.status_code, 200)
        try:
            etree.fromstring(response.data, parser)
        except (etree.XMLSyntaxError) as error:
            self.fail(f'Invalid WMTSCapabilities.xml: {error}')
