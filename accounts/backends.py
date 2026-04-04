from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveModelBackend(ModelBackend):
    """Authenticate on email/username case-insensitively."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is not None:
            username = username.strip().lower()
        return super().authenticate(request, username=username, password=password, **kwargs)
