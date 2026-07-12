"""
Filtersets for NetBox Grafana Annotations Plugin.

For more information on NetBox filtersets, see:
https://docs.netbox.dev/en/stable/plugins/development/filtersets/

AnnotationLog is a plain BaseModel, not a NetBoxModel (see models.py), so
this uses NetBox's BaseFilterSet rather than NetBoxModelFilterSet, which
assumes change-logging/tag fields that don't exist here.
"""

from netbox.filtersets import BaseFilterSet

from .models import AnnotationLog


class AnnotationLogFilterSet(BaseFilterSet):
    class Meta:
        model = AnnotationLog
        fields = ("id", "object_type", "event_type", "success", "dashboard_uid")

    def search(self, queryset, name, value):
        return queryset.filter(object_repr__icontains=value)
