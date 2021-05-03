import os

from gunicorn.app.base import BaseApplication

from app import app as application
from app.helpers import get_logging_cfg


class StandaloneApplication(BaseApplication):
    # pylint: disable=abstract-method

    # pylint: disable=redefined-outer-name
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key,
            value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


# We use the port 9000 as default, otherwise we set the HTTP_PORT env variable
# within the container.
if __name__ == '__main__':
    WMTS_PORT = str(os.environ.get('WMTS_PORT', "9000"))
    # Bind to 0.0.0.0 to let your app listen to all network interfaces.
    options = {
        'bind': '%s:%s' % ('0.0.0.0', WMTS_PORT),
        'worker_class': 'gevent',
        'workers': 2,  # scaling horizontally is left to Kubernetes
        'timeout': 60,
        'logconfig_dict': get_logging_cfg()
    }
    StandaloneApplication(application, options).run()
