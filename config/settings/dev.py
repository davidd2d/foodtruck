from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']
INTERNAL_IPS = ['127.0.0.1']

# Celery: execute tasks synchronously in development (no separate worker needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

