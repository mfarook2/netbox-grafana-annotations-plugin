"""
URL patterns for NetBox Grafana Annotations Plugin.

For more information on URL routing, see:
https://docs.netbox.dev/en/stable/plugins/development/views/#url-registration
"""

from django.urls import path

from . import views

urlpatterns = (
    path("annotation-logs/", views.AnnotationLogListView.as_view(), name="annotationlog_list"),
    path("annotation-logs/<int:pk>/", views.AnnotationLogView.as_view(), name="annotationlog"),
    path("annotation-logs/<int:pk>/delete/", views.AnnotationLogDeleteView.as_view(), name="annotationlog_delete"),
    # No changelog route: AnnotationLog is a plain BaseModel, not a
    # NetBoxModel, so it has no ObjectChange history (see models.py).
    # Webhook receiver: point a NetBox Event Rule's Webhook at this URL.
    # Not login-gated (see views.WebhookReceiverView) -- authenticated via
    # X-Hook-Signature HMAC instead. See README.md for setup instructions.
    path("webhook/", views.WebhookReceiverView.as_view(), name="webhook"),
)
