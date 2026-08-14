"""
Views for the network APIs.
"""

import json
import logging
import os

from django.db.models import Q
from rest_framework import viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Connection, Device, Interface, Network, Site
from network import serializers

logger = logging.getLogger("network")


def log_action(action, resource, user, target=None):
    """Write a one-line debug message for CRUD operations."""
    user_name = getattr(user, "email", "anonymous")
    target_name = f" '{target}'" if target else ""
    logger.debug("%s %s%s for %s", action, resource, target_name, user_name)


def _safe_json(value):
    """Serialize request/response values into a readable string."""
    if value in (None, "", {}, [], ()):
        return "none"
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            value = value.decode("utf-8", errors="replace")
    if hasattr(value, "dict") and callable(value.dict):
        value = value.dict()
    if hasattr(value, "items"):
        try:
            return json.dumps(dict(value), sort_keys=True)
        except TypeError:
            return str(value)
    if isinstance(value, (list, tuple)):
        try:
            return json.dumps(value, sort_keys=True)
        except TypeError:
            return str(value)
    return str(value)


def log_error_request(request, response):
    """Log failed requests with method, path, headers, and both payloads."""
    if response is None or response.status_code < 400:
        return

    debug_value = os.getenv("DJANGO_DEBUG")
    if debug_value is None or str(debug_value).lower() in {"0", "false", "no"}:
        return

    user_name = getattr(request.user, "email", "anonymous")
    headers = dict(request.headers)

    incoming_payload = {}
    if hasattr(request, "data"):
        incoming_payload = request.data
    elif hasattr(request, "POST"):
        incoming_payload = request.POST
    incoming_payload = _safe_json(incoming_payload)

    outgoing_payload = getattr(response, "data", None)
    if outgoing_payload is None and hasattr(response, "content"):
        outgoing_payload = response.content
    outgoing_payload = _safe_json(outgoing_payload)

    logger.warning(
        "\nRequest failed\n"
        "Method: %s\n"
        "URL: %s\n"
        "User: %s\n"
        "Status: %s\n"
        "Headers: %s\n"
        "Incoming payload: %s\n"
        "Outgoing payload: %s",
        request.method,
        request.get_full_path(),
        user_name,
        response.status_code,
        headers,
        incoming_payload,
        outgoing_payload,
    )


class LoggingViewSetMixin:
    """Log warning details when an endpoint returns an error response."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        log_error_request(request, response)
        return response


class SiteViewSet(LoggingViewSetMixin, viewsets.ModelViewSet):
    """Manage sites in the database."""

    serializer_class = serializers.SiteSerializer
    queryset = Site.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        log_action("Listing", "site", request.user)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action("Getting", "site", request.user, instance.name)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        target_name = (
            request.data.get("name")
            if isinstance(request.data, dict)
            else None
        )
        log_action("Creating", "site", request.user, target_name)
        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response = super().update(request, *args, **kwargs)
        log_action("Updating", "site", request.user, instance.name)
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action("Deleting", "site", request.user, instance.name)
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by("-id")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        has_devices = Device.objects.filter(site=instance).exists()
        if has_devices:
            raise ValidationError(
                {
                    "detail": (
                        "Cannot delete a site that still has devices "
                        "attached."
                    )
                }
            )
        instance.delete()


class DeviceViewSet(LoggingViewSetMixin, viewsets.ModelViewSet):
    """Manage devices in the database."""

    serializer_class = serializers.DeviceSerializer
    queryset = Device.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        log_action("Listing", "device", request.user)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action("Getting", "device", request.user, instance.name)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        target_name = (
            request.data.get("name")
            if isinstance(request.data, dict)
            else None
        )
        log_action("Creating", "device", request.user, target_name)
        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response = super().update(request, *args, **kwargs)
        log_action("Updating", "device", request.user, instance.name)
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action("Deleting", "device", request.user, instance.name)
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by("-id")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        has_interfaces = Interface.objects.filter(device=instance).exists()
        if has_interfaces:
            raise ValidationError(
                {
                    "detail": (
                        "Cannot delete a device that still has interfaces "
                        "attached."
                    )
                }
            )
        instance.delete()


class InterfaceViewSet(LoggingViewSetMixin, viewsets.ModelViewSet):
    """Manage interfaces in the database."""

    serializer_class = serializers.InterfaceSerializer
    queryset = Interface.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        log_action("Listing", "interface", request.user)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action("Getting", "interface", request.user, str(instance))
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        target_name = (
            request.data.get("name")
            if isinstance(request.data, dict)
            else None
        )
        log_action("Creating", "interface", request.user, target_name)
        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response = super().update(request, *args, **kwargs)
        log_action("Updating", "interface", request.user, str(instance))
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action("Deleting", "interface", request.user, str(instance))
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by("-id")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        has_connections = Connection.objects.filter(
            Q(start=instance) | Q(end=instance)
        ).exists()
        if has_connections:
            raise ValidationError(
                {
                    "detail": (
                        "Cannot delete an interface that is attached "
                        "to a connection."
                    )
                }
            )
        instance.delete()


class ConnectionViewSet(LoggingViewSetMixin, viewsets.ModelViewSet):
    """Manage connections in the database."""

    serializer_class = serializers.ConnectionSerializer
    queryset = Connection.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        log_action("Listing", "connection", request.user)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action(
            "Getting",
            "connection",
            request.user,
            instance.name or str(instance.connection_id),
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        target_name = (
            request.data.get("name")
            if isinstance(request.data, dict)
            else None
        )
        log_action(
            "Creating",
            "connection",
            request.user,
            target_name or "new connection",
        )
        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response = super().update(request, *args, **kwargs)
        log_action(
            "Updating",
            "connection",
            request.user,
            instance.name or str(instance.connection_id),
        )
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action(
            "Deleting",
            "connection",
            request.user,
            instance.name or str(instance.connection_id),
        )
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by("-id")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        instance.delete()


class ConnectionNestedViewSet(LoggingViewSetMixin, viewsets.ModelViewSet):
    """Create or update connections using nested
    network/site/device/interface JSON.
    """

    serializer_class = serializers.ConnectionNestedSerializer
    queryset = Connection.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        log_action("Listing", "connection-full", request.user)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action(
            "Getting",
            "connection-full",
            request.user,
            instance.name or str(instance.connection_id),
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        target_name = (
            request.data.get("name")
            if isinstance(request.data, dict)
            else None
        )
        log_action(
            "Creating",
            "connection-full",
            request.user,
            target_name or "new connection",
        )
        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response = super().update(request, *args, **kwargs)
        log_action(
            "Updating",
            "connection-full",
            request.user,
            instance.name or str(instance.connection_id),
        )
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action(
            "Deleting",
            "connection-full",
            request.user,
            instance.name or str(instance.connection_id),
        )
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by("-id")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class NetworkViewSet(LoggingViewSetMixin, viewsets.ModelViewSet):
    """Manage networks in the database."""

    serializer_class = serializers.NetworkDetailSerializer
    queryset = Network.objects.all()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by("-id")

    def list(self, request, *args, **kwargs):
        log_action("Listing", "network", request.user)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action("Getting", "network", request.user, instance.title)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        target_name = (
            request.data.get("title")
            if isinstance(request.data, dict)
            else None
        )
        log_action("Creating", "network", request.user, target_name)
        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response = super().update(request, *args, **kwargs)
        log_action("Updating", "network", request.user, instance.title)
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action("Deleting", "network", request.user, instance.title)
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        has_sites = Site.objects.filter(network=instance).exists()
        if has_sites:
            raise ValidationError(
                {
                    "detail": (
                        "Cannot delete a network that still has sites "
                        "attached."
                    )
                }
            )
        instance.delete()

    def get_serializer_class(self):
        if self.action == "list":
            return serializers.NetworkSerializer
        return self.serializer_class
