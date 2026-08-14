from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    Connection,
    Device,
    Interface,
    InterfaceStatus,
    Network,
    Site,
    SiteStatus,
)


class EndpointSecurityTests(TestCase):
    """Ensure all authenticated-only CRUD endpoints reject
    unauthenticated access."""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="security-user@example.com",
            password="testpass123",
            name="Security User",
        )

    def assert_401_for_all_methods(
        self, list_url, detail_url, payload=None, detail_payload=None
    ):
        self.assertEqual(
            self.client.get(list_url).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self.client.post(
                list_url, payload or {}, format="json"
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get(detail_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.put(
                detail_url, detail_payload or payload or {}, format="json"
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.patch(
                detail_url, detail_payload or payload or {}, format="json"
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.delete(detail_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_network_endpoints_require_authentication_on_all_methods(self):
        network = Network.objects.create(
            user=self.user,
            title="Security network",
            description="Network security check",
        )
        self.assert_401_for_all_methods(
            reverse("network:network-list"),
            reverse("network:network-detail", args=[network.id]),
            payload={
                "title": "No auth network",
                "description": "Should fail without auth",
            },
            detail_payload={
                "title": "Updated no auth network",
                "description": "Should fail without auth",
                "sites": [],
            },
        )

    def test_site_endpoints_require_authentication_on_all_methods(self):
        network = Network.objects.create(
            user=self.user,
            title="Site security network",
            description="Security network",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Security site",
            description="Site security check",
            status=SiteStatus.ACTIVE,
        )
        self.assert_401_for_all_methods(
            reverse("network:site-list"),
            reverse("network:site-detail", args=[site.id]),
            payload={
                "network": network.id,
                "name": "No auth site",
                "description": "Should fail without auth",
                "status": SiteStatus.PLANNED,
            },
            detail_payload={
                "network": network.id,
                "name": "Updated no auth site",
                "description": "Should fail without auth",
                "status": SiteStatus.ACTIVE,
            },
        )

    def test_device_endpoints_require_authentication_on_all_methods(self):
        network = Network.objects.create(
            user=self.user,
            title="Device security network",
            description="Security network",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Device security site",
            description="Site security check",
            status=SiteStatus.ACTIVE,
        )
        device = Device.objects.create(
            user=self.user,
            site=site,
            name="Security device",
            serial_number="SEC-DEV-001",
        )
        self.assert_401_for_all_methods(
            reverse("network:device-list"),
            reverse("network:device-detail", args=[device.id]),
            payload={
                "site": site.id,
                "name": "No auth device",
                "serial_number": "SEC-DEV-002",
            },
            detail_payload={
                "site": site.id,
                "name": "Updated no auth device",
                "serial_number": "SEC-DEV-003",
            },
        )

    def test_interface_endpoints_require_authentication_on_all_methods(self):
        network = Network.objects.create(
            user=self.user,
            title="Interface security network",
            description="Security network",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Interface security site",
            description="Site security check",
            status=SiteStatus.ACTIVE,
        )
        device = Device.objects.create(
            user=self.user,
            site=site,
            name="Interface security device",
            serial_number="SEC-IFACE-001",
        )
        iface = Interface.objects.create(
            user=self.user,
            device=device,
            name="eth0",
            speed=1000,
            status=InterfaceStatus.UP,
        )
        self.assert_401_for_all_methods(
            reverse("network:interface-list"),
            reverse("network:interface-detail", args=[iface.id]),
            payload={
                "device": device.id,
                "name": "eth99",
                "speed": 1000,
                "status": InterfaceStatus.UP,
            },
            detail_payload={
                "device": device.id,
                "name": "eth1",
                "speed": 2000,
                "status": InterfaceStatus.DOWN,
            },
        )

    def test_connection_endpoints_require_authentication_on_all_methods(self):
        network = Network.objects.create(
            user=self.user,
            title="Connection security network",
            description="Security network",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Connection security site",
            description="Site security check",
            status=SiteStatus.ACTIVE,
        )
        device = Device.objects.create(
            user=self.user,
            site=site,
            name="Connection security device",
            serial_number="SEC-CONN-001",
        )
        start = Interface.objects.create(
            user=self.user,
            device=device,
            name="eth0",
            speed=1000,
            status=InterfaceStatus.UP,
        )
        end = Interface.objects.create(
            user=self.user,
            device=device,
            name="eth1",
            speed=1000,
            status=InterfaceStatus.UP,
        )
        connection = Connection.objects.create(
            user=self.user,
            name="security-connection",
            status="connected",
            start=start,
            end=end,
        )
        self.assert_401_for_all_methods(
            reverse("network:connection-list"),
            reverse("network:connection-detail", args=[connection.id]),
            payload={
                "name": "no-auth-connection",
                "status": "connected",
                "start": start.id,
                "end": end.id,
            },
            detail_payload={
                "name": "updated-no-auth-connection",
                "status": "disconnected",
                "start": start.id,
                "end": end.id,
            },
        )

    def test_nested_connection_endpoints_require_authentication_on_all_methods(
        self,
    ):
        network = Network.objects.create(
            user=self.user,
            title="Nested connection security network",
            description="Nested security network",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Nested security site",
            description="Site security check",
            status=SiteStatus.ACTIVE,
        )
        device = Device.objects.create(
            user=self.user,
            site=site,
            name="Nested security device",
            serial_number="SEC-NEST-001",
        )
        start = Interface.objects.create(
            user=self.user,
            device=device,
            name="eth0",
            speed=1000,
            status=InterfaceStatus.UP,
        )
        end = Interface.objects.create(
            user=self.user,
            device=device,
            name="eth1",
            speed=1000,
            status=InterfaceStatus.UP,
        )
        connection = Connection.objects.create(
            user=self.user,
            name="nested-security-connection",
            status="connected",
            start=start,
            end=end,
        )
        self.assert_401_for_all_methods(
            reverse("network:connection-full-list"),
            reverse("network:connection-full-detail", args=[connection.id]),
            payload={
                "name": "nested-no-auth",
                "status": "connected",
                "start": {
                    "network": {"title": "N", "description": "N desc"},
                    "site": {
                        "name": "A",
                        "description": "A desc",
                        "status": "active",
                    },
                    "device": {"name": "D1", "serial_number": "SER-1"},
                    "interface": {
                        "name": "eth0",
                        "speed": 1000,
                        "status": "up",
                    },
                },
                "end": {
                    "network": {"title": "M", "description": "M desc"},
                    "site": {
                        "name": "B",
                        "description": "B desc",
                        "status": "active",
                    },
                    "device": {"name": "D2", "serial_number": "SER-2"},
                    "interface": {
                        "name": "eth1",
                        "speed": 1000,
                        "status": "up",
                    },
                },
            },
            detail_payload={
                "name": "nested-updated-no-auth",
                "status": "disconnected",
                "start": {
                    "network": {"title": "N", "description": "N desc"},
                    "site": {
                        "name": "A",
                        "description": "A desc",
                        "status": "active",
                    },
                    "device": {"name": "D1", "serial_number": "SER-1"},
                    "interface": {
                        "name": "eth0",
                        "speed": 1000,
                        "status": "up",
                    },
                },
                "end": {
                    "network": {"title": "M", "description": "M desc"},
                    "site": {
                        "name": "B",
                        "description": "B desc",
                        "status": "active",
                    },
                    "device": {"name": "D2", "serial_number": "SER-2"},
                    "interface": {
                        "name": "eth1",
                        "speed": 1000,
                        "status": "up",
                    },
                },
            },
        )
