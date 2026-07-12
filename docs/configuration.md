# Configuration Reference

All settings live under `PLUGINS_CONFIG["netbox_grafana_annotations_plugin"]` in NetBox's `configuration.py` (or netbox-docker's `configuration/plugins.py`).

```python
PLUGINS_CONFIG = {
    "netbox_grafana_annotations_plugin": {
        "grafana_url": "https://grafana.example.com",
        "grafana_token": "<Grafana API token, Bearer auth>",
        "webhook_secret": "<a random string>",
        "tag_template": "netbox:{object_type}:{object_name}",
        "dashboard_uid_field": "grafana_dashboard_uid",
        "panel_id_field": "grafana_panel_id",
        "default_tags": ["netbox"],
        "timeout": 5,
        "cache_ttl": 60,
    },
}
```

## `grafana_url`

**Required.** Base URL of your Grafana instance, no trailing slash (e.g. `https://grafana.example.com`, not `https://grafana.example.com/`).

If NetBox and Grafana are containerized separately (e.g. NetBox in `netbox-docker`, Grafana as its own container), remember that `localhost` from inside NetBox's container refers to that container, not the host or Grafana's container — use a reachable hostname (a Docker Compose service name, `host.docker.internal`, or a real network address).

## `grafana_token`

**Required.** A Grafana API token, sent as `Authorization: Bearer <token>`. A [service account token](https://grafana.com/docs/grafana/latest/administration/service-accounts/) is recommended over a personal API key. Needs permission to:

- `GET /api/search` (dashboard search, for the tag-search mapping path) — Viewer role is enough.
- `POST /api/annotations` (creating annotations) — needs at least Editor role.

## `webhook_secret`

Strongly recommended; defaults to `""` (empty). A shared secret used to verify NetBox's `X-Hook-Signature` header on every incoming webhook request — must be the exact same string as the Secret field on the corresponding NetBox Webhook object. See [Architecture](architecture.md#Why-a-plain-unauthenticated-Django-view) for how this works.

**If left blank, the webhook endpoint accepts any request that reaches it, unsigned.** This is acceptable for a local/dev instance with no external network exposure; anywhere else, set this.

## `tag_template`

Default: `"netbox:{object_type}:{object_name}"`. A Python format string used to build the tag the plugin searches Grafana for when no custom-field override is set. `{object_type}` is NetBox's dotted app/model name (e.g. `dcim.device`); `{object_name}` is the object's display name (or, for a resolved child object like Interface, its parent's display name — see [Architecture](architecture.md#Object--dashboard-mapping-two-shapes)).

Change this if your organization already has a conflicting Grafana tagging convention — the format string can use any literal text plus the two named placeholders.

## `dashboard_uid_field` / `panel_id_field`

Defaults: `"grafana_dashboard_uid"` / `"grafana_panel_id"`. The names of NetBox custom fields that, when created and filled in on a specific object, override the tag-search mapping for that object. `dashboard_uid_field` alone is enough to target a whole dashboard; add `panel_id_field` too to pin a specific panel within it. See the README's "Which NetBox object types should I cover?" section for when to use this vs. tagging a dashboard.

You don't have to create these custom fields at all if you're only using the tag-search path — they're purely opt-in per object.

## `default_tags`

Default: `["netbox"]`. Tags applied to every annotation this plugin creates, in addition to `device-{event}` (e.g. `device-updated`) and the resolved object's name. Useful for filtering all plugin-created annotations in Grafana regardless of which object triggered them.

## `timeout`

Default: `5` (seconds). How long to wait on each individual Grafana HTTP call (search or annotation POST) before giving up and logging a `grafana_unreachable` failure in `AnnotationLog`.

## `cache_ttl`

Default: `60` (seconds). How long to cache a tag-search result — including a *negative* result ("searched, found nothing") — keyed by the resolved object type/name. This means a burst of several edits to the same object within the TTL window triggers at most one `GET /api/search` call to Grafana, not one per edit.

Uses whatever cache backend NetBox's `CACHES` setting configures. Django's default in-memory `LocMemCache` is **per-process** — with multiple web workers (a typical production NetBox deployment), each worker keeps its own independent cache, so the dedup only applies within a single worker's traffic. If you want the cache genuinely shared across all workers, point `CACHES` at a shared backend like Redis (NetBox already depends on Redis for other purposes, so this is usually just reusing an existing connection).
