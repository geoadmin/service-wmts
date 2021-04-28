import unittest

from app import app
from app.version import APP_VERSION


class CheckerTests(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.assertEqual(app.debug, False)

    def test_checker(self):
        response = self.app.get("/checker")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(
            response.json, {
                "message": "OK", "success": True, "version": APP_VERSION
            }
        )
