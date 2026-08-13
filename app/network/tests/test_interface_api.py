from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Connection, Device, Interface, InterfaceStatus, Network, Site, SiteStatus


class InterfaceApiTests(TestCase):
    """Tests for the interface endpoints."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='interface-api@example.com',
            password='testpass123',
            name='Interface API User',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_interface_and_connection(self):
        network = Network.objects.create(
            user=self.user,
            title='Interface network',
            description='Network for interfaces',
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name='Interface site',
            description='Interface site',
            status=SiteStatus.ACTIVE,
        )
        device = Device.objects.create(
            user=self.user,
            site=site,
            name='Switch-1',
            serial_number='SW-001',
        )

        interface_payload = {
            'name': 'eth0',
            'speed': 1000,
            'status': InterfaceStatus.UP,
            'device': device.id,
        }

        interface_res = self.client.post(reverse('network:interface-list'), interface_payload, format='json')

        self.assertEqual(interface_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(interface_res.data['name'], 'eth0')

    def test_interface_crud_endpoints(self):
        network = Network.objects.create(user=self.user, title='Interface CRUD network', description='CRUD network')
        site = Site.objects.create(user=self.user, network=network, name='Interface CRUD site', description='Site', status=SiteStatus.ACTIVE)
        device = Device.objects.create(user=self.user, site=site, name='Switch-1', serial_number='SW-CRUD-1')
        create_payload = {'device': device.id, 'name': 'eth0', 'speed': 1000, 'status': InterfaceStatus.UP}
        create_res = self.client.post(reverse('network:interface-list'), create_payload, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)

        interface = Interface.objects.get(id=create_res.data['id'])
        detail_url = reverse('network:interface-detail', args=[interface.id])

        get_res = self.client.get(detail_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data['name'], 'eth0')

        put_res = self.client.put(
            detail_url,
            {'device': device.id, 'name': 'eth1', 'speed': 2000, 'status': InterfaceStatus.DOWN},
            format='json',
        )
        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        self.assertEqual(put_res.data['name'], 'eth1')

        patch_res = self.client.patch(detail_url, {'speed': 2500}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['speed'], 2500)

        delete_res = self.client.delete(detail_url)
        self.assertEqual(delete_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Interface.objects.filter(id=interface.id).exists())

    def test_interface_name_must_be_unique_per_device(self):
        network = Network.objects.create(
            user=self.user,
            title='Duplicate interface network',
            description='Network for interface name validation',
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name='Interface uniqueness site',
            description='Site for unique interface checks',
            status=SiteStatus.ACTIVE,
        )
        device = Device.objects.create(
            user=self.user,
            site=site,
            name='Switch-uniqueness',
            serial_number='IFACE-UNI-001',
        )
        original_interface = Interface.objects.create(
            user=self.user,
            device=device,
            name='eth0',
            speed=1000,
            status=InterfaceStatus.UP,
        )
        detail_url = reverse('network:interface-detail', args=[original_interface.id])

        create_valid = self.client.post(
            reverse('network:interface-list'),
            {'device': device.id, 'name': 'eth1', 'speed': 1500, 'status': InterfaceStatus.UP},
            format='json',
        )
        self.assertEqual(create_valid.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_valid.data['name'], 'eth1')

        create_duplicate = self.client.post(
            reverse('network:interface-list'),
            {'device': device.id, 'name': 'eth0', 'speed': 2000, 'status': InterfaceStatus.DOWN},
            format='json',
        )
        self.assertEqual(create_duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Interface.objects.filter(device=device, name='eth0').count(), 1)

        put_valid = self.client.put(
            detail_url,
            {'device': device.id, 'name': 'eth2', 'speed': 2500, 'status': InterfaceStatus.DOWN},
            format='json',
        )
        self.assertEqual(put_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(put_valid.data['name'], 'eth2')

        put_duplicate = self.client.put(
            detail_url,
            {'device': device.id, 'name': 'eth1', 'speed': 3000, 'status': InterfaceStatus.UP},
            format='json',
        )
        self.assertEqual(put_duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        original_interface.refresh_from_db()
        self.assertEqual(original_interface.name, 'eth2')

        patch_valid = self.client.patch(detail_url, {'name': 'eth3'}, format='json')
        self.assertEqual(patch_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_valid.data['name'], 'eth3')

        patch_duplicate = self.client.patch(detail_url, {'name': 'eth1'}, format='json')
        self.assertEqual(patch_duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        original_interface.refresh_from_db()
        self.assertEqual(original_interface.name, 'eth3')

    def test_interface_invalid_device_and_duplicate_name_are_rejected_on_create_update_and_patch(self):
        network = Network.objects.create(
            user=self.user,
            title='Interface validation network',
            description='Validation network for interface rules',
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name='Interface validation site',
            description='Validation site',
            status=SiteStatus.ACTIVE,
        )
        valid_device = Device.objects.create(
            user=self.user,
            site=site,
            name='Switch-1',
            serial_number='IFACE-VALID-001',
        )
        original_interface = Interface.objects.create(
            user=self.user,
            device=valid_device,
            name='eth0',
            speed=1000,
            status=InterfaceStatus.UP,
        )
        duplicate_interface = Interface.objects.create(
            user=self.user,
            device=valid_device,
            name='eth1',
            speed=1000,
            status=InterfaceStatus.UP,
        )
        detail_url = reverse('network:interface-detail', args=[duplicate_interface.id])

        create_success = self.client.post(
            reverse('network:interface-list'),
            {'device': valid_device.id, 'name': 'eth2', 'speed': 1500, 'status': InterfaceStatus.UP},
            format='json',
        )
        self.assertEqual(create_success.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_success.data['device'], valid_device.id)
        self.assertEqual(create_success.data['name'], 'eth2')

        create_invalid_device = self.client.post(
            reverse('network:interface-list'),
            {'device': 999999, 'name': 'eth3', 'speed': 1500, 'status': InterfaceStatus.UP},
            format='json',
        )
        self.assertEqual(create_invalid_device.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Interface.objects.filter(device=valid_device, name='eth3').exists())

        create_duplicate = self.client.post(
            reverse('network:interface-list'),
            {'device': valid_device.id, 'name': 'eth0', 'speed': 1200, 'status': InterfaceStatus.DOWN},
            format='json',
        )
        self.assertEqual(create_duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Interface.objects.filter(device=valid_device, name='eth0').count(), 1)

        put_success = self.client.put(
            detail_url,
            {'device': valid_device.id, 'name': 'eth4', 'speed': 2000, 'status': InterfaceStatus.DOWN},
            format='json',
        )
        self.assertEqual(put_success.status_code, status.HTTP_200_OK)
        self.assertEqual(put_success.data['device'], valid_device.id)
        self.assertEqual(put_success.data['name'], 'eth4')

        put_invalid_device = self.client.put(
            detail_url,
            {'device': 999999, 'name': 'eth5', 'speed': 2000, 'status': InterfaceStatus.UP},
            format='json',
        )
        self.assertEqual(put_invalid_device.status_code, status.HTTP_400_BAD_REQUEST)
        duplicate_interface.refresh_from_db()
        self.assertEqual(duplicate_interface.name, 'eth4')

        put_duplicate_name = self.client.put(
            detail_url,
            {'device': valid_device.id, 'name': 'eth0', 'speed': 2000, 'status': InterfaceStatus.UP},
            format='json',
        )
        self.assertEqual(put_duplicate_name.status_code, status.HTTP_400_BAD_REQUEST)
        duplicate_interface.refresh_from_db()
        self.assertEqual(duplicate_interface.name, 'eth4')

        patch_success = self.client.patch(detail_url, {'name': 'eth6'}, format='json')
        self.assertEqual(patch_success.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_success.data['name'], 'eth6')

        patch_invalid_device = self.client.patch(detail_url, {'device': 999999}, format='json')
        self.assertEqual(patch_invalid_device.status_code, status.HTTP_400_BAD_REQUEST)
        duplicate_interface.refresh_from_db()
        self.assertEqual(duplicate_interface.name, 'eth6')

        patch_duplicate_name = self.client.patch(detail_url, {'name': 'eth0'}, format='json')
        self.assertEqual(patch_duplicate_name.status_code, status.HTTP_400_BAD_REQUEST)
        duplicate_interface.refresh_from_db()
        self.assertEqual(duplicate_interface.name, 'eth6')

    def test_interface_device_assignment_is_immutable_after_creation(self):
        network = Network.objects.create(
            user=self.user,
            title='Immutable interface device network',
            description='Network for device immutability checks',
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name='Immutable interface site',
            description='Site for interface immutability checks',
            status=SiteStatus.ACTIVE,
        )
        original_device = Device.objects.create(
            user=self.user,
            site=site,
            name='Switch-original',
            serial_number='IMMUTABLE-DEV-001',
        )
        replacement_device = Device.objects.create(
            user=self.user,
            site=site,
            name='Switch-replacement',
            serial_number='IMMUTABLE-DEV-002',
        )
        interface = Interface.objects.create(
            user=self.user,
            device=original_device,
            name='eth0',
            speed=1000,
            status=InterfaceStatus.UP,
        )
        detail_url = reverse('network:interface-detail', args=[interface.id])

        create_valid = self.client.post(
            reverse('network:interface-list'),
            {'device': replacement_device.id, 'name': 'eth1', 'speed': 1000, 'status': InterfaceStatus.UP},
            format='json',
        )
        self.assertEqual(create_valid.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_valid.data['device'], replacement_device.id)

        put_res = self.client.put(
            detail_url,
            {'device': replacement_device.id, 'name': 'eth2', 'speed': 2000, 'status': InterfaceStatus.DOWN},
            format='json',
        )
        self.assertEqual(put_res.status_code, status.HTTP_400_BAD_REQUEST)
        interface.refresh_from_db()
        self.assertEqual(interface.device_id, original_device.id)
        self.assertEqual(interface.name, 'eth0')

        patch_res = self.client.patch(detail_url, {'device': replacement_device.id}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_400_BAD_REQUEST)
        interface.refresh_from_db()
        self.assertEqual(interface.device_id, original_device.id)

    def test_interface_status_must_be_one_of_the_allowed_choices(self):
        network = Network.objects.create(
            user=self.user,
            title='Interface status validation network',
            description='Network for interface status validation',
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name='Interface status validation site',
            description='Validation site',
            status=SiteStatus.ACTIVE,
        )
        device = Device.objects.create(
            user=self.user,
            site=site,
            name='Status switch',
            serial_number='IFACE-STATUS-001',
        )
        interface = Interface.objects.create(
            user=self.user,
            device=device,
            name='eth0',
            speed=1000,
            status=InterfaceStatus.UP,
        )
        detail_url = reverse('network:interface-detail', args=[interface.id])

        create_valid = self.client.post(
            reverse('network:interface-list'),
            {'device': device.id, 'name': 'eth1', 'speed': 1500, 'status': InterfaceStatus.MAINTENANCE},
            format='json',
        )
        self.assertEqual(create_valid.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_valid.data['status'], InterfaceStatus.MAINTENANCE)

        create_invalid_value = self.client.post(
            reverse('network:interface-list'),
            {'device': device.id, 'name': 'eth2', 'speed': 1500, 'status': 'offline'},
            format='json',
        )
        self.assertEqual(create_invalid_value.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Interface.objects.filter(device=device, name='eth2').exists())

        create_null_status = self.client.post(
            reverse('network:interface-list'),
            {'device': device.id, 'name': 'eth3', 'speed': 1500, 'status': None},
            format='json',
        )
        self.assertEqual(create_null_status.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Interface.objects.filter(device=device, name='eth3').exists())

        put_valid = self.client.put(
            detail_url,
            {'device': device.id, 'name': 'eth4', 'speed': 2000, 'status': InterfaceStatus.DOWN},
            format='json',
        )
        self.assertEqual(put_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(put_valid.data['status'], InterfaceStatus.DOWN)

        put_invalid_value = self.client.put(
            detail_url,
            {'device': device.id, 'name': 'eth5', 'speed': 2000, 'status': 'failed'},
            format='json',
        )
        self.assertEqual(put_invalid_value.status_code, status.HTTP_400_BAD_REQUEST)
        interface.refresh_from_db()
        self.assertEqual(interface.status, InterfaceStatus.DOWN)

        put_null_status = self.client.put(
            detail_url,
            {'device': device.id, 'name': 'eth6', 'speed': 2000, 'status': None},
            format='json',
        )
        self.assertEqual(put_null_status.status_code, status.HTTP_400_BAD_REQUEST)
        interface.refresh_from_db()
        self.assertEqual(interface.name, 'eth4')

        patch_valid = self.client.patch(detail_url, {'status': InterfaceStatus.MAINTENANCE}, format='json')
        self.assertEqual(patch_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_valid.data['status'], InterfaceStatus.MAINTENANCE)

        patch_invalid_value = self.client.patch(detail_url, {'status': 'maintenance-mode'}, format='json')
        self.assertEqual(patch_invalid_value.status_code, status.HTTP_400_BAD_REQUEST)
        interface.refresh_from_db()
        self.assertEqual(interface.status, InterfaceStatus.MAINTENANCE)

        patch_null_status = self.client.patch(detail_url, {'status': None}, format='json')
        self.assertEqual(patch_null_status.status_code, status.HTTP_400_BAD_REQUEST)
        interface.refresh_from_db()
        self.assertEqual(interface.status, InterfaceStatus.MAINTENANCE)

    def test_interface_cannot_be_deleted_when_connections_are_attached(self):
        network = Network.objects.create(
            user=self.user,
            title='Protected interface network',
            description='Network used for delete protection checks',
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name='Protected interface site',
            description='Site for delete protection',
            status=SiteStatus.ACTIVE,
        )
        device = Device.objects.create(
            user=self.user,
            site=site,
            name='Protected switch',
            serial_number='PROTECT-IFACE-001',
        )
        start_interface = Interface.objects.create(
            user=self.user,
            device=device,
            name='eth0',
            speed=1000,
            status=InterfaceStatus.UP,
        )
        end_interface = Interface.objects.create(
            user=self.user,
            device=device,
            name='eth1',
            speed=1000,
            status=InterfaceStatus.UP,
        )
        Connection.objects.create(
            user=self.user,
            name='protected-connection',
            start=start_interface,
            end=end_interface,
        )

        res = self.client.delete(reverse('network:interface-detail', args=[start_interface.id]))

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Interface.objects.filter(id=start_interface.id).exists())
        self.assertTrue(Connection.objects.filter(start=start_interface).exists())

    def test_interface_security_requires_authentication_for_all_methods(self):
        network = Network.objects.create(
            user=self.user,
            title='Interface security network',
            description='Security network',
        )
        site = Site.objects.create(
            user=self.user,
            network=network,
            name='Interface security site',
            description='Site security',
            status=SiteStatus.ACTIVE,
        )
        device = Device.objects.create(
            user=self.user,
            site=site,
            name='Interface security device',
            serial_number='SEC-IFACE-001',
        )
        interface = Interface.objects.create(
            user=self.user,
            device=device,
            name='eth0',
            speed=1000,
            status=InterfaceStatus.UP,
        )
        unauthenticated_client = APIClient()
        detail_url = reverse('network:interface-detail', args=[interface.id])

        self.assertEqual(
            unauthenticated_client.get(reverse('network:interface-list')).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.post(
                reverse('network:interface-list'),
                {'device': device.id, 'name': 'eth99', 'speed': 1000, 'status': InterfaceStatus.UP},
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
                {'device': device.id, 'name': 'eth1', 'speed': 2000, 'status': InterfaceStatus.DOWN},
                format='json',
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.patch(detail_url, {'speed': 2500}, format='json').status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            unauthenticated_client.delete(detail_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
