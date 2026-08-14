"""
URL mappings for the network app.
"""

from django.urls import include, path

from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("networks", views.NetworkViewSet)
router.register("sites", views.SiteViewSet)
router.register("devices", views.DeviceViewSet)
router.register("interfaces", views.InterfaceViewSet)
router.register("connections", views.ConnectionViewSet)
router.register(
    "connections-full",
    views.ConnectionNestedViewSet,
    basename="connection-full",
)

app_name = "network"

urlpatterns = [
    path("", include(router.urls)),
]
