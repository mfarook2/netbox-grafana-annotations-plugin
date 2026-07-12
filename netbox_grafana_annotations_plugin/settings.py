"""
Plugin settings for NetBox Grafana Annotations Plugin.

All settings are read from PLUGINS_CONFIG['netbox_grafana_annotations_plugin']
in NetBox's configuration.py. See README.md for the full list and examples.
"""
from dataclasses import dataclass

from django.conf import settings

PLUGIN_NAME = "netbox_grafana_annotations_plugin"

# NetBox custom field names used for the mapping override (spec/02-technical-design.md).
DEFAULT_DASHBOARD_UID_FIELD = "grafana_dashboard_uid"
DEFAULT_PANEL_ID_FIELD = "grafana_panel_id"

# Default tag template used to resolve a dashboard via Grafana's search API
# when no custom-field override is set. Formatted with object_type/object_name.
DEFAULT_TAG_TEMPLATE = "netbox:{object_type}:{object_name}"

DEFAULT_TIMEOUT = 5
DEFAULT_CACHE_TTL = 60
DEFAULT_TAGS = ["netbox"]


@dataclass(frozen=True)
class PluginSettings:
    grafana_url: str
    grafana_token: str
    webhook_secret: str
    tag_template: str
    dashboard_uid_field: str
    panel_id_field: str
    default_tags: list
    timeout: int
    cache_ttl: int


def get_settings() -> PluginSettings:
    config = settings.PLUGINS_CONFIG.get(PLUGIN_NAME, {})
    return PluginSettings(
        grafana_url=config.get("grafana_url", "").rstrip("/"),
        grafana_token=config.get("grafana_token", ""),
        webhook_secret=config.get("webhook_secret", ""),
        tag_template=config.get("tag_template", DEFAULT_TAG_TEMPLATE),
        dashboard_uid_field=config.get("dashboard_uid_field", DEFAULT_DASHBOARD_UID_FIELD),
        panel_id_field=config.get("panel_id_field", DEFAULT_PANEL_ID_FIELD),
        default_tags=list(config.get("default_tags", DEFAULT_TAGS)),
        timeout=int(config.get("timeout", DEFAULT_TIMEOUT)),
        cache_ttl=int(config.get("cache_ttl", DEFAULT_CACHE_TTL)),
    )
