# Setup Guide

This is the same walkthrough as the README's "Setup workflow", expanded with more context per step. See [Configuration Reference](configuration.md) for what each setting does, and [Architecture](architecture.md) for why the plugin is built this way.

## Prerequisites

- NetBox 4.6+ with this plugin installed (`pip install`) and added to `PLUGINS` (see the README's "Installing" section).
- A reachable Grafana instance — reachable specifically from wherever NetBox's *webhook-delivery worker* process runs, which may not be the same host/container as NetBox's web process. See the networking note under step 5 below.
- `python manage.py migrate` run at least once since installing, so the `AnnotationLog` table exists.

## Step 1 — Grafana API token

**Administration → Service accounts → Add service account** (Editor role) → **Add service account token**. Copy the token value immediately — Grafana only shows it once. Put it in `grafana_token`.

Editor role is sufficient: the plugin needs to search dashboards (`GET /api/search`, works with Viewer) and create annotations (`POST /api/annotations`, needs Editor).

## Step 2 — Shared secret

Generate any random string, e.g.:

```bash
openssl rand -hex 32
```

Put it in `webhook_secret` now — you'll enter the identical string into NetBox's Webhook object in step 4. This is what lets the webhook endpoint verify a request actually came from your NetBox instance without needing a login session or API token (see [Architecture](architecture.md#Why-a-plain-unauthenticated-Django-view)).

## Step 3 — Choose your mapping strategy

Pick one, or use both (custom field always wins when set):

### Option A: tag your Grafana dashboards (recommended default)

Open the dashboard in Grafana → **Edit** (pencil icon) → **Settings** (gear icon) → **JSON Model** → add the tag string to the top-level `"tags"` array, e.g.:

```json
{
  "tags": ["netbox:dcim.device:core-switch-01"],
  ...
}
```

→ **Save dashboard**. (Some Grafana versions expose a plain "Tags" field under Settings → General instead — use whichever your version shows; JSON Model always works.)

The tag format is `netbox:{object_type}:{object_name}` by default (configurable via `tag_template`) — `{object_type}` is NetBox's dotted model name (`dcim.device`, `circuits.circuit`), `{object_name}` is the object's display name.

### Option B: NetBox custom field override

**Customization → Custom Fields → Add**:

- **Object types**: the NetBox type(s) you want this override available on (e.g. `DCIM > Device`)
- **Name**: `grafana_dashboard_uid` (must match `dashboard_uid_field` if you've customized it)
- **Type**: Text
- **Create**

Then, on any object of that type, its edit page will show a "Custom Fields" section with this field — fill in the target dashboard's UID (the string after `/d/` in the dashboard's URL).

Optionally repeat for a second field `grafana_panel_id` (Type: Integer) to also pin a specific panel.

## Step 4 — Create the NetBox Webhook

**Operations → Webhooks → Add**:

| Field | Value |
|---|---|
| Name | anything descriptive, e.g. `grafana-annotations` |
| Payload URL | `http(s)://<your-netbox-host>/plugins/netbox_grafana_annotations_plugin/webhook/` |
| HTTP method | POST |
| HTTP content type | `application/json` |
| Secret | the same string as `webhook_secret` from step 2 |

!!! warning "Networking gotcha"
    NetBox's webhook worker (the process that actually sends this HTTP request) may run in a different container or host than the web process the Payload URL points at. This is true of the default `netbox-docker` layout, where `netbox-worker` is a separate container from `netbox`. If so, `localhost` in the Payload URL will **not** reach the web process — you'll see connection-refused errors in the worker's logs. Use a hostname the worker container can actually resolve: the Compose service name (`http://netbox:8080/...`) if both are on the same Compose network, or the real reachable address otherwise.

## Step 5 — Create the NetBox Event Rule

**Operations → Event Rules → Add**:

- **Object types** — a multi-select: type to search, click a match to add it as a chip, repeat for each type. Recommended starting set: `DCIM > Device`, `DCIM > Interface`, `Circuits > Circuit` (see the README's "Which NetBox object types should I cover?" for why these three and not others).
- **Event types** — which operations trigger the rule, also a multi-select: **Object created**, **Object updated**, **Object deleted**. "Object updated" alone is a reasonable starting point; add the others if you want annotations for object creation/deletion too.
- **Enabled** — checked.
- Scroll to **Action type**: `Webhook`, then **Webhook**: select the one created in step 4.
- **Save**.

## Step 6 — Verify

Make a real change to an object matching the Event Rule — e.g. edit a device's role, or an interface's description. Within a few seconds:

1. **NetBox → Annotation Logs** (`/plugins/netbox_grafana_annotations_plugin/annotation-logs/`) — a new entry should appear with `success = Yes`, the resolved dashboard UID, and the exact annotation text sent.
2. **Grafana**, on the matching dashboard — a dashed vertical marker should appear at that timestamp; hovering it shows the same text and tags.

If either doesn't show up, work through [Troubleshooting](troubleshooting.md) — it's organized by exactly what you're seeing (or not seeing).
