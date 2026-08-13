from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Connection, Device, Interface, InterfaceStatus, Network, Site, SiteStatus


class ConnectionApiTests(TestCase):
    """Tests for the connection endpoints."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='connection-api@example.com',
            password='testpass123',
            name='Connection API User',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_connection_with_nested_network_site_device_interface(self):
        payload = {
            'name': 'uplink',
            'status': 'connected',
            'start': {
                'network': {'title': 'Core Network', 'description': 'Main core'},
                'site': {'name': 'HQ', 'description': 'Head office', 'status': 'active'},
                'device': {'name': 'Router-1', 'serial_number': 'SER-1'},
                'interface': {'name': 'eth0', 'speed': 1000, 'status': 'up'},
            },
            'end': {
                'network': {'title': 'Core Network', 'description': 'Main core'},
                'site': {'name': 'HQ', 'description': 'Head office', 'status': 'active'},
                'device': {'name': 'Switch-1', 'serial_number': 'SER-2'},
                'interface': {'name': 'eth1', 'speed': 1000, 'status': 'up'},
            },
        }

        res = self.client.post(reverse('network:connection-full-list'), payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['name'], 'uplink')
        self.assertEqual(Network.objects.filter(user=self.user, title='Core Network').count(), 1)
        self.assertEqual(Site.objects.filter(user=self.user, name='HQ').count(), 1)
        self.assertEqual(Device.objects.filter(user=self.user, name='Router-1').count(), 1)
        self.assertEqual(Interface.objects.filter(user=self.user, name='eth0').count(), 1)
        self.assertEqual(Interface.objects.filter(user=self.user, name='eth1').count(), 1)

    def test_connection_crud_endpoints(self):
        network = Network.objects.create(user=self.user, title='Connection CRUD network', description='CRUD network')
        site = Site.objects.create(user=self.user, network=network, name='Connection CRUD site', description='Site', status=SiteStatus.ACTIVE)
        device = Device.objects.create(user=self.user, site=site, name='Connection device', serial_number='CONN-DEV-1')
        start_interface = Interface.objects.create(user=self.user, device=device, name='eth0', speed=1000, status='up')
        end_interface = Interface.objects.create(user=self.user, device=device, name='eth1', speed=1000, status='up')

        create_payload = {'name': 'uplink', 'status': 'connected', 'start': start_interface.id, 'end': end_interface.id}
        create_res = self.client.post(reverse('network:connection-list'), create_payload, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)

        connection = Connection.objects.get(id=create_res.data['id'])
        detail_url = reverse('network:connection-detail', args=[connection.id])

        get_res = self.client.get(detail_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data['name'], 'uplink')

        put_payload = {
            'name': 'uplink-updated',
            'status': 'disconnected',
            'start': end_interface.id,
            'end': start_interface.id,
        }
        put_res = self.client.put(detail_url, put_payload, format='json')
        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        self.assertEqual(put_res.data['name'], 'uplink-updated')

        patch_res = self.client.patch(detail_url, {'status': 'connected'}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['status'], 'connected')

        delete_res = self.client.delete(detail_url)
        self.assertEqual(delete_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Connection.objects.filter(id=connection.id).exists())

    def test_delete_connection_removes_only_the_connection(self):
        network = Network.objects.create(user=self.user, title='Delete Network', description='Delete me')
        site = Site.objects.create(user=self.user, network=network, name='Delete Site', description='Delete site', status=SiteStatus.ACTIVE)
        device = Device.objects.create(user=self.user, site=site, name='Delete Device', serial_number='DEL-1')
        start_interface = Interface.objects.create(user=self.user, device=device, name='eth0', speed=1000, status='up')
        end_interface = Interface.objects.create(user=self.user, device=device, name='eth1', speed=1000, status='up')
        connection = Connection.objects.create(user=self.user, name='delete-me', start=start_interface, end=end_interface)

        res = self.client.delete(reverse('network:connection-detail', args=[connection.id]))

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Connection.objects.filter(id=connection.id).exists())
        self.assertTrue(Network.objects.filter(id=network.id).exists())
        self.assertTrue(Site.objects.filter(id=site.id).exists())
        self.assertTrue(Device.objects.filter(id=device.id).exists())
        self.assertTrue(Interface.objects.filter(id=start_interface.id).exists())
        self.assertTrue(Interface.objects.filter(id=end_interface.id).exists())

    def test_connection_start_and_end_must_be_unique_pair(self):
        network = Network.objects.create(user=self.user, title='Duplicate connection network', description='Validation network')
        site = Site.objects.create(user=self.user, network=network, name='Duplicate connection site', description='Site', status=SiteStatus.ACTIVE)
        device = Device.objects.create(user=self.user, site=site, name='Duplicate connection device', serial_number='CONN-DUP-001')
        start_interface = Interface.objects.create(user=self.user, device=device, name='eth0', speed=1000, status='up')
        end_interface = Interface.objects.create(user=self.user, device=device, name='eth1', speed=1000, status='up')
        other_device = Device.objects.create(user=self.user, site=site, name='Duplicate connection device 2', serial_number='CONN-DUP-002')
        other_start_interface = Interface.objects.create(user=self.user, device=other_device, name='eth0', speed=1000, status='up')
        other_end_interface = Interface.objects.create(user=self.user, device=other_device, name='eth1', speed=1000, status='up')
        replacement_device = Device.objects.create(user=self.user, site=site, name='Duplicate connection device 3', serial_number='CONN-DUP-003')
        replacement_start_interface = Interface.objects.create(user=self.user, device=replacement_device, name='eth0', speed=1000, status='up')
        replacement_end_interface = Interface.objects.create(user=self.user, device=replacement_device, name='eth1', speed=1000, status='up')
        connection = Connection.objects.create(user=self.user, name='original-connection', start=start_interface, end=end_interface)
        detail_url = reverse('network:connection-detail', args=[connection.id])

        create_valid = self.client.post(
            reverse('network:connection-list'),
            {'name': 'valid-connection-2', 'status': 'connected', 'start': other_start_interface.id, 'end': other_end_interface.id},
            format='json',
        )
        self.assertEqual(create_valid.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_valid.data['start'], other_start_interface.id)
        self.assertEqual(create_valid.data['end'], other_end_interface.id)

        create_duplicate = self.client.post(
            reverse('network:connection-list'),
            {'name': 'duplicate-connection', 'status': 'connected', 'start': start_interface.id, 'end': end_interface.id},
            format='json',
        )
        self.assertEqual(create_duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Connection.objects.filter(start=start_interface, end=end_interface).count(), 1)

        put_valid = self.client.put(
            detail_url,
            {'name': 'updated-connection', 'status': 'disconnected', 'start': replacement_start_interface.id, 'end': replacement_end_interface.id},
            format='json',
        )
        self.assertEqual(put_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(put_valid.data['name'], 'updated-connection')

        put_duplicate = self.client.put(
            detail_url,
            {'name': 'duplicate-connection-update', 'status': 'connected', 'start': other_start_interface.id, 'end': other_end_interface.id},
            format='json',
        )
        self.assertEqual(put_duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        connection.refresh_from_db()
        self.assertEqual(connection.name, 'updated-connection')

        patch_valid = self.client.patch(detail_url, {'name': 'patched-connection'}, format='json')
        self.assertEqual(patch_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_valid.data['name'], 'patched-connection')

        patch_duplicate = self.client.patch(detail_url, {'start': other_start_interface.id, 'end': other_end_interface.id}, format='json')
        self.assertEqual(patch_duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        connection.refresh_from_db()
        self.assertEqual(connection.name, 'patched-connection')

    def test_connection_status_is_read_only_and_derived_from_interface_states(self):
        network = Network.objects.create(user=self.user, title='Connection status network', description='Validation network')
        site = Site.objects.create(user=self.user, network=network, name='Connection status site', description='Site', status=SiteStatus.ACTIVE)
        device = Device.objects.create(user=self.user, site=site, name='Connection status device', serial_number='CONN-STATUS-001')
        other_device = Device.objects.create(user=self.user, site=site, name='Connection status device 2', serial_number='CONN-STATUS-002')
        start_interface = Interface.objects.create(user=self.user, device=device, name='eth0', speed=1000, status=InterfaceStatus.UP)
        end_interface = Interface.objects.create(user=self.user, device=device, name='eth1', speed=1000, status=InterfaceStatus.UP)
        alt_start_interface = Interface.objects.create(user=self.user, device=other_device, name='eth0', speed=1000, status=InterfaceStatus.UP)
        alt_end_interface = Interface.objects.create(user=self.user, device=other_device, name='eth1', speed=1000, status=InterfaceStatus.UP)

        create_res = self.client.post(
            reverse('network:connection-list'),
            {'name': 'auto-status-create', 'status': 'disconnected', 'start': start_interface.id, 'end': end_interface.id},
            format='json',
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_res.data['status'], 'connected')

        connection = Connection.objects.get(id=create_res.data['id'])
        detail_url = reverse('network:connection-detail', args=[connection.id])

        start_interface.status = InterfaceStatus.DOWN
        start_interface.save(update_fields=['status'])
        put_res = self.client.put(
            detail_url,
            {'name': 'auto-status-put', 'status': 'connected', 'start': start_interface.id, 'end': end_interface.id},
            format='json',
        )
        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        self.assertEqual(put_res.data['status'], 'disconnected')

        start_interface.status = InterfaceStatus.UP
        start_interface.save(update_fields=['status'])
        patch_res = self.client.patch(detail_url, {'status': 'disconnected'}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['status'], 'connected')

        alt_start_interface.status = InterfaceStatus.DOWN
        alt_start_interface.save(update_fields=['status'])
        create_disconnected = self.client.post(
            reverse('network:connection-list'),
            {'name': 'alt-disconnected', 'status': 'connected', 'start': alt_start_interface.id, 'end': alt_end_interface.id},
            format='json',
        )
        self.assertEqual(create_disconnected.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_disconnected.data['status'], 'disconnected')

    def test_connection_invalid_start_or_end_is_rejected_on_create_update_and_patch(self):
        network = Network.objects.create(user=self.user, title='Connection validation network', description='Validation network')
        site = Site.objects.create(user=self.user, network=network, name='Connection validation site', description='Site', status=SiteStatus.ACTIVE)
        device = Device.objects.create(user=self.user, site=site, name='Connection validation device', serial_number='CONN-VALID-001')
        start_interface = Interface.objects.create(user=self.user, device=device, name='eth0', speed=1000, status='up')
        end_interface = Interface.objects.create(user=self.user, device=device, name='eth1', speed=1000, status='up')
        other_device = Device.objects.create(user=self.user, site=site, name='Connection validation device 2', serial_number='CONN-VALID-002')
        other_start_interface = Interface.objects.create(user=self.user, device=other_device, name='eth0', speed=1000, status='up')
        other_end_interface = Interface.objects.create(user=self.user, device=other_device, name='eth1', speed=1000, status='up')
        replacement_device = Device.objects.create(user=self.user, site=site, name='Connection validation device 3', serial_number='CONN-VALID-003')
        replacement_start_interface = Interface.objects.create(user=self.user, device=replacement_device, name='eth0', speed=1000, status='up')
        replacement_end_interface = Interface.objects.create(user=self.user, device=replacement_device, name='eth1', speed=1000, status='up')
        connection = Connection.objects.create(user=self.user, name='valid-connection', start=start_interface, end=end_interface)
        detail_url = reverse('network:connection-detail', args=[connection.id])

        create_valid = self.client.post(
            reverse('network:connection-list'),
            {'name': 'valid-connection-2', 'status': 'connected', 'start': other_start_interface.id, 'end': other_end_interface.id},
            format='json',
        )
        self.assertEqual(create_valid.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_valid.data['start'], other_start_interface.id)
        self.assertEqual(create_valid.data['end'], other_end_interface.id)

        create_invalid_start = self.client.post(
            reverse('network:connection-list'),
            {'name': 'invalid-start', 'status': 'connected', 'start': 999999, 'end': end_interface.id},
            format='json',
        )
        self.assertEqual(create_invalid_start.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Connection.objects.filter(name='invalid-start').exists())

        create_invalid_end = self.client.post(
            reverse('network:connection-list'),
            {'name': 'invalid-end', 'status': 'connected', 'start': start_interface.id, 'end': 999999},
            format='json',
        )
        self.assertEqual(create_invalid_end.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Connection.objects.filter(name='invalid-end').exists())

        put_valid = self.client.put(
            detail_url,
            {'name': 'valid-updated', 'status': 'disconnected', 'start': replacement_start_interface.id, 'end': replacement_end_interface.id},
            format='json',
        )
        self.assertEqual(put_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(put_valid.data['name'], 'valid-updated')

        put_invalid_start = self.client.put(
            detail_url,
            {'name': 'invalid-start-update', 'status': 'connected', 'start': 999999, 'end': start_interface.id},
            format='json',
        )
        self.assertEqual(put_invalid_start.status_code, status.HTTP_400_BAD_REQUEST)
        connection.refresh_from_db()
        self.assertEqual(connection.name, 'valid-updated')

        put_invalid_end = self.client.put(
            detail_url,
            {'name': 'invalid-end-update', 'status': 'connected', 'start': end_interface.id, 'end': 999999},
            format='json',
        )
        self.assertEqual(put_invalid_end.status_code, status.HTTP_400_BAD_REQUEST)
        connection.refresh_from_db()
        self.assertEqual(connection.name, 'valid-updated')

        patch_valid = self.client.patch(detail_url, {'start': replacement_start_interface.id, 'end': replacement_end_interface.id}, format='json')
        self.assertEqual(patch_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_valid.data['start'], replacement_start_interface.id)
        self.assertEqual(patch_valid.data['end'], replacement_end_interface.id)

        patch_invalid_start = self.client.patch(detail_url, {'start': 999999}, format='json')
        self.assertEqual(patch_invalid_start.status_code, status.HTTP_400_BAD_REQUEST)
        connection.refresh_from_db()
        self.assertEqual(connection.start_id, replacement_start_interface.id)

        patch_invalid_end = self.client.patch(detail_url, {'end': 999999}, format='json')
        self.assertEqual(patch_invalid_end.status_code, status.HTTP_400_BAD_REQUEST)
        connection.refresh_from_db()
        self.assertEqual(connection.end_id, replacement_end_interface.id)

    def test_connection_security_requires_authentication_for_all_methods(self):
        network = Network.objects.create(user=self.user, title='Connection security network', description='Security network')
        site = Site.objects.create(user=self.user, network=network, name='Connection security site', description='Site', status=SiteStatus.ACTIVE)
        device = Device.objects.create(user=self.user, site=site, name='Connection security device', serial_number='SEC-CONN-001')
        start_interface = Interface.objects.create(user=self.user, device=device, name='eth0', speed=1000, status='up')
        end_interface = Interface.objects.create(user=self.user, device=device, name='eth1', speed=1000, status='up')
        connection = Connection.objects.create(user=self.user, name='security-connection', start=start_interface, end=end_interface)
        unauthenticated_client = APIClient()
        detail_url = reverse('network:connection-detail', args=[connection.id])

        self.assertEqual(
            unauthenticated_client.get(reverse('network:connection-list')).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.post(
                reverse('network:connection-list'),
                {'name': 'No auth conn', 'status': 'connected', 'start': start_interface.id, 'end': end_interface.id},
                format='json',
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
                {'name': 'Updated denied conn', 'status': 'disconnected', 'start': start_interface.id, 'end': end_interface.id},
                format='json',
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.patch(detail_url, {'status': 'connected'}, format='json').status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.delete(detail_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_nested_connection_security_requires_authentication_for_all_methods(self):
        network = Network.objects.create(user=self.user, title='Nested security network', description='Security network')
        site = Site.objects.create(user=self.user, network=network, name='Nested security site', description='Site', status=SiteStatus.ACTIVE)
        device = Device.objects.create(user=self.user, site=site, name='Nested security device', serial_number='SEC-NEST-001')
        start_interface = Interface.objects.create(user=self.user, device=device, name='eth0', speed=1000, status='up')
        end_interface = Interface.objects.create(user=self.user, device=device, name='eth1', speed=1000, status='up')
        connection = Connection.objects.create(user=self.user, name='nested-security', start=start_interface, end=end_interface)
        unauthenticated_client = APIClient()
        detail_url = reverse('network:connection-full-detail', args=[connection.id])

        self.assertEqual(
            unauthenticated_client.get(reverse('network:connection-full-list')).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.post(
                reverse('network:connection-full-list'),
                {
                    'name': 'nested-no-auth',
                    'status': 'connected',
                    'start': {
                        'network': {'title': 'Nested A', 'description': 'A desc'},
                        'site': {'name': 'A Site', 'description': 'A', 'status': 'active'},
                        'device': {'name': 'A Device', 'serial_number': 'A-1'},
                        'interface': {'name': 'eth0', 'speed': 1000, 'status': 'up'},
                    },
                    'end': {
                        'network': {'title': 'Nested B', 'description': 'B desc'},
                        'site': {'name': 'B Site', 'description': 'B', 'status': 'active'},
                        'device': {'name': 'B Device', 'serial_number': 'B-1'},
                        'interface': {'name': 'eth1', 'speed': 1000, 'status': 'up'},
                    },
                },
                format='json',
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
                    'name': 'nested-updated-no-auth',
                    'status': 'disconnected',
                    'start': {'network': {'title': 'Nested A', 'description': 'A desc'}, 'site': {'name': 'A Site', 'description': 'A', 'status': 'active'}, 'device': {'name': 'A Device', 'serial_number': 'A-1'}, 'interface': {'name': 'eth0', 'speed': 1000, 'status': 'up'}},
                    'end': {'network': {'title': 'Nested B', 'description': 'B desc'}, 'site': {'name': 'B Site', 'description': 'B', 'status': 'active'}, 'device': {'name': 'B Device', 'serial_number': 'B-1'}, 'interface': {'name': 'eth1', 'speed': 1000, 'status': 'up'}},
                },
                format='json',
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.patch(detail_url, {'status': 'connected'}, format='json').status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.delete(detail_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
