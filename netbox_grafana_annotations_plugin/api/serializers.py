"""
API serializers for NetBox Grafana Annotations Plugin.

AnnotationLog is a plain BaseModel, not a NetBoxModel (see models.py for why),
so this uses DRF's BaseModelSerializer rather than NetBoxModelSerializer --
there are no tags/custom_fields/change-log features to serialize.
"""

from netbox.api.serializers import BaseModelSerializer

from ..models import AnnotationLog


class AnnotationLogSerializer(BaseModelSerializer):
    class Meta:
        model = AnnotationLog
        fields = (
            "id", "display", "triggered_at", "object_type", "event_type", "object_repr",
            "dashboard_uid", "panel_id", "annotation_text", "success", "grafana_response_status",
            "error_detail",
        )
