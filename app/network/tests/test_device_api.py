from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    Device,
    Interface,
    InterfaceStatus,
    Network,
    Site,
    SiteStatus,
)


class DeviceApiTests(TestCase):
    """Tests for the device endpoints."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="device-api@example.com",
            password="testpass123",
            name="Device API User",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_device_with_site(self):
        network = Network.objects.create(
            user=self.user,
            title="Device network",
            description="Network for devices",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Device site",
            description="Primary device site",
            status=SiteStatus.ACTIVE,
        )

        payload = {
            "name": "Router-1",
            "serial_number": "ABC-123",
            "site": site.id,
        }

        res = self.client.post(
            reverse("network:device-list"), payload, format="json"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["name"], "Router-1")
        self.assertEqual(res.data["site"], site.id)

    def test_device_crud_endpoints(self):
        network = Network.objects.create(
            user=self.user,
            title="Device CRUD network",
            description="CRUD network",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Device CRUD site",
            description="Site",
            status=SiteStatus.ACTIVE,
        )
        create_payload = {
            "site": site.id,
            "name": "Router-1",
            "serial_number": "SER-CRUD-1",
        }
        create_res = self.client.post(
            reverse("network:device-list"), create_payload, format="json"
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)

        device = Device.objects.get(id=create_res.data["id"])
        detail_url = reverse("network:device-detail", args=[device.id])

        get_res = self.client.get(detail_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["name"], "Router-1")

        put_res = self.client.put(
            detail_url,
            {
                "site": site.id,
                "name": "Router-2",
                "serial_number": "SER-CRUD-2",
            },
            format="json",
        )
        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        self.assertEqual(put_res.data["name"], "Router-2")

        patch_res = self.client.patch(
            detail_url, {"serial_number": "SER-CRUD-3"}, format="json"
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["serial_number"], "SER-CRUD-3")

        delete_res = self.client.delete(detail_url)
        self.assertEqual(delete_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Device.objects.filter(id=device.id).exists())

    def test_device_cannot_be_deleted_while_interfaces_are_attached(self):
        network = Network.objects.create(
            user=self.user,
            title="Protected device network",
            description="Network used for delete protection checks",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Protected device site",
            description="Site used for attach validation",
            status=SiteStatus.ACTIVE,
        )
        device = Device.objects.create(
            user=self.user,
            site=site,
            name="Protected device",
            serial_number="PROTECT-DEV-001",
        )
        Interface.objects.create(
            user=self.user,
            device=device,
            name="eth0",
            speed=1000,
            status=InterfaceStatus.UP,
        )

        res = self.client.delete(
            reverse("network:device-detail", args=[device.id])
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Device.objects.filter(id=device.id).exists())
        self.assertTrue(Interface.objects.filter(device=device).exists())

    def test_device_security_requires_authentication_for_all_methods(self):
        network = Network.objects.create(
            user=self.user,
            title="Device security network",
            description="Security network",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Device security site",
            description="Security site",
            status=SiteStatus.ACTIVE,
        )
        device = Device.objects.create(
            user=self.user,
            site=site,
            name="Security device",
            serial_number="SEC-DEV-001",
        )
        unauthenticated_client = APIClient()
        detail_url = reverse("network:device-detail", args=[device.id])

        self.assertEqual(
            unauthenticated_client.get(
                reverse("network:device-list")
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.post(
                reverse("network:device-list"),
                {
                    "site": site.id,
                    "name": "No auth device",
                    "serial_number": "SEC-DEV-002",
                },
                format="json",
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.get(detail_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.put(
                detail_url,
                {
                    "site": site.id,
                    "name": "Updated denied device",
                    "serial_number": "SEC-DEV-003",
                },
                format="json",
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.patch(
                detail_url, {"serial_number": "SEC-DEV-004"}, format="json"
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.delete(detail_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_device_name_must_be_unique_per_site(self):
        network = Network.objects.create(
            user=self.user,
            title="Duplicate device site network",
            description="Network used for device name validation",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Duplicate device site",
            description="Site for duplicate device checks",
            status=SiteStatus.ACTIVE,
        )
        original_device = Device.objects.create(
            user=self.user,
            site=site,
            name="Router-1",
            serial_number="DUP-DEV-ORIG",
        )
        detail_url = reverse(
            "network:device-detail", args=[original_device.id]
        )

        create_valid = self.client.post(
            reverse("network:device-list"),
            {
                "site": site.id,
                "name": "Router-2",
                "serial_number": "DUP-DEV-VALID",
            },
            format="json",
        )
        self.assertEqual(create_valid.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_valid.data["name"], "Router-2")

        create_duplicate = self.client.post(
            reverse("network:device-list"),
            {
                "site": site.id,
                "name": "Router-1",
                "serial_number": "DUP-DEV-DUPLICATE",
            },
            format="json",
        )
        self.assertEqual(
            create_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(
            Device.objects.filter(site=site, name="Router-1").count(), 1
        )

        put_valid = self.client.put(
            detail_url,
            {
                "site": site.id,
                "name": "Router-3",
                "serial_number": "DUP-DEV-UPDATED",
            },
            format="json",
        )
        self.assertEqual(put_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(put_valid.data["name"], "Router-3")

        put_duplicate = self.client.put(
            detail_url,
            {
                "site": site.id,
                "name": "Router-2",
                "serial_number": "DUP-DEV-INVALID-UPDATE",
            },
            format="json",
        )
        self.assertEqual(
            put_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )
        original_device.refresh_from_db()
        self.assertEqual(original_device.name, "Router-3")

        patch_valid = self.client.patch(
            detail_url, {"name": "Router-4"}, format="json"
        )
        self.assertEqual(patch_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_valid.data["name"], "Router-4")

        patch_duplicate = self.client.patch(
            detail_url, {"name": "Router-2"}, format="json"
        )
        self.assertEqual(
            patch_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )
        original_device.refresh_from_db()
        self.assertEqual(original_device.name, "Router-4")

    def test_device_serial_number_must_be_unique_across_all_devices(self):
        network = Network.objects.create(
            user=self.user,
            title="Duplicate serial network",
            description="Network for serial validation",
        )
        first_site = Site.objects.create(
            user=self.user,
            network=network,
            name="First serial site",
            description="First site",
            status=SiteStatus.ACTIVE,
        )
        second_site = Site.objects.create(
            user=self.user,
            network=network,
            name="Second serial site",
            description="Second site",
            status=SiteStatus.ACTIVE,
        )
        original_device = Device.objects.create(
            user=self.user,
            site=first_site,
            name="Router-serial-1",
            serial_number="SERIAL-UNIQUE-001",
        )
        detail_url = reverse(
            "network:device-detail", args=[original_device.id]
        )

        create_valid = self.client.post(
            reverse("network:device-list"),
            {
                "site": second_site.id,
                "name": "Router-serial-2",
                "serial_number": "SERIAL-UNIQUE-002",
            },
            format="json",
        )
        self.assertEqual(create_valid.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            create_valid.data["serial_number"], "SERIAL-UNIQUE-002"
        )

        create_duplicate = self.client.post(
            reverse("network:device-list"),
            {
                "site": second_site.id,
                "name": "Router-serial-3",
                "serial_number": "SERIAL-UNIQUE-001",
            },
            format="json",
        )
        self.assertEqual(
            create_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(
            Device.objects.filter(serial_number="SERIAL-UNIQUE-001").count(), 1
        )

        put_valid = self.client.put(
            detail_url,
            {
                "site": second_site.id,
                "name": "Router-serial-4",
                "serial_number": "SERIAL-UNIQUE-003",
            },
            format="json",
        )
        self.assertEqual(put_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(put_valid.data["serial_number"], "SERIAL-UNIQUE-003")

        put_duplicate = self.client.put(
            detail_url,
            {
                "site": second_site.id,
                "name": "Router-serial-5",
                "serial_number": "SERIAL-UNIQUE-002",
            },
            format="json",
        )
        self.assertEqual(
            put_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )
        original_device.refresh_from_db()
        self.assertEqual(original_device.serial_number, "SERIAL-UNIQUE-003")

        patch_valid = self.client.patch(
            detail_url, {"serial_number": "SERIAL-UNIQUE-004"}, format="json"
        )
        self.assertEqual(patch_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(
            patch_valid.data["serial_number"], "SERIAL-UNIQUE-004"
        )

        patch_duplicate = self.client.patch(
            detail_url, {"serial_number": "SERIAL-UNIQUE-002"}, format="json"
        )
        self.assertEqual(
            patch_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )
        original_device.refresh_from_db()
        self.assertEqual(original_device.serial_number, "SERIAL-UNIQUE-004")

    def test_device_invalid_site_is_rejected_on_create_update_and_patch(self):
        network = Network.objects.create(
            user=self.user,
            title="Invalid device site network",
            description="Invalid site test network",
        )
        valid_site = Site.objects.create(
            user=self.user,
            network=network,
            name="Valid site",
            description="Valid site for device tests",
            status=SiteStatus.ACTIVE,
        )
        device = Device.objects.create(
            user=self.user,
            site=valid_site,
            name="Original device",
            serial_number="ORIG-DEV-1",
        )
        detail_url = reverse("network:device-detail", args=[device.id])

        create_success = self.client.post(
            reverse("network:device-list"),
            {
                "site": valid_site.id,
                "name": "Valid site device",
                "serial_number": "GOOD-SITE-1",
            },
            format="json",
        )
        self.assertEqual(create_success.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_success.data["site"], valid_site.id)
        self.assertEqual(create_success.data["name"], "Valid site device")

        create_res = self.client.post(
            reverse("network:device-list"),
            {
                "site": 999999,
                "name": "Bad site device",
                "serial_number": "BAD-SITE-1",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            Device.objects.filter(serial_number="BAD-SITE-1").exists()
        )

        put_success = self.client.put(
            detail_url,
            {
                "site": valid_site.id,
                "name": "Updated valid device",
                "serial_number": "UPDATED-GOOD-SITE",
            },
            format="json",
        )
        self.assertEqual(put_success.status_code, status.HTTP_200_OK)
        self.assertEqual(put_success.data["site"], valid_site.id)
        self.assertEqual(put_success.data["name"], "Updated valid device")

        put_res = self.client.put(
            detail_url,
            {
                "site": 999999,
                "name": "Updated device",
                "serial_number": "UPDATED-BAD-SITE",
            },
            format="json",
        )
        self.assertEqual(put_res.status_code, status.HTTP_400_BAD_REQUEST)
        device.refresh_from_db()
        self.assertEqual(device.name, "Updated valid device")
        self.assertEqual(device.serial_number, "UPDATED-GOOD-SITE")

        patch_success = self.client.patch(
            detail_url,
            {"site": valid_site.id, "name": "Patched valid device"},
            format="json",
        )
        self.assertEqual(patch_success.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_success.data["site"], valid_site.id)
        self.assertEqual(patch_success.data["name"], "Patched valid device")

        patch_res = self.client.patch(
            detail_url, {"site": 999999}, format="json"
        )
        self.assertEqual(patch_res.status_code, status.HTTP_400_BAD_REQUEST)
        device.refresh_from_db()
        self.assertEqual(device.site_id, valid_site.id)
        self.assertEqual(device.name, "Patched valid device")
