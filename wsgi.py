"""
The gevent monkey import and patch suppress a warning, and a potential problem.
Gunicorn would call it anyway, but if it tries to call it after the ssl module
has been initialized in another module (like, in our code, by the botocore
library), then it could lead to inconsistencies in how the ssl module is used.
Thus we patch the ssl module through gevent.monkey.patch_all before any other
import, especially the app import, which would cause the boto module to be
loaded, which would in turn load the ssl module.
"""
# pylint: disable=wrong-import-position,wrong-import-order
import gevent.monkey

gevent.monkey.patch_all()

import os

from gunicorn.app.base import BaseApplication

from app import app as application
from app.helpers.logging_utils import get_logging_cfg
from app.helpers.wmts_config import init_wmts_config


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


def on_starting(server):
    # We initialize the wmts config here to do it only once, but only when
    # the logging has been configured. If we do it in the app.__init__.py module
    # the we don't have the logging yet configured and we don't get any logs
    init_wmts_config()


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
        'access_log_format':
            '%(h)s %(l)s %(u)s "%(r)s" %(s)s %(B)s Bytes '
            '"%(f)s" "%(a)s" %(L)ss',
        'logconfig_dict': get_logging_cfg(),
        'on_starting': on_starting
    }
    StandaloneApplication(application, options).run()
