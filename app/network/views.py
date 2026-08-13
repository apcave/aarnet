"""
Views for the network APIs.
"""
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from core.models import Connection, Device, Interface, Network, Site
from network import serializers


class SiteViewSet(viewsets.ModelViewSet):
    """Manage sites in the database."""
    serializer_class = serializers.SiteSerializer
    queryset = Site.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by('-id')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        has_devices = Device.objects.filter(site=instance).exists()
        if has_devices:
            raise ValidationError({'detail': 'Cannot delete a site that still has devices attached.'})
        instance.delete()


class DeviceViewSet(viewsets.ModelViewSet):
    """Manage devices in the database."""
    serializer_class = serializers.DeviceSerializer
    queryset = Device.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by('-id')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        has_interfaces = Interface.objects.filter(device=instance).exists()
        if has_interfaces:
            raise ValidationError({'detail': 'Cannot delete a device that still has interfaces attached.'})
        instance.delete()


class InterfaceViewSet(viewsets.ModelViewSet):
    """Manage interfaces in the database."""
    serializer_class = serializers.InterfaceSerializer
    queryset = Interface.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by('-id')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        has_connections = Connection.objects.filter(Q(start=instance) | Q(end=instance)).exists()
        if has_connections:
            raise ValidationError({'detail': 'Cannot delete an interface that is attached to a connection.'})
        instance.delete()


class ConnectionViewSet(viewsets.ModelViewSet):
    """Manage connections in the database."""
    serializer_class = serializers.ConnectionSerializer
    queryset = Connection.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by('-id')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        instance.delete()


class ConnectionNestedViewSet(viewsets.ModelViewSet):
    """Create or update connections using nested network/site/device/interface JSON."""
    serializer_class = serializers.ConnectionNestedSerializer
    queryset = Connection.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by('-id')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class NetworkViewSet(viewsets.ModelViewSet):
    """Manage networks in the database."""
    serializer_class = serializers.NetworkDetailSerializer
    queryset = Network.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by('-id')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        has_sites = Site.objects.filter(network=instance).exists()
        if has_sites:
            raise ValidationError({'detail': 'Cannot delete a network that still has sites attached.'})
        instance.delete()

    def get_serializer_class(self):
        if self.action == 'list':
            return serializers.NetworkSerializer
        return self.serializer_class
