import os

from celery import Celery
from celery.signals import setup_logging
from celery.utils.log import get_task_logger

from app.helpers import init_logging

logger = get_task_logger(__name__)


@setup_logging.connect
def on_setup_logging(**kwargs):
    init_logging()


def make_celery(app):
    '''Initialize Celery to work with the Flask app

    Args:
        app: Flask
            Flask app instance

    Returns: Celery
        Celery instance
    '''
    my_celery = Celery(
        app.import_name,
        broker='amqp://localhost:%s' % os.getenv('RABBITMQ_PORT')
    )
    my_celery.conf.update(app.config)

    TaskBase = my_celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    my_celery.Task = ContextTask
    return my_celery
