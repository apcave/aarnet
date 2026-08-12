"""
Serializers for the network API.
"""
from rest_framework import serializers

from core.models import Network, Site


class SiteSerializer(serializers.ModelSerializer):
    """Serializer for the Site object."""

    class Meta:
        model = Site
        fields = ('id', 'name', 'description', 'status')
        read_only_fields = ('id',)


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

