import logging

from werkzeug.exceptions import HTTPException

from flask import Flask

from app.helpers import ALLOWED_DOMAINS_PATTERN
from app.helpers import make_error_msg
from app.middleware import ReverseProxy

logger = logging.getLogger(__name__)

# Standard Flask application initialization

app = Flask(__name__)
app.wsgi_app = ReverseProxy(app.wsgi_app, script_name='/')


# Add CORS Headers to all request
@app.after_request
def add_cors_header(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Methods', 'GET, HEAD')
    response.headers.add(
        'Access-Control-Allow-Headers',
        'Content-Type, Authorization, x-requested-with, Origin, Accept'
    )
    return response


# Register error handler to make sure that every error returns a json answer
@app.errorhandler(HTTPException)
def handle_exception(err):
    """Return JSON instead of HTML for HTTP errors."""
    logger.error(
        'Request failed code=%d description=%s', err.code, err.description
    )
    return make_error_msg(err.code, err.description)


from app import routes  # pylint: disable=wrong-import-position


def main():
    app.run()


if __name__ == '__main__':
    """
    Entrypoint for the application. At the moment, we do nothing specific, but
    there might be preparatory steps in the future
    """
    main()
