# This files contains the Flask Application default settings

CACHE_TYPE = "SimpleCache"
CACHE_DEFAULT_TIMEOUT = 300

CELERY_TASK_SERIALIZER = 'pickle'
CELERY_RESULT_SERIALIZER = 'pickle'
CELERY_ACCEPT_CONTENT = ['pickle']
