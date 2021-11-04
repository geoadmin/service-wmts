'''Service launcher to use Flask without wsgi.py
'''
from app.helpers.logging_utils import init_logging
from app.helpers.wmts_config import init_wmts_config

# Initialize Logging using JSON format for all loggers and using the Stream
# Handler.
init_logging()

# We initialize the wmts config here to do it only once, but only when
# the logging has been configured. If we do it in the app.__init__.py module
# the we don't have the logging yet configured and we don't get any logs
init_wmts_config()

# pylint: disable=unused-import,wrong-import-position
from app import app
