"""
Grafana HTTP API client for NetBox Grafana Annotations Plugin.

Confirmed against a live Grafana 13.0.2 instance (2026-07-12 spike, see
spec/02-technical-design.md). Uses Bearer token auth (a scoped service
account token) -- not the admin Basic Auth the v0 spike used for expediency.
"""
import logging

import requests

from .settings import PluginSettings

logger = logging.getLogger("netbox_grafana_annotations_plugin")


class GrafanaClientError(Exception):
    """Raised when Grafana can't be reached at all (timeout, DNS, connection refused)."""


def _headers(settings: PluginSettings) -> dict:
    return {
        "Authorization": f"Bearer {settings.grafana_token}",
        "Content-Type": "application/json",
    }


def search_dashboards_by_tag(settings: PluginSettings, tag: str) -> list:
    """GET /api/search?tag=<tag> -- returns a list of matching dashboards (dicts)."""
    try:
        response = requests.get(
            f"{settings.grafana_url}/api/search",
            params={"tag": tag, "type": "dash-db"},
            headers=_headers(settings),
            timeout=settings.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise GrafanaClientError(str(exc)) from exc
    return response.json()


def get_dashboard_panel_ids(settings: PluginSettings, dashboard_uid: str) -> list:
    """GET /api/dashboards/uid/<uid> -- returns the list of panel ids on a dashboard."""
    try:
        response = requests.get(
            f"{settings.grafana_url}/api/dashboards/uid/{dashboard_uid}",
            headers=_headers(settings),
            timeout=settings.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise GrafanaClientError(str(exc)) from exc
    panels = (response.json().get("dashboard") or {}).get("panels") or []
    return [p["id"] for p in panels if "id" in p]


def post_annotation(settings: PluginSettings, *, dashboard_uid: str, panel_id, time_ms: int, tags: list, text: str):
    """
    POST /api/annotations. Returns (status_code, response_body).
    Raises GrafanaClientError on connection-level failures so callers can
    distinguish "Grafana rejected the request" from "couldn't reach Grafana".
    """
    body = {"dashboardUID": dashboard_uid, "time": time_ms, "tags": tags, "text": text}
    if panel_id is not None:
        body["panelId"] = panel_id

    try:
        response = requests.post(
            f"{settings.grafana_url}/api/annotations",
            json=body,
            headers=_headers(settings),
            timeout=settings.timeout,
        )
    except requests.RequestException as exc:
        raise GrafanaClientError(str(exc)) from exc

    try:
        response_body = response.json()
    except ValueError:
        response_body = response.text

    return response.status_code, response_body
