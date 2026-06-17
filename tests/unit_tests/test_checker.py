import unittest
from unittest.mock import patch

import requests

from app import app
from app.version import APP_VERSION


class CheckerTests(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_checker(self):
        response = self.app.get("/checker")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(
            response.json, {
                "message": "OK", "success": True, "version": APP_VERSION
            }
        )

    def test_backend_checker(self):
        resp = self.app.get('/checker/ready')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, "application/json")
        self.assertEqual(resp.json, {
            "message": "OK",
            "success": True,
        })

    @patch('app.helpers.wms.get_backend')
    def test_backend_checker_down(self, mock_get_backend):
        mock_get_backend.side_effect = \
            requests.exceptions.ConnectionError
        resp = self.app.get('/checker/ready')
        mock_get_backend.assert_called_once()
        self.assertEqual(resp.status_code, 502)

    @patch('app.routes.get_wms_backend_readiness')
    def test_backend_checker_ready(self, mock_readiness):
        mock_readiness.return_value = (
            b'No query information to decode. QUERY_STRING is set, but empty.'
        )
        resp = self.app.get('/checker/ready')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'success': True, 'message': 'OK'})

    @patch('app.routes.get_wms_backend_readiness')
    def test_backend_checker_missing_marker(self, mock_readiness):
        mock_readiness.return_value = (
            b'<HTML><BODY>Apache is up but MapServer is not.</BODY></HTML>'
        )
        resp = self.app.get('/checker/ready')
        self.assertEqual(resp.status_code, 503)
