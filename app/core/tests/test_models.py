"""
Tests for models.
"""
from django.db import IntegrityError
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
        network = models.Network.objects.create(
            user=user,
            title='Satellite network',
            description='Network for satellite site',
        )
        site = models.Site.objects.create(
            user=user,
            network=network,
            name='Satellite site',
            description='Primary site',
            status=models.SiteStatus.PLANNED,
        )

        self.assertEqual(str(site), site.name)
        self.assertEqual(site.get_status_display(), 'Planned')

    def test_create_network_with_sites(self):
        """Test creating a network with sites attached."""
        user = create_user()
        network = models.Network.objects.create(
            user=user,
            title='Regional network',
            description='North region',
        )
        site = models.Site.objects.create(
            user=user,
            network=network,
            name='Edge site',
            description='Connected site',
            status=models.SiteStatus.ACTIVE,
        )
        network.sites.add(site)

        self.assertEqual(str(network), network.title)
        self.assertEqual(network.sites.count(), 1)
        self.assertEqual(network.sites.first().name, 'Edge site')

    def test_create_device_interface_and_connection(self):
        """Test creating a device, interface, and connection."""
        user = create_user('device@example.com')
        network = models.Network.objects.create(
            user=user,
            title='Core network',
            description='Main network',
        )
        site = models.Site.objects.create(
            user=user,
            network=network,
            name='HQ site',
            description='Primary site',
            status=models.SiteStatus.ACTIVE,
        )
        device = models.Device.objects.create(
            user=user,
            site=site,
            name='Router-1',
            serial_number='SER-001',
        )
        interface = models.Interface.objects.create(
            user=user,
            device=device,
            name='eth0',
            speed=1000,
            status=models.InterfaceStatus.UP,
        )
        connection = models.Connection.objects.create(
            user=user,
            start=interface,
            end=interface,
            status=models.ConnectionStatus.CONNECTED,
        )

        self.assertEqual(str(device), 'Router-1')
        self.assertEqual(str(interface), 'Router-1 - eth0')
        self.assertEqual(str(connection), f'{interface} <-> {interface}')

    def test_device_name_is_unique_per_site(self):
        """Test duplicate device names are not allowed within the same site."""
        user = create_user('duplicate-device@example.com')
        network = models.Network.objects.create(
            user=user,
            title='Duplicate network',
            description='Test network',
        )
        site = models.Site.objects.create(
            user=user,
            network=network,
            name='Duplicate site',
            description='A site with duplicate devices',
            status=models.SiteStatus.ACTIVE,
        )

        models.Device.objects.create(
            user=user,
            site=site,
            name='Router-1',
            serial_number='SER-100',
        )

        with self.assertRaises(IntegrityError):
            models.Device.objects.create(
                user=user,
                site=site,
                name='Router-1',
                serial_number='SER-101',
            )

    def test_interface_name_may_repeat_across_devices(self):
        """Test the same interface name can be used on different devices."""
        user = create_user('iface-repeat@example.com')
        network = models.Network.objects.create(
            user=user,
            title='Interface network',
            description='Network using repeated interface names',
        )
        site = models.Site.objects.create(
            user=user,
            network=network,
            name='Interface site',
            description='Site with multiple devices',
            status=models.SiteStatus.ACTIVE,
        )
        device_1 = models.Device.objects.create(
            user=user,
            site=site,
            name='Router-A',
            serial_number='SER-A',
        )
        device_2 = models.Device.objects.create(
            user=user,
            site=site,
            name='Router-B',
            serial_number='SER-B',
        )

        models.Interface.objects.create(
            user=user,
            device=device_1,
            name='eth0',
            speed=1000,
        )
        interface_2 = models.Interface.objects.create(
            user=user,
            device=device_2,
            name='eth0',
            speed=1000,
        )

        self.assertEqual(interface_2.name, 'eth0')
        self.assertNotEqual(device_1.id, device_2.id)

    def test_connection_cannot_be_created_twice_for_same_pair(self):
        """Test duplicate interface-to-interface connections are blocked."""
        user = create_user('connection@example.com')
        network = models.Network.objects.create(
            user=user,
            title='Connection network',
            description='Test link rules',
        )
        site = models.Site.objects.create(
            user=user,
            network=network,
            name='Connection site',
            description='Site for connections',
            status=models.SiteStatus.ACTIVE,
        )
        device_1 = models.Device.objects.create(
            user=user,
            site=site,
            name='Switch-1',
            serial_number='SW-1',
        )
        device_2 = models.Device.objects.create(
            user=user,
            site=site,
            name='Switch-2',
            serial_number='SW-2',
        )
        start = models.Interface.objects.create(
            user=user,
            device=device_1,
            name='eth1',
            speed=1000,
        )
        end = models.Interface.objects.create(
            user=user,
            device=device_2,
            name='eth1',
            speed=1000,
        )

        models.Connection.objects.create(
            user=user,
            start=start,
            end=end,
        )

        with self.assertRaises(IntegrityError):
            models.Connection.objects.create(
                user=user,
                start=start,
                end=end,
            )
