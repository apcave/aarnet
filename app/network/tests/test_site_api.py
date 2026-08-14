from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Device, Network, Site, SiteStatus


class SiteApiTests(TestCase):
    """Tests for the site endpoints."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="site-api@example.com",
            password="testpass123",
            name="Site API User",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_site_with_status(self):
        network = Network.objects.create(
            user=self.user,
            title="Primary network",
            description="Main network",
        )
        payload = {
            "network": network.id,
            "name": "Edge site",
            "description": "Primary edge site",
            "status": SiteStatus.PLANNED,
        }

        res = self.client.post(
            reverse("network:site-list"), payload, format="json"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], SiteStatus.PLANNED)
        self.assertEqual(res.data["name"], "Edge site")

    def test_list_sites_for_authenticated_user(self):
        network = Network.objects.create(
            user=self.user,
            title="Alpha network",
            description="Alpha network",
        )
        Site.objects.create(
            user=self.user,
            network=network,
            name="Alpha",
            description="Alpha site",
            status=SiteStatus.ACTIVE,
        )
        Site.objects.create(
            user=self.user,
            network=network,
            name="Beta",
            description="Beta site",
            status=SiteStatus.DECOMMISSIONED,
        )

        res = self.client.get(reverse("network:site-list"))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)

    def test_site_crud_endpoints(self):
        network = Network.objects.create(
            user=self.user,
            title="Site CRUD network",
            description="CRUD network",
        )
        create_payload = {
            "network": network.id,
            "name": "HQ site",
            "description": "HQ site description",
            "status": SiteStatus.ACTIVE,
        }
        create_res = self.client.post(
            reverse("network:site-list"), create_payload, format="json"
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)

        site = Site.objects.get(id=create_res.data["id"])
        detail_url = reverse("network:site-detail", args=[site.id])

        get_res = self.client.get(detail_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["name"], "HQ site")

        put_res = self.client.put(
            detail_url,
            {
                "network": network.id,
                "name": "HQ site updated",
                "description": "Updated site description",
                "status": SiteStatus.PLANNED,
            },
            format="json",
        )
        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        self.assertEqual(put_res.data["name"], "HQ site updated")

        patch_res = self.client.patch(
            detail_url,
            {"description": "Patched site description"},
            format="json",
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            patch_res.data["description"], "Patched site description"
        )

        delete_res = self.client.delete(detail_url)
        self.assertEqual(delete_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Site.objects.filter(id=site.id).exists())

    def test_site_name_must_be_unique_per_network(self):
        network = Network.objects.create(
            user=self.user,
            title="Duplicate site network",
            description="Network used for duplicate site checks",
        )
        original = Site.objects.create(
            user=self.user,
            network=network,
            name="Duplicate site",
            description="Original site",
            status=SiteStatus.ACTIVE,
        )
        detail_url = reverse("network:site-detail", args=[original.id])

        create_valid = self.client.post(
            reverse("network:site-list"),
            {
                "network": network.id,
                "name": "Unique site",
                "description": "Valid site",
                "status": SiteStatus.PLANNED,
            },
            format="json",
        )
        self.assertEqual(create_valid.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_valid.data["name"], "Unique site")

        create_duplicate = self.client.post(
            reverse("network:site-list"),
            {
                "network": network.id,
                "name": "Duplicate site",
                "description": "Duplicate attempt",
                "status": SiteStatus.ACTIVE,
            },
            format="json",
        )
        self.assertEqual(
            create_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(
            Site.objects.filter(
                network=network, name="Duplicate site"
            ).count(),
            1,
        )

        put_valid = self.client.put(
            detail_url,
            {
                "network": network.id,
                "name": "Updated site name",
                "description": "Updated description",
                "status": SiteStatus.PLANNED,
            },
            format="json",
        )
        self.assertEqual(put_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(put_valid.data["name"], "Updated site name")

        put_duplicate = self.client.put(
            detail_url,
            {
                "network": network.id,
                "name": "Unique site",
                "description": "Trying to duplicate a site name",
                "status": SiteStatus.ACTIVE,
            },
            format="json",
        )
        self.assertEqual(
            put_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )
        original.refresh_from_db()
        self.assertEqual(original.name, "Updated site name")

        patch_valid = self.client.patch(
            detail_url, {"name": "Patched site name"}, format="json"
        )
        self.assertEqual(patch_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_valid.data["name"], "Patched site name")

        patch_duplicate = self.client.patch(
            detail_url, {"name": "Unique site"}, format="json"
        )
        self.assertEqual(
            patch_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )
        original.refresh_from_db()
        self.assertEqual(original.name, "Patched site name")

    def test_site_status_must_be_one_of_the_allowed_choices(self):
        network = Network.objects.create(
            user=self.user,
            title="Site status validation network",
            description="Network for site status validation",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Base site status test",
            description="Seed site",
            status=SiteStatus.ACTIVE,
        )
        detail_url = reverse("network:site-detail", args=[site.id])

        create_valid = self.client.post(
            reverse("network:site-list"),
            {
                "network": network.id,
                "name": "Valid planned site",
                "description": "Valid status",
                "status": SiteStatus.PLANNED,
            },
            format="json",
        )
        self.assertEqual(create_valid.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_valid.data["status"], SiteStatus.PLANNED)

        create_invalid_value = self.client.post(
            reverse("network:site-list"),
            {
                "network": network.id,
                "name": "Invalid status site",
                "description": "Not an allowed status",
                "status": "offline",
            },
            format="json",
        )
        self.assertEqual(
            create_invalid_value.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertFalse(
            Site.objects.filter(
                network=network, name="Invalid status site"
            ).exists()
        )

        create_null_status = self.client.post(
            reverse("network:site-list"),
            {
                "network": network.id,
                "name": "Null status site",
                "description": "Null status should fail",
                "status": None,
            },
            format="json",
        )
        self.assertEqual(
            create_null_status.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertFalse(
            Site.objects.filter(
                network=network, name="Null status site"
            ).exists()
        )

        put_valid = self.client.put(
            detail_url,
            {
                "network": network.id,
                "name": "Updated valid site",
                "description": "Status valid update",
                "status": SiteStatus.DECOMMISSIONED,
            },
            format="json",
        )
        self.assertEqual(put_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(put_valid.data["status"], SiteStatus.DECOMMISSIONED)

        put_invalid_value = self.client.put(
            detail_url,
            {
                "network": network.id,
                "name": "Rejected site",
                "description": "Invalid status value",
                "status": "retired",
            },
            format="json",
        )
        self.assertEqual(
            put_invalid_value.status_code, status.HTTP_400_BAD_REQUEST
        )
        site.refresh_from_db()
        self.assertEqual(site.status, SiteStatus.DECOMMISSIONED)

        put_null_status = self.client.put(
            detail_url,
            {
                "network": network.id,
                "name": "Null status update site",
                "description": "Null should fail",
                "status": None,
            },
            format="json",
        )
        self.assertEqual(
            put_null_status.status_code, status.HTTP_400_BAD_REQUEST
        )
        site.refresh_from_db()
        self.assertEqual(site.name, "Updated valid site")

        patch_valid = self.client.patch(
            detail_url, {"status": SiteStatus.ACTIVE}, format="json"
        )
        self.assertEqual(patch_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_valid.data["status"], SiteStatus.ACTIVE)

        patch_invalid_value = self.client.patch(
            detail_url, {"status": "suspended"}, format="json"
        )
        self.assertEqual(
            patch_invalid_value.status_code, status.HTTP_400_BAD_REQUEST
        )
        site.refresh_from_db()
        self.assertEqual(site.status, SiteStatus.ACTIVE)

        patch_null_status = self.client.patch(
            detail_url, {"status": None}, format="json"
        )
        self.assertEqual(
            patch_null_status.status_code, status.HTTP_400_BAD_REQUEST
        )
        site.refresh_from_db()
        self.assertEqual(site.status, SiteStatus.ACTIVE)

    def test_site_cannot_be_deleted_while_devices_are_attached(self):
        network = Network.objects.create(
            user=self.user,
            title="Protected site network",
            description="Network used for site delete protection checks",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Protected site",
            description="Site to protect from deletion",
            status=SiteStatus.ACTIVE,
        )
        Device.objects.create(
            user=self.user,
            site=site,
            name="Protected router",
            serial_number="PROTECT-SITE-001",
        )

        res = self.client.delete(
            reverse("network:site-detail", args=[site.id])
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Site.objects.filter(id=site.id).exists())
        self.assertTrue(Device.objects.filter(site=site).exists())

    def test_site_security_requires_authentication_for_all_methods(self):
        network = Network.objects.create(
            user=self.user,
            title="Site security network",
            description="Security network",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Site security check",
            description="Site check",
            status=SiteStatus.ACTIVE,
        )
        unauthenticated_client = APIClient()
        detail_url = reverse("network:site-detail", args=[site.id])

        self.assertEqual(
            unauthenticated_client.get(
                reverse("network:site-list")
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.post(
                reverse("network:site-list"),
                {
                    "network": network.id,
                    "name": "No auth site",
                    "description": "No auth",
                    "status": SiteStatus.PLANNED,
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
                    "network": network.id,
                    "name": "Updated denied site",
                    "description": "No auth",
                    "status": SiteStatus.ACTIVE,
                },
                format="json",
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.patch(
                detail_url, {"description": "No auth"}, format="json"
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.delete(detail_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
