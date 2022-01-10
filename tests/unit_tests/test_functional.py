import unittest
from datetime import datetime

from PIL import Image
from werkzeug import exceptions

from app import app
from app.helpers.utils import crop_image
from app.helpers.utils import extend_bbox
from app.helpers.utils import is_still_valid_tile
from app.helpers.wms import get_wms_params
from app.views import GetCapabilities


class MockResponse:

    def __init__(self, headers):
        self.headers = headers

    def getheader(self, name):
        return self.headers.get(name)


class FunctionalGetTileTests(unittest.TestCase):

    def test_crop_image(self):
        gutter = 30
        img = Image.open('tests/sample/gutter_image.png')
        height = img.height
        width = img.width
        img_crop = crop_image(img, gutter)
        h_crop = img_crop.height
        w_crop = img_crop.width
        self.assertGreater(height, h_crop)
        self.assertGreater(width, w_crop)
        self.assertEqual(h_crop, 256)
        self.assertEqual(w_crop, 256)

    def test_extend_bbox(self):
        bbox = [10, 10, 20, 20]
        bbox_extended = extend_bbox(bbox, 10)
        self.assertEqual(bbox_extended[0], 0)
        self.assertEqual(bbox_extended[1], 0)
        self.assertEqual(bbox_extended[2], 30)
        self.assertEqual(bbox_extended[3], 30)

    def test_get_wms_params(self):
        bbox = [1.0, 1.0, 5.0, 5.0]
        srid = 2056
        image_format = 'png'
        layers = 'ch.dummy'
        gutter = 10
        time = 'current'
        wms_params = get_wms_params(
            bbox, image_format, srid, layers, gutter, time
        )
        self.assertEqual(wms_params['SERVICE'], 'WMS')
        self.assertEqual(wms_params['VERSION'], '1.3.0')
        self.assertEqual(wms_params['FORMAT'], 'image/png')
        self.assertEqual(wms_params['TRANSPARENT'], 'true')
        self.assertEqual(wms_params['LAYERS'], 'ch.dummy')
        self.assertEqual(wms_params['WIDTH'], '276')
        self.assertEqual(wms_params['HEIGHT'], '276')
        self.assertEqual(wms_params['CRS'], 'EPSG:2056')
        self.assertEqual(wms_params['STYLES'], '')
        self.assertEqual(wms_params['TIME'], 'current')
        self.assertEqual(wms_params['BBOX'], '1.0,1.0,5.0,5.0')

        image_format = 'jpeg'
        wms_params = get_wms_params(
            bbox, image_format, srid, layers, gutter, time
        )
        self.assertEqual(wms_params['TRANSPARENT'], 'false')
        self.assertEqual(wms_params['FORMAT'], 'image/jpeg')

    def test_valid_tile_with_headers(self):
        headers = """expiry-date="Tue, 8 May 2018 00:00:00 GMT",
                  rule-id="all 2056 PK grau - prefix and tag 16/2/1, 5
                  days" """
        self.assertEqual(
            is_still_valid_tile(
                headers,
                datetime.strptime('5 May 2018 09:00:00', '%d %b %Y %H:%M:%S')
            ),
            True
        )

    def test_invalidated_tile(self):
        headers = """expiry-date="Tue, 8 May 2018 00:00:00 GMT",
                  rule-id="all 2056 PK grau - prefix and tag 16/2/1, 5
                  days" """
        self.assertEqual(is_still_valid_tile(headers, datetime.now()), False)


class FunctionalGetCapTests(unittest.TestCase):

    def test_invalid_query(self):
        with self.assertRaises(exceptions.BadRequest) as context:
            with app.test_request_context('/1.0.0/WMTSCapabilities?epsg=abc'):
                GetCapabilities.get_and_validate_args(
                    version='1.0.0', epsg=None, lang=None
                )
        exception = context.exception
        self.assertEqual(
            exception.description, 'Invalid epsg "abc", must be an integer'
        )

        with self.assertRaises(exceptions.BadRequest) as context:
            with app.test_request_context('/1.0.0/WMTSCapabilities?lang=123'):
                GetCapabilities.get_and_validate_args(
                    version='1.0.0', epsg=None, lang=None
                )
        exception = context.exception
        self.assertEqual(
            exception.description,
            "Unsupported lang 123, must be on of ['de', 'fr', 'it', 'rm', 'en']"
        )

        with self.assertRaises(exceptions.BadRequest) as context:
            with app.test_request_context('/1.0.0/WMTSCapabilities'):
                GetCapabilities.get_and_validate_args(
                    version='unknown', epsg=None, lang=None
                )
        exception = context.exception
        self.assertEqual(
            exception.description,
            'Unsupported version: unknown. Only "1.0.0" is supported.'
        )

    def test_valid_query(self):
        with app.test_request_context(
            '/1.0.0/WMTSCapabilities?epsg=2056&lang=fr'
        ):
            version, epsg, lang = GetCapabilities.get_and_validate_args(
                version='1.0.0', epsg=None, lang=None
            )
        self.assertEqual(version, '1.0.0')
        self.assertEqual(epsg, 2056)
        self.assertEqual(lang, 'fr')
