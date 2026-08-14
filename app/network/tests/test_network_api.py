from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Network, Site, SiteStatus


class NetworkApiTests(TestCase):
    """Tests for the network endpoints."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="network-api@example.com",
            password="testpass123",
            name="Network API User",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_network_with_sites(self):
        network = Network.objects.create(
            user=self.user,
            title="Parent network",
            description="Parent network",
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name="Gateway",
            description="Gateway site",
            status=SiteStatus.ACTIVE,
        )

        payload = {
            "title": "Regional network",
            "description": "Core region",
            "sites": [site.id],
        }

        res = self.client.post(
            reverse("network:network-list"), payload, format="json"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["title"], "Regional network")
        self.assertEqual(
            Network.objects.get(id=res.data["id"]).sites.count(), 1
        )

    def test_network_crud_endpoints(self):
        create_payload = {
            "title": "CRUD network",
            "description": "Network for CRUD",
        }
        create_res = self.client.post(
            reverse("network:network-list"), create_payload, format="json"
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)

        network = Network.objects.get(id=create_res.data["id"])
        detail_url = reverse("network:network-detail", args=[network.id])

        get_res = self.client.get(detail_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["title"], "CRUD network")

        put_res = self.client.put(
            detail_url,
            {
                "title": "Updated network",
                "description": "Updated description",
                "sites": [],
            },
            format="json",
        )
        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        self.assertEqual(put_res.data["title"], "Updated network")

        patch_res = self.client.patch(
            detail_url, {"description": "Patched description"}, format="json"
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["description"], "Patched description")

        delete_res = self.client.delete(detail_url)
        self.assertEqual(delete_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Network.objects.filter(id=network.id).exists())

    def test_network_title_must_be_unique(self):
        first_network = Network.objects.create(
            user=self.user,
            title="Unique network title",
            description="Original network",
        )
        detail_url = reverse("network:network-detail", args=[first_network.id])

        create_valid = self.client.post(
            reverse("network:network-list"),
            {
                "title": "Another valid network",
                "description": "Valid creation path",
            },
            format="json",
        )
        self.assertEqual(create_valid.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_valid.data["title"], "Another valid network")

        create_duplicate = self.client.post(
            reverse("network:network-list"),
            {
                "title": "Unique network title",
                "description": "Duplicate title",
            },
            format="json",
        )
        self.assertEqual(
            create_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(
            Network.objects.filter(title="Unique network title").count(), 1
        )

        put_valid = self.client.put(
            detail_url,
            {
                "title": "Updated network title",
                "description": "Updated description",
                "sites": [],
            },
            format="json",
        )
        self.assertEqual(put_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(put_valid.data["title"], "Updated network title")

        put_duplicate = self.client.put(
            detail_url,
            {
                "title": "Another valid network",
                "description": "Should fail duplicate",
                "sites": [],
            },
            format="json",
        )
        self.assertEqual(
            put_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )
        first_network.refresh_from_db()
        self.assertEqual(first_network.title, "Updated network title")

        patch_valid = self.client.patch(
            detail_url, {"title": "Patched network title"}, format="json"
        )
        self.assertEqual(patch_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_valid.data["title"], "Patched network title")

        patch_duplicate = self.client.patch(
            detail_url, {"title": "Another valid network"}, format="json"
        )
        self.assertEqual(
            patch_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )
        first_network.refresh_from_db()
        self.assertEqual(first_network.title, "Patched network title")

    def test_network_cannot_be_deleted_while_sites_are_attached(self):
        network = Network.objects.create(
            user=self.user,
            title="Protected network",
            description="Network used for delete protection checks",
        )
        Site.objects.create(
            user=self.user,
            network=network,
            name="Protected site",
            description="Site that should block delete",
            status=SiteStatus.ACTIVE,
        )

        res = self.client.delete(
            reverse("network:network-detail", args=[network.id])
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Network.objects.filter(id=network.id).exists())
        self.assertTrue(Site.objects.filter(network=network).exists())

    def test_network_security_requires_authentication_for_all_methods(self):
        network = Network.objects.create(
            user=self.user,
            title="Security network",
            description="Secured network",
        )
        unauthenticated_client = APIClient()
        detail_url = reverse("network:network-detail", args=[network.id])

        self.assertEqual(
            unauthenticated_client.get(
                reverse("network:network-list")
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.post(
                reverse("network:network-list"),
                {"title": "Should fail", "description": "No auth"},
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
                    "title": "Updated denied",
                    "description": "No auth",
                    "sites": [],
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
