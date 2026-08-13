"""
Serializers for the network API.
"""
from rest_framework import serializers

from core.models import (
    Connection,
    ConnectionStatus,
    Device,
    Interface,
    InterfaceStatus,
    Network,
    Site,
    SiteStatus,
)


class SiteSerializer(serializers.ModelSerializer):
    """Serializer for the Site object."""
    network = serializers.PrimaryKeyRelatedField(queryset=Network.objects.all())

    class Meta:
        model = Site
        fields = ('id', 'network', 'name', 'description', 'status')
        read_only_fields = ('id',)


class DeviceSerializer(serializers.ModelSerializer):
    """Serializer for the Device object."""
    site = serializers.PrimaryKeyRelatedField(queryset=Site.objects.all())

    class Meta:
        model = Device
        fields = ('id', 'name', 'serial_number', 'site')
        read_only_fields = ('id',)


class InterfaceSerializer(serializers.ModelSerializer):
    """Serializer for the Interface object."""
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all())

    class Meta:
        model = Interface
        fields = ('id', 'name', 'speed', 'status', 'device')
        read_only_fields = ('id',)

    def validate(self, attrs):
        if self.instance is not None and 'device' in attrs and attrs['device'] != self.instance.device:
            raise serializers.ValidationError({'device': 'The device assignment cannot be changed after creation.'})
        return attrs

    def update(self, instance, validated_data):
        if 'device' in validated_data and validated_data['device'] != instance.device:
            raise serializers.ValidationError({'device': 'The device assignment cannot be changed after creation.'})

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class ConnectionSerializer(serializers.ModelSerializer):
    """Serializer for the Connection object."""
    start = serializers.PrimaryKeyRelatedField(queryset=Interface.objects.all())
    end = serializers.PrimaryKeyRelatedField(queryset=Interface.objects.all())

    class Meta:
        model = Connection
        fields = ('id', 'connection_id', 'name', 'status', 'start', 'end')
        read_only_fields = ('id', 'connection_id')


class ConnectionNestedSerializer(serializers.ModelSerializer):
    """Serializer that accepts nested network/site/device/interface payloads."""
    start = serializers.SerializerMethodField()
    end = serializers.SerializerMethodField()

    class Meta:
        model = Connection
        fields = ('id', 'connection_id', 'name', 'status', 'start', 'end')
        read_only_fields = ('id', 'connection_id')

    def get_start(self, obj):
        return obj.start_id

    def get_end(self, obj):
        return obj.end_id

    def to_internal_value(self, data):
        data = data.copy()
        user = self.context['request'].user

        start_data = data.pop('start', None)
        end_data = data.pop('end', None)

        validated = super().to_internal_value(data)

        if start_data is not None:
            validated['start'] = self._resolve_endpoint(start_data, user)
        if end_data is not None:
            validated['end'] = self._resolve_endpoint(end_data, user)

        return validated

    def _resolve_network(self, network_data, user):
        title = network_data.get('title')
        if not title:
            raise serializers.ValidationError({'network': 'A network title is required.'})

        network = Network.objects.filter(user=user, title=title).first()
        if network is None:
            network = Network.objects.create(
                user=user,
                title=title,
                description=network_data.get('description', ''),
            )
        return network

    def _resolve_site(self, site_data, network, user):
        name = site_data.get('name')
        if not name:
            raise serializers.ValidationError({'site': 'A site name is required.'})

        site = Site.objects.filter(user=user, network=network, name=name).first()
        if site is None:
            status_value = site_data.get('status', SiteStatus.ACTIVE)
            site = Site.objects.create(
                user=user,
                network=network,
                name=name,
                description=site_data.get('description', ''),
                status=status_value,
            )
        return site

    def _resolve_device(self, device_data, site, user):
        name = device_data.get('name')
        if not name:
            raise serializers.ValidationError({'device': 'A device name is required.'})

        device = Device.objects.filter(user=user, site=site, name=name).first()
        if device is None:
            device = Device.objects.create(
                user=user,
                site=site,
                name=name,
                serial_number=device_data.get('serial_number', f'{site.name}-{name}-{user.id}'),
            )
        return device

    def _resolve_interface(self, interface_data, device, user):
        name = interface_data.get('name')
        if not name:
            raise serializers.ValidationError({'interface': 'An interface name is required.'})

        interface = Interface.objects.filter(user=user, device=device, name=name).first()
        if interface is None:
            interface = Interface.objects.create(
                user=user,
                device=device,
                name=name,
                speed=interface_data.get('speed', 0),
                status=interface_data.get('status', InterfaceStatus.UP),
            )
        return interface

    def _resolve_endpoint(self, endpoint_data, user):
        if not endpoint_data:
            raise serializers.ValidationError({'start': 'Connection endpoint data is required.'})

        network = self._resolve_network(endpoint_data.get('network', {}), user)
        site = self._resolve_site(endpoint_data.get('site', {}), network, user)
        device = self._resolve_device(endpoint_data.get('device', {}), site, user)
        interface_data = endpoint_data.get('interface', {})
        return self._resolve_interface(interface_data, device, user)

    def create(self, validated_data):
        user = self.context['request'].user
        start_data = validated_data.pop('start', None)
        end_data = validated_data.pop('end', None)

        if start_data is None or end_data is None:
            raise serializers.ValidationError({'start': 'Both connection endpoints are required.'})

        connection = Connection.objects.create(
            user=user,
            name=validated_data.get('name', ''),
            status=validated_data.get('status', ConnectionStatus.CONNECTED),
            start=start_data,
            end=end_data,
        )
        return connection

    def update(self, instance, validated_data):
        user = self.context['request'].user
        if 'start' in validated_data:
            instance.start = self._resolve_endpoint(validated_data['start'], user)
        if 'end' in validated_data:
            instance.end = self._resolve_endpoint(validated_data['end'], user)
        if 'name' in validated_data:
            instance.name = validated_data['name']
        if 'status' in validated_data:
            instance.status = validated_data['status']
        instance.save()
        return instance


class NetworkSerializer(serializers.ModelSerializer):
    """Serializer for the Network object."""
    sites = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Site.objects.all(),
        required=False,
    )

    class Meta:
        model = Network
        fields = ('id', 'title', 'description', 'sites')
        read_only_fields = ('id',)

    def _attach_sites(self, sites, network):
        """Attach authenticated-user sites to a network."""
        auth_user = self.context['request'].user
        valid_sites = [
            site for site in sites
            if Site.objects.filter(id=site.id, user=auth_user).exists()
        ]
        network.sites.set(valid_sites)

    def create(self, validated_data):
        """Create a new network."""
        sites = validated_data.pop('sites', [])
        network = Network.objects.create(**validated_data)
        self._attach_sites(sites, network)
        return network

    def update(self, instance, validated_data):
        """Update the network."""
        sites = validated_data.pop('sites', None)

        if sites is not None:
            self._attach_sites(sites, instance)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class NetworkDetailSerializer(NetworkSerializer):
    """Detailed serializer for network objects."""

    class Meta(NetworkSerializer.Meta):
        fields = NetworkSerializer.Meta.fields

