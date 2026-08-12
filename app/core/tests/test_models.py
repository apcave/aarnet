"""
Tests for models.
"""
from unittest.mock import patch
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from core import models


def create_user(email='user@example.com', password='password123'):
    """Helper function to create a user."""
    return get_user_model().objects.create_user(email, password)


class ModelTests(TestCase):
    """Test models."""

    def test_create_user_with_email_successful(self):
        """Test creating a new user with an email is successful."""
        email = 'test@example.com'
        password = 'testpass123'
        user = get_user_model().objects.create_user(
            email=email,
            password=password,
        )

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalized(self):
        """Test the email for a new user is normalized."""
        sample_emails = [
            ['test1@EXAMPLE.com', 'test1@example.com'],
            ['Test2@Example.com', 'Test2@example.com'],
            ['TEST3@EXAMPLE.COM', 'TEST3@example.com'],
            ['test4@example.COM',  'test4@example.com'],
        ]
        for email, expected in sample_emails:
            user = get_user_model().objects.create_user(email, 'sample123')
            self.assertEqual(user.email, expected)

    def test_new_user_without_email_raises_error(self):
        """Test creating user without email raises error."""
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user('', 'sample123')

    def test_create_superuser(self):
        """Test creating a new superuser."""
        user = get_user_model().objects.create_superuser(
            'test@example.com',
            'test123',
        )

        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_create_site(self):
        """Test creating a site."""
        user = get_user_model().objects.create_user(
            'test@example.com',
            'testpass123',
        )
        site = models.Site.objects.create(
            user=user,
            name='Satellite site',
            description='Primary site',
            status=models.SiteStatus.PLANNED,
        )

        self.assertEqual(str(site), site.name)
        self.assertEqual(site.get_status_display(), 'Planned')

    def test_create_network_with_sites(self):
        """Test creating a network with sites attached."""
        user = create_user()
        site = models.Site.objects.create(
            user=user,
            name='Edge site',
            description='Connected site',
            status=models.SiteStatus.ACTIVE,
        )
        network = models.Network.objects.create(
            user=user,
            title='Regional network',
            description='North region',
        )
        network.sites.add(site)

        self.assertEqual(str(network), network.title)
        self.assertEqual(network.sites.count(), 1)
        self.assertEqual(network.sites.first().name, 'Edge site')
