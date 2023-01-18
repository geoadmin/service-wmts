import io
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

import requests
import requests_mock
import requests_mock.mocker
from PIL import Image

from app import app
from app import settings
from app.helpers.wmts import handle_2nd_level_cache
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


class BaseTest(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

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
        self.assertIn('X-Tiles-S3-Cache', response.headers)
        self.assertEqual(
            response.headers['X-Tiles-S3-Cache'],
            'hit' if cache_hit else 'miss'
        )


@patch('http.client.HTTPConnection')
class InvalidRequestTests(BaseTest):

    def test_wmts_bad_layer(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        resp = self.app.get(
            '/1.0.0/knickerbocker/default/current/21781/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported Layer', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_bad_extension(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.toto'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported image format', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_bad_mode(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png?mode=toto'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported mode', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_bad_srid(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        resp = self.app.get(
            '/1.0.0/inline_points/default/current/9999/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported srid', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_invalid_time(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        resp = self.app.get(
            '/1.0.0/inline_points/default/toto/2056/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Invalid time format', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_wrong_time(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        resp = self.app.get(
            '/1.0.0/inline_points/default/16021212/2056/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported timestamp', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_bad_version(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        resp = self.app.get(
            '/2.0.0/inline_points/default/current/9999/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported version', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_bad_stylename(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        resp = self.app.get(
            '/1.0.0/inline_points/customstyle/current/9999/20/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported style name', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_unsupported_zoom(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/35/76/44.png'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unsupported zoom level', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_not_allowed_method(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        resp = self.app.post(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png',
            headers={"Accept": "text/html"}
        )
        self.assertEqual(resp.status_code, 405)
        self.assertIn('405 Method Not Allowed', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_out_of_bounds(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        resp = self.app.get(
            '/1.0.0/inline_points/default/current/4326/9/123/539.jpeg'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Tile out of bounds', resp.get_data(as_text=True))
        self.assertCacheControl(resp)

    def test_wmts_4326_unsupported_zoom(self, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        resp = self.app.get(
            '1.0.0/inline_points/default/current/4326/18/273577/63352.png'
            '?mode=preview'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertCacheControl(resp)


@requests_mock.Mocker()
@patch('http.client.HTTPConnection')
class GetTileRequestsTests(BaseTest):

    def test_wmts_options_method(self, mock_wms, mock_get_s3_file):
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

    def test_wmts_png_preview_gutter(self, mock_wms, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_ok
        self.get_wms_request_mock(mock_wms)

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
        self.assertNotEqual(resp.data, self.data)
        img = Image.open(io.BytesIO(resp.data))
        self.assertEqual(img.width, 256)
        self.assertEqual(img.height, 256)

        # Check proprietary timing headers
        self.assertXWmtsHeaders(resp, cache_hit=False)

    def test_wmts_4326(self, mock_wms, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        self.get_wms_request_mock(mock_wms)

        resp = self.app.get(
            '/1.0.0/inline_points/' + 'default/current/4326/15/34136/7882.png'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers['Cache-Control'],
            'public, max-age=3600, s-maxage=31556952'
        )
        # Check proprietary timing headers
        self.assertXWmtsHeaders(resp, cache_hit=False)

    def test_cache_control_header(self, mock_wms, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        self.get_wms_request_mock(mock_wms)

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
        # Check proprietary timing headers
        self.assertXWmtsHeaders(resp, cache_hit=False)


@requests_mock.Mocker()
@patch('http.client.HTTPConnection')
class GetTileRequestsS3Tests(BaseTest):

    def assertMock(self, mock_wms, mock_get_s3_file):
        self.assertIsInstance(mock_wms, requests_mock.mocker.Mocker)
        self.assertIsInstance(mock_get_s3_file, MagicMock)
        # pylint: disable=protected-access
        self.assertEqual(mock_get_s3_file._mock_name, 'HTTPConnection')

    def test_wmts_nodata_true(self, mock_wms, mock_get_s3_file):
        self.assertMock(mock_wms, mock_get_s3_file)

        def handle_2nd_level_cache_wrapper(*args, **kwargs):
            wrapper_return_value = handle_2nd_level_cache(*args, **kwargs)
            self.assertIsNotNone(
                wrapper_return_value,
                msg='handle_2nd_level_cache() did not returned the write to S3 '
                'callback'
            )
            self.assertEqual(wrapper_return_value.__name__, 'on_close_handler')
            return wrapper_return_value

        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        self.get_wms_request_mock(mock_wms)

        with patch(
            'app.helpers.wmts.handle_2nd_level_cache',
            wraps=handle_2nd_level_cache_wrapper
        ) as mock_handle_2nd_level_cache:
            resp = self.app.get(
                '/1.0.0/inline_points/default/current/4326/15/34136/7882.png' +
                '?nodata=true&mode=default'
            )
            self.assertEqual(resp.status_code, 200)
            mock_handle_2nd_level_cache.assert_called()
        self.assertEqual(resp.data, b'OK')
        self.assertEqual(
            resp.headers['Cache-Control'],
            'public, max-age=3600, s-maxage=31556952'
        )
        self.assert2ndCacheHeader(resp, False)

    def test_wmts_nodata_false(self, mock_wms, mock_get_s3_file):
        self.assertMock(mock_wms, mock_get_s3_file)
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        self.get_wms_request_mock(mock_wms)

        def handle_2nd_level_cache_wrapper(*args, **kwargs):
            wrapper_return_value = handle_2nd_level_cache(*args, **kwargs)
            self.assertIsNotNone(
                wrapper_return_value,
                msg='handle_2nd_level_cache() did not returned the write to S3 '
                'callback'
            )
            self.assertEqual(wrapper_return_value.__name__, 'on_close_handler')
            return wrapper_return_value

        with patch(
            'app.helpers.wmts.handle_2nd_level_cache',
            wraps=handle_2nd_level_cache_wrapper
        ) as mock_handle_2nd_level_cache:
            resp = self.app.get(
                '/1.0.0/inline_points/default/current/4326/15/34136/7882.png'
                '?nodata=false&mode=default'
            )
            self.assertEqual(resp.status_code, 200)
            mock_handle_2nd_level_cache.assert_called()

        self.assertNotEqual(resp.data, b'OK')
        self.assertEqual(
            resp.headers['Cache-Control'],
            'public, max-age=3600, s-maxage=31556952'
        )
        self.assert2ndCacheHeader(resp, False)

    def test_wmts_cadastral_wms_proxy(self, mock_wms, mock_get_s3_file):
        self.assertMock(mock_wms, mock_get_s3_file)
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        self.get_wms_request_mock(mock_wms)

        def handle_2nd_level_cache_wrapper(*args, **kwargs):
            wrapper_return_value = handle_2nd_level_cache(*args, **kwargs)
            self.assertIsNotNone(
                wrapper_return_value,
                msg='handle_2nd_level_cache() did not returned the write to S3 '
                'callback'
            )
            self.assertEqual(wrapper_return_value.__name__, 'on_close_handler')
            return wrapper_return_value

        with patch(
            'app.helpers.wmts.handle_2nd_level_cache',
            wraps=handle_2nd_level_cache_wrapper
        ) as mock_handle_2nd_level_cache:
            resp = self.app.get(
                '1.0.0/inline_points/default/current/2056/17/4/7.png'
            )
            self.assertEqual(resp.status_code, 200)
            mock_handle_2nd_level_cache.assert_called()
        self.assertIsNotNone(
            mock_handle_2nd_level_cache.return_value,
            msg="call_on_close handler for caching answer into S3 not set"
        )
        self.assert2ndCacheHeader(resp, False)

    def test_wmts_preview_mode(self, mock_wms, mock_get_s3_file):
        self.assertMock(mock_wms, mock_get_s3_file)
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        self.get_wms_request_mock(mock_wms)

        def handle_2nd_level_cache_wrapper(*args, **kwargs):
            wrapper_return_value = handle_2nd_level_cache(*args, **kwargs)
            self.assertIsNone(
                wrapper_return_value,
                msg='handle_2nd_level_cache() did returned the write to S3 '
                'callback'
            )
            return wrapper_return_value

        with patch(
            'app.helpers.wmts.handle_2nd_level_cache',
            wraps=handle_2nd_level_cache_wrapper
        ) as mock_handle_2nd_level_cache:
            resp = self.app.get(
                '/1.0.0/inline_points/default/current/21781/20/76/44.png'
                '?mode=preview'
            )
            self.assertEqual(resp.status_code, 200)
            mock_handle_2nd_level_cache.assert_called()
        self.assertEqual(
            resp.headers['Cache-Control'],
            'public, max-age=3600, s-maxage=31556952'
        )
        self.assert2ndCacheHeader(resp, False)


@patch('http.client.HTTPConnection')
class GetTileRequestsFromS3Tests(BaseTest):

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


@patch('http.client.HTTPConnection')
class ErrorRequestsTests(BaseTest):

    @patch('app.helpers.wms.get_wms_image')
    def test_wmts_timeout(self, mock_wms_image, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        mock_wms_image.side_effect = requests.exceptions.Timeout

        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png'
        )

        mock_wms_image.assert_called()
        self.assertEqual(resp.status_code, 408)
        self.assertEqual(resp.headers['Cache-Control'], 'public, max-age=3600')
        self.assertIn('timed out', resp.get_data(as_text=True))

    @patch('app.helpers.wms.get_wms_image')
    def test_wmts_connection_error(self, mock_wms_image, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        mock_wms_image.side_effect = requests.exceptions.ConnectionError

        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png'
        )
        mock_wms_image.assert_called()
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.headers['Cache-Control'], 'no-cache')
        self.assertIn('Bad Gateway', resp.get_data(as_text=True))

    @patch('app.helpers.wms.get_wms_image')
    def test_wmts_ssl_error(self, mock_wms_image, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
        mock_wms_image.side_effect = requests.exceptions.SSLError

        resp = self.app.get(
            '/1.0.0/inline_points/default/current/21781/20/76/44.png'
        )
        mock_wms_image.assert_called()
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.headers['Cache-Control'], 'no-cache')
        self.assertIn('Unable to verify SSL', resp.get_data(as_text=True))

    @patch('app.helpers.wms.get_wms_image')
    def test_wmts_internal_server_error(self, mock_wms_image, mock_get_s3_file):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok
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
    def test_wmts_bad_content_type(self, mock_get_s3_file, mocker):
        mock_get_s3_file.return_value = self.mock_get_s3_file_conn_nok

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
