from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Network, Site, SiteStatus


class SiteApiTests(TestCase):
    """Tests for the network site API."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='network@example.com',
            password='testpass123',
            name='Network User',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_site_with_status(self):
        payload = {
            'name': 'Edge site',
            'description': 'Primary edge site',
            'status': SiteStatus.PLANNED,
        }

        res = self.client.post(reverse('network:site-list'), payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['status'], SiteStatus.PLANNED)
        self.assertEqual(res.data['name'], 'Edge site')

    def test_list_sites_for_authenticated_user(self):
        Site.objects.create(
            user=self.user,
            name='Alpha',
            description='Alpha site',
            status=SiteStatus.ACTIVE,
        )
        Site.objects.create(
            user=self.user,
            name='Beta',
            description='Beta site',
            status=SiteStatus.DECOMMISSIONED,
        )

        res = self.client.get(reverse('network:site-list'))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)

    def test_create_network_with_sites(self):
        site = Site.objects.create(
            user=self.user,
            name='Gateway',
            description='Gateway site',
            status=SiteStatus.ACTIVE,
        )

        payload = {
            'title': 'Regional network',
            'description': 'Core region',
            'sites': [site.id],
        }

        res = self.client.post(reverse('network:network-list'), payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['title'], 'Regional network')
        self.assertEqual(Network.objects.get(id=res.data['id']).sites.count(), 1)
