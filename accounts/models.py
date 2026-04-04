from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email).lower()
        extra_fields.setdefault('is_customer', True)
        user = self.model(email=email, **extra_fields)
        user.username = email  # Set username to email since USERNAME_FIELD = 'email'
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_customer', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model for the food truck platform.

    Uses email as the unique identifier for authentication while supporting
    explicit role flags required by the SaaS platform.
    """
    email = models.EmailField('email address', unique=True)
    email_verified = models.BooleanField(default=False, help_text=_("Whether the email is verified"))
    is_foodtruck_owner = models.BooleanField(
        default=False,
        help_text=_("Whether the user owns or manages food trucks")
    )
    is_customer = models.BooleanField(
        default=True,
        help_text=_("Whether the user places orders")
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def __str__(self):
        return self.email

    def can_manage_foodtruck(self, foodtruck):
        """
        Determine whether this user can manage the provided food truck.
        """
        if not hasattr(foodtruck, 'owner_id'):
            return False
        return self.is_foodtruck_owner and foodtruck.owner_id == self.pk
