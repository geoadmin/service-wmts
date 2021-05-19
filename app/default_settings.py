# This files contains the Flask Application default settings

# TODO CLEAN_UP: remove S3 second level caching if not needed
CELERY_TASK_SERIALIZER = 'pickle'
CELERY_RESULT_SERIALIZER = 'pickle'
CELERY_ACCEPT_CONTENT = ['pickle']
