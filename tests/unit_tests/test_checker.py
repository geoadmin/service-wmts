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
        resp = self.app.get('/wms_checker')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b'OK')

    @patch('app.routes.get_wms_backend_root')
    def test_backend_checker_down(self, mock_get_wms_backend_root):
        mock_get_wms_backend_root.side_effect = \
            requests.exceptions.ConnectionError
        resp = self.app.get('/wms_checker')
        mock_get_wms_backend_root.assert_called_once()
        self.assertEqual(resp.status_code, 502)
