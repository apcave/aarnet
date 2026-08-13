"""
Database models.
"""
import uuid
import os

from django.conf import settings
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser, BaseUserManager, PermissionsMixin,
)

class UserManager(BaseUserManager):
    """Manager for users."""

    def create_user(self, email, password=None, **extra_fields):
        """Create, save and return a new user."""
        if not email:
            raise ValueError('Users must have an email address.')

        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password):
        """Create, save and return a new superuser."""
        user = self.create_user(email, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)

        return user


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model that supports using email instead of username."""
    email = models.EmailField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'


class SiteStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PLANNED = "planned", "Planned"
    DECOMMISSIONED = "decommissioned", "Decommissioned"


class Network(models.Model):
    """Network object."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title


class Site(models.Model):
    """Site to be used in networks."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    network = models.ForeignKey(
        Network,
        on_delete=models.CASCADE,
        related_name='sites',
    )
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=255,
        choices=SiteStatus.choices,
        default=SiteStatus.ACTIVE,
    )

    def __str__(self):
        return self.name


class Device(models.Model):
    """Device to be used in a site."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name='devices',
    )
    serial_number = models.CharField(max_length=255, unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['site', 'name'],
                name='unique_device_name_per_site',
            )
        ]

    def __str__(self):
        return self.name

class InterfaceStatus(models.TextChoices):
    UP = "up", "Up"
    DOWN = "down", "Down"
    MAINTENANCE = "maintenance", "Maintenance"

class Interface(models.Model):
    """Interface to be used in a device."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='interfaces',
    )
    speed = models.PositiveIntegerField()
    status = models.CharField(
        max_length=255,
        choices=InterfaceStatus.choices,
        default=InterfaceStatus.UP,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['device', 'name'],
                name='unique_interface_name_per_device',
            )
        ]

    def __str__(self):
        return f"{self.device.name} - {self.name}"

class ConnectionStatus(models.TextChoices):
    CONNECTED = "connected", "Connected"
    DISCONNECTED = "disconnected", "Disconnected"

class Connection(models.Model):
    """Connection between two interfaces."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    connection_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=255,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.DISCONNECTED,
    )

    start = models.ForeignKey(
        Interface,
        on_delete=models.CASCADE,
        related_name='connections_as_start',
    )
    end = models.ForeignKey(
        Interface,
        on_delete=models.CASCADE,
        related_name='connections_as_end',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['start', 'end'],
                name='unique_connection_between_interfaces',
            )
        ]

    def __str__(self):
        return f"{self.start} <-> {self.end}"