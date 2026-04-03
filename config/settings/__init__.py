import os

DJANGO_ENV = os.environ.get('DJANGO_ENV', 'development').strip().lower()

if DJANGO_ENV == 'production':
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
