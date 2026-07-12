"""
Models for NetBox Grafana Annotations Plugin.

For more information on NetBox models, see:
https://docs.netbox.dev/en/stable/plugins/development/models/
"""

from django.db import models
from django.urls import reverse
from netbox.models import BaseModel


class AnnotationLog(BaseModel):
    """
    A record of one attempt to post a Grafana annotation in response to a
    NetBox webhook event. Entries are created by the plugin's webhook
    receiver only -- never manually authored -- so this model has no create
    or edit views, only list/detail/delete (see spec/02-technical-design.md
    "AnnotationLog (candidate model, for visibility/debugging)").

    Deliberately NOT a NetBoxModel: NetBoxModel's automatic change-logging
    tries to record `request.user` for every save, which crashes for
    AnonymousUser -- and the webhook receiver that creates these entries is
    intentionally unauthenticated (see views.WebhookReceiverView). A log
    record doesn't need change history, tags, or custom fields anyway.
    BaseModel still provides NetBox's permission-aware queryset, which is
    what the list/detail/delete views actually need.
    """

    triggered_at = models.DateTimeField(help_text="When the NetBox event occurred, per the webhook payload.")
    object_type = models.CharField(max_length=100, help_text="NetBox object_type, e.g. 'dcim.device'.")
    event_type = models.CharField(max_length=20, help_text="created / updated / deleted.")
    object_repr = models.CharField(max_length=200, help_text="Human-readable representation of the changed object.")

    dashboard_uid = models.CharField(max_length=100, blank=True)
    panel_id = models.PositiveIntegerField(null=True, blank=True)
    annotation_text = models.TextField(blank=True)

    success = models.BooleanField(default=False)
    grafana_response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    error_detail = models.TextField(blank=True)

    class Meta:
        app_label = "netbox_grafana_annotations_plugin"
        ordering = ("-triggered_at",)
        verbose_name = "Annotation Log"
        verbose_name_plural = "Annotation Logs"

    def __str__(self):
        return f"{self.object_repr} ({self.event_type}) @ {self.triggered_at:%Y-%m-%d %H:%M:%S}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_grafana_annotations_plugin:annotationlog", args=[self.pk])
