import logging

from kombu.serialization import registry
from werkzeug.exceptions import HTTPException

from flask import Flask
from flask import request
from flask_sqlalchemy import SQLAlchemy

from app import settings
from app.helpers.celery import make_celery
from app.helpers.utils import get_closest_zoom
from app.helpers.utils import make_error_msg
from app.middleware import ReverseProxy

logger = logging.getLogger(__name__)

# TODO CLEAN_UP: Enable kombu pickle serializer that is used by Celery to
# serialize messages
registry.enable('pickle')

# Standard Flask application initialization

app = Flask(__name__)
app.config.from_object('app.settings')

# Setup the DB
db = SQLAlchemy(app)

# TODO CLEAN_UP: check if the reverse proxy is needed or not
# app.wsgi_app = ReverseProxy(app.wsgi_app, script_name='/')

# TODO CLEAN_UP: remove S3 second level caching if not needed
celery = make_celery(app)

# JINJA Configuration


# Jinja doesn't support by default the string split() method therefore add it
# here
@app.template_filter('split')
def split_filter(string, separator):
    return string.split(separator)


# register the get_closest_zoom as jinja filter which is used in the
# Get capabilities
app.jinja_env.filters['get_closest_zoom'] = get_closest_zoom
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True


# Add CORS Headers to all request
@app.after_request
def add_cors_and_cache_header(response):
    # only override cache-control when not present in response
    if not response.headers.get('Cache-Control'):
        if response.status_code == 200:
            cache_control = settings.DEFAULT_CACHE
        else:
            cache_control = settings.NO_CACHE
        response.headers.add('Cache-Control', cache_control)
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
    response.headers.add(
        'Access-Control-Allow-Headers',
        'Content-Type, Authorization, x-requested-with, Origin, Accept'
    )
    return response


# Register error handler to return an error based on the accept header
@app.errorhandler(HTTPException)
def handle_exception(error):
    logger.error(
        'Request failed code=%d description=%s', error.code, error.description
    )
    if 'Accept' in request.headers and 'text/html' in request.headers['Accept']:
        return error
    return make_error_msg(error.code, error.description)


# isort: off
from app import routes  # pylint: disable=wrong-import-position


def main():
    app.run()


if __name__ == '__main__':
    """
    Entrypoint for the application. At the moment, we do nothing specific, but
    there might be preparatory steps in the future
    """
    main()
