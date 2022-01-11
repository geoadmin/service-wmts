import io
import unittest
from unittest.mock import patch

import requests
import requests_mock
from PIL import Image

from app import app
from app import settings
from app.helpers.wmts_config import init_wmts_config

init_wmts_config()


class HTTPConnectionMock:

    def __init__(self, response_mock):
        self._response_mock = response_mock

    def request(self, *args, **kwargs):
        pass

    def close(self):
        pass

    def getresponse(self):
        return self._response_mock


class HttpResponseMock:

    def __init__(self, status, headers, data):
        self.status = status
        self.reason = "reason"
        self.headers = headers
        self.data = data

    def read(self):
        return self.data

    def getheaders(self):
        return self.headers.items()


def get_image_data():
    with open('tests/sample/gutter_image.png', 'rb') as fd:
        data = fd.read()
    return data


@patch('app.settings.ENABLE_S3_CACHING', False)
class InvalidRequestTests(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def assertCacheControl(self, response):
        self.assertIn(
            'Cache-Control',
            response.headers,
            msg='Missing cache-control header in GetTile response.'
        )
        self.assertIn(
            'max-age',
            response.headers['Cache-Control'],
            msg='Missing cache-control max-age directive '
            'in GetTile response.'
        )

    def test_wmts_bad_layer(self):
        resp = self.app.get(
            '/1.0.0/knickerbocker/default/current/21781/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported Layer', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_bad_extension(self):
        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.toto'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported image format', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_bad_mode(self):
        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png?mode=toto'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported mode', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_bad_srid(self):
        resp = self.app.get(
            '/1.0.0/inline_points/default/current/9999/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported srid', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_invalid_time(self):
        resp = self.app.get(
            '/1.0.0/inline_points/default/toto/2056/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Invalid time format', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_wrong_time(self):
        resp = self.app.get(
            '/1.0.0/inline_points/default/16021212/2056/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported timestamp', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_bad_version(self):
        resp = self.app.get(
            '/2.0.0/inline_points/default/current/9999/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported version', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_bad_stylename(self):
        resp = self.app.get(
            '/1.0.0/inline_points/customstyle/current/9999/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported style name', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_unsupported_zoom(self):
        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/35/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported zoom level', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_not_allowed_method(self):
        resp = self.app.post(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png',
            headers={"Accept": "text/html"}
        )
        self.assertEqual(resp.status_code, 405)
        self.assertIn('405 Method Not Allowed', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_out_of_bounds(self):
        resp = self.app.get(
            '/1.0.0/inline_points/default/current/4326/9/123/539.jpeg'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Tile out of bounds', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_4326_unsupported_zoom(self):
        resp = self.app.get(
            '1.0.0/inline_points/default/current/4326/18/273577/63352.png'
            '?mode=preview'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertCacheControl(resp)


class GetTileRequestsBaseTests(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def assertXWmtsHeaders(self, response, cache_hit=False):
        self.assert2ndCacheHeader(response, cache_hit)
        self.assertIn('X-WMS-Time', response.headers)
        try:
            self.assertGreater(float(response.headers['X-WMS-Time']), 0)
        except ValueError as err:
            self.fail(f'Invalid value "{err}" for X-WMS-Time header')
        self.assertIn('X-Tile-Generation-Time', response.headers)
        try:
            self.assertGreater(
                float(response.headers['X-Tile-Generation-Time']), 0
            )
        except ValueError as err:
            self.fail(
                f'Invalid value "{err}" for X-Tile-Generation-Time header'
            )

    def assert2ndCacheHeader(self, response, cache_hit):
        self.assertIn('X-2nd-Cache', response.headers)
        self.assertEqual(
            response.headers['X-2nd-Cache'], 'hit' if cache_hit else 'miss'
        )


@patch('app.settings.ENABLE_S3_CACHING', False)
class GetTileRequestsTests(GetTileRequestsBaseTests):

    def test_wmts_options_method(self):
        resp = self.app.options(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers['Cache-Control'],
            'public, max-age=3600, s-maxage=5184000'
        )
        self.assertEqual(resp.headers['Access-Control-Allow-Origin'], '*')
        self.assertEqual(
            resp.headers['Access-Control-Allow-Methods'], 'GET, HEAD, OPTIONS'
        )
        self.assertEqual(
            resp.headers['Access-Control-Allow-Headers'],
            'Content-Type, Authorization, x-requested-with, Origin, Accept'
        )
        self.assertEqual(len(resp.data), 0)

    @requests_mock.Mocker()
    def test_wmts_png_preview_gutter(self, mocker):
        data = get_image_data()

        mocker.get(
            settings.WMS_BACKEND,
            content=data,
            headers={
                'Content-Type': 'image/png', 'Content-Length': str(len(data))
            }
        )

        resp = self.app.get(
            '/1.0.0/inline_points/' +
            'default/current/21781/20/76/44.png?mode=preview'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers['Cache-Control'],
            'public, max-age=3600, s-maxage=31556952'
        )
        # Image must be cropped
        self.assertNotEqual(resp.data, data)
        img = Image.open(io.BytesIO(resp.data))
        self.assertEqual(img.width, 256)
        self.assertEqual(img.height, 256)

        # Check proprietary timing headers
        self.assertXWmtsHeaders(resp, cache_hit=False)

    @requests_mock.Mocker()
    def test_wmts_4326(self, mocker):
        data = get_image_data()

        mocker.get(
            settings.WMS_BACKEND,
            content=data,
            headers={
                'Content-Type': 'image/png', 'Content-Length': str(len(data))
            }
        )

        resp = self.app.get(
            '/1.0.0/inline_points/' +
            'default/current/4326/15/34136/7882.png?mode=preview'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers['Cache-Control'],
            'public, max-age=3600, s-maxage=31556952'
        )
        # Check proprietary timing headers
        self.assertXWmtsHeaders(resp)

    @requests_mock.Mocker()
    def test_cache_control_header(self, mocker):
        data = get_image_data()
        mocker.get(
            settings.WMS_BACKEND,
            content=data,
            headers={
                'Content-Type': 'image/png', 'Content-Length': str(len(data))
            }
        )

        resp = self.app.get(
            '/1.0.0/inline_points/'
            'default/current/4326/15/34136/7882.png'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            'Cache-Control',
            resp.headers,
            msg='Missing cache-control header in GetTile response.'
        )
        self.assertIn(
            'max-age',
            resp.headers['Cache-Control'],
            msg='Missing cache-control max-age directive '
            'in GetTile response.'
        )


@patch('app.settings.ENABLE_S3_CACHING', True)
@patch('http.client.HTTPConnection')
class GetTileRequestsS3Tests(GetTileRequestsBaseTests):

    def setUp(self):
        super().setUp()

        self.data = get_image_data()
        self.mock_get_s3_file_response_ok = HttpResponseMock(
            200, {
                'Content-Type': 'image/png',
                'Content-Length': str(len(self.data))
            },
            self.data
        )
        self.assertEqual(self.mock_get_s3_file_response_ok.status, 200)
        self.s3_not_found_data = '''
        <?xml version="1.0" encoding="UTF-8"?>
        <Error>
            <Code>NoSuchKey</Code>
            <Message>The specified key does not exist.</Message>
            <Key>my-key</Key>
            <BucketName>service-wmts-cache</BucketName>
            <Resource>/service-wmts-cache/my-key</Resource>
            <RequestId>16C7ABC12677586E</RequestId>
            <HostId>ddef4098-7a5f-41e9-a8ba-dd9ae85f0459</HostId>
        </Error>
        '''
        self.mock_get_s3_file_response_nok = HttpResponseMock(
            404,
            {
                'Content-Type': 'application/xml',
                'Content-Length': str(len(self.s3_not_found_data))
            },
            self.s3_not_found_data
        )
        self.assertEqual(self.mock_get_s3_file_response_nok.status, 404)
        self.mock_get_s3_file_conn_ok = HTTPConnectionMock(
            self.mock_get_s3_file_response_ok
        )
        self.mock_get_s3_file_conn_nok = HTTPConnectionMock(
            self.mock_get_s3_file_response_nok
        )

    def get_wms_request_mock(self, mocker):
        return mocker.get(
            settings.WMS_BACKEND,
            content=self.data,
            headers={
                'Content-Type': 'image/png',
                'Content-Length': str(len(self.data))
            }
        )

    @requests_mock.Mocker()
    @patch('app.helpers.wmts.put_s3_file')
    @patch('app.settings.S3_WRITE_MODE', 'sync')
    def test_wmts_nodata_true(self, mocker, mock_put_s3_file, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        self.get_wms_request_mock(mocker)

        resp = self.app.get(
            '/1.0.0/inline_points/default/current/4326/15/34136/7882.png' +
            '?nodata=true&mode=default'
        )
        mock_put_s3_file.assert_called()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b'OK')
        self.assertEqual(
            resp.headers['Cache-Control'],
            'public, max-age=3600, s-maxage=31556952'
        )
        self.assert2ndCacheHeader(resp, False)

    @requests_mock.Mocker()
    @patch('app.helpers.wmts.put_s3_file')
    @patch('app.settings.S3_WRITE_MODE', 'sync')
    def test_wmts_nodata_false(
        self, mocker, mock_put_s3_file, mock_get_s3_file
    ):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        self.get_wms_request_mock(mocker)

        resp = self.app.get(
            '/1.0.0/inline_points/default/current/4326/15/34136/7882.png'
            '?nodata=false&mode=default'
        )
        mock_put_s3_file.assert_called()
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(resp.data, b'OK')
        self.assertEqual(
            resp.headers['Cache-Control'],
            'public, max-age=3600, s-maxage=31556952'
        )
        self.assert2ndCacheHeader(resp, False)

    @requests_mock.Mocker()
    @patch('app.helpers.wmts.put_s3_file')
    @patch('app.settings.S3_WRITE_MODE', 'sync')
    def test_wmts_cadastral_wms_proxy(
        self, mocker, mock_put_s3_file, mock_get_s3_file
    ):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        self.get_wms_request_mock(mocker)

        resp = self.app.get(
            '1.0.0/inline_points/default/current/2056/17/4/7.png'
        )
        self.assertEqual(resp.status_code, 200)
        mock_put_s3_file.assert_called()
        self.assert2ndCacheHeader(resp, False)

    @requests_mock.Mocker()
    @patch('app.helpers.wmts.put_s3_file')
    @patch('app.settings.S3_WRITE_MODE', 'sync')
    def test_wmts_default_mode(
        self, mocker, mock_put_s3_file, mock_get_s3_file
    ):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        self.get_wms_request_mock(mocker)

        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png'
            '?mode=default'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers['Cache-Control'],
            'public, max-age=3600, s-maxage=31556952'
        )
        mock_put_s3_file.assert_called()
        self.assert2ndCacheHeader(resp, False)

    @requests_mock.Mocker()
    @patch('app.helpers.wmts.put_s3_file_async')
    @patch('app.settings.S3_WRITE_MODE', 'async')
    def test_wmts_default_mode_async_s3_write(
        self, mocker, mock_put_s3_file_async, mock_get_s3_file
    ):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        self.get_wms_request_mock(mocker)

        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png'
            '?mode=default'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers['Cache-Control'],
            'public, max-age=3600, s-maxage=31556952'
        )
        mock_put_s3_file_async.assert_called()
        self.assert2ndCacheHeader(resp, False)

    def test_wmts_cadastral_wms_proxy_from_s3_cache(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_ok

        resp = self.app.get(
            '1.0.0/inline_points/default/current/2056/17/4/7.png'
        )
        self.assertEqual(resp.status_code, 200)
        self.assert2ndCacheHeader(resp, True)

    def test_wmts_cadastral_wms_proxy_from_s3_cache_preview(
        self, mock_get_s3_file
    ):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_ok

        resp = self.app.get(
            '1.0.0/inline_points/default/current/2056/17/4/7.png?mode=preview'
        )
        self.assertEqual(resp.status_code, 200)
        self.assert2ndCacheHeader(resp, False)


@patch('app.settings.ENABLE_S3_CACHING', False)
class ErrorRequestsTests(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('app.helpers.wms.get_wms_image')
    def test_wmts_timeout(self, mock_wms_image):
        mock_wms_image.side_effect = requests.exceptions.Timeout

        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png'
        )

        mock_wms_image.assert_called()
        self.assertEqual(resp.status_code, 408)
        self.assertEqual(resp.headers['Cache-Control'], 'public, max-age=3600')
        self.assertIn('timed out', resp.get_data(as_text=True))

    @patch('app.helpers.wms.get_wms_image')
    def test_wmts_connection_error(self, mock_wms_image):
        mock_wms_image.side_effect = requests.exceptions.ConnectionError

        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png'
        )
        mock_wms_image.assert_called()
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.headers['Cache-Control'], 'public, max-age=5')
        self.assertIn('Bad Gateway', resp.get_data(as_text=True))

    @patch('app.helpers.wms.get_wms_image')
    def test_wmts_ssl_error(self, mock_wms_image):
        mock_wms_image.side_effect = requests.exceptions.SSLError

        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png'
        )
        mock_wms_image.assert_called()
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.headers['Cache-Control'], 'public, max-age=5')
        self.assertIn('Unable to verify SSL', resp.get_data(as_text=True))

    @patch('app.helpers.wms.get_wms_image')
    def test_wmts_internal_server_error(self, mock_wms_image):
        mock_wms_image.side_effect = Exception

        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png'
        )
        mock_wms_image.assert_called()
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.headers['Cache-Control'], 'public, max-age=5')
        self.assertIn(
            'Internal server error, please consult logs',
            resp.get_data(as_text=True)
        )

    @requests_mock.Mocker()
    def test_wmts_bad_content_type(self, mocker):
        # we simulate a xml mapserver response
        mocker.get(
            settings.WMS_BACKEND,
            content='<?xml version="1.0"?>'.encode('utf-8'),
            headers={'Content-Type': 'text/xml; charset=UTF-8'}
        )

        resp = self.app.get(
            '/1.0.0/inline_points/' +
            'default/current/21781/20/76/44.png?mode=preview'
        )
        self.assertEqual(resp.status_code, 501)
        self.assertEqual(resp.headers['Cache-Control'], 'public, max-age=5')
