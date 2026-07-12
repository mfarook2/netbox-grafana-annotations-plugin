"""
Search indexes for NetBox Grafana Annotations Plugin.

See: https://docs.netbox.dev/en/stable/plugins/development/search/
"""

from netbox.search import SearchIndex

from .models import AnnotationLog


class AnnotationLogIndex(SearchIndex):
    model = AnnotationLog
    fields = (
        ("object_repr", 100),
        ("object_type", 200),
        ("dashboard_uid", 300),
    )
    display_attrs = ("event_type", "success")


indexes = (AnnotationLogIndex,)
