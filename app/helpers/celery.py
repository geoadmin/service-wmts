from celery import Celery
from celery.signals import setup_logging

from app import settings
from app.helpers.logging_utils import init_logging


@setup_logging.connect
def on_setup_logging(**kwargs):
    '''Initialize logging for celery worker
    '''
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
        broker=f'amqp://{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}'
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
