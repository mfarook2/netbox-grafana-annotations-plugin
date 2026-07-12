"""
Tables for NetBox Grafana Annotations Plugin.

For more information on NetBox tables, see:
https://docs.netbox.dev/en/stable/plugins/development/tables/
"""

import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from .models import AnnotationLog


class AnnotationLogTable(NetBoxTable):
    object_repr = tables.Column(linkify=True, verbose_name="Object")
    success = columns.BooleanColumn()
    triggered_at = tables.DateTimeColumn()
    # AnnotationLog has no edit or changelog view (it's a plain BaseModel,
    # system-generated only -- see models.py) -- only delete makes sense.
    actions = columns.ActionsColumn(actions=("delete",))

    class Meta(NetBoxTable.Meta):
        model = AnnotationLog
        fields = (
            "pk", "id", "triggered_at", "object_type", "event_type", "object_repr",
            "dashboard_uid", "panel_id", "success", "grafana_response_status", "actions",
        )
        default_columns = (
            "triggered_at", "object_type", "event_type", "object_repr", "dashboard_uid", "success",
        )
