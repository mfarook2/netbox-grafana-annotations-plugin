"""
Object -> Grafana dashboard/panel mapping for NetBox Grafana Annotations Plugin.

Resolution order (spec/02-technical-design.md, resolved 2026-07-12):
  1. NetBox custom field override (settings.dashboard_uid_field /
     panel_id_field) on the changed object -- read straight from the
     webhook payload's `data.custom_fields`, no DB lookup needed.
  2. Live Grafana tag-search: GET /api/search?tag={tag_template}, cached
     briefly so a burst of edits to the same object doesn't cause a search
     call per event.
  3. No mapping found -> caller skips the annotation.
"""
import logging
from dataclasses import dataclass

from django.core.cache import cache

from . import grafana_client
from .settings import PluginSettings

logger = logging.getLogger("netbox_grafana_annotations_plugin")


@dataclass
class MappingResult:
    dashboard_uid: str
    panel_id: int | None


def _custom_field_override(settings: PluginSettings, data: dict) -> MappingResult | None:
    custom_fields = data.get("custom_fields") or {}
    dashboard_uid = custom_fields.get(settings.dashboard_uid_field)
    if not dashboard_uid:
        return None
    return MappingResult(dashboard_uid=dashboard_uid, panel_id=custom_fields.get(settings.panel_id_field))


def _cache_key(tag: str) -> str:
    return f"netbox_grafana_annotations_plugin:tag_search:{tag}"


def _tag_search(settings: PluginSettings, object_type: str, object_name: str) -> MappingResult | None:
    tag = settings.tag_template.format(object_type=object_type, object_name=object_name)
    cache_key = _cache_key(tag)

    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None  # cached False means "searched before, found nothing"

    dashboards = grafana_client.search_dashboards_by_tag(settings, tag)
    if not dashboards:
        cache.set(cache_key, False, settings.cache_ttl)
        return None

    dashboard_uid = dashboards[0]["uid"]
    panel_ids = grafana_client.get_dashboard_panel_ids(settings, dashboard_uid)
    panel_id = panel_ids[0] if len(panel_ids) == 1 else None

    result = MappingResult(dashboard_uid=dashboard_uid, panel_id=panel_id)
    cache.set(cache_key, result, settings.cache_ttl)
    return result


def resolve_target(settings: PluginSettings, object_type: str, object_name: str, data: dict) -> MappingResult | None:
    override = _custom_field_override(settings, data)
    if override is not None:
        return override

    try:
        return _tag_search(settings, object_type, object_name)
    except grafana_client.GrafanaClientError:
        logger.exception("Grafana tag-search failed while mapping %s %s", object_type, object_name)
        return None
