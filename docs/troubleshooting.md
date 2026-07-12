# Troubleshooting

Start with **NetBox → Annotation Logs** (`/plugins/netbox_grafana_annotations_plugin/annotation-logs/`) — every webhook the plugin receives is recorded there, successful or not, with an error detail for failures. If there's no entry at all for your test change, the problem is upstream of the plugin (NetBox never delivered the webhook, or it never reached this endpoint). If there's an entry with `success = No`, the error detail tells you which of the steps below to check.

## Nothing shows up in Annotation Logs at all

The webhook never reached the plugin. Check, in order:

1. **Is the Event Rule enabled, and scoped to the object type/event you're testing?** A role change on a Device won't fire a rule scoped only to Interface, for example.
2. **Is the Webhook's Payload URL exactly right**, including the trailing slash (`/webhook/`, not `/webhook`)?
3. **Can NetBox's webhook-delivery worker actually reach that URL?** Check the worker's own logs (in netbox-docker, `docker logs <netbox-worker-container>`) for a connection error. See the networking note in [Setup Guide, step 4](setup-guide.md#Step-4--Create-the-NetBox-Webhook) — `localhost` doesn't cross container boundaries.

## Annotation Logs entry has `success = No`, error mentions signature or 403

`webhook_secret` in `PLUGINS_CONFIG` doesn't match the Secret field on the NetBox Webhook object — they must be the *identical* string, not just "similar." Re-copy one into the other rather than retyping either by hand.

If you deliberately haven't set a `webhook_secret` (e.g. local dev instance with no external exposure), this shouldn't happen — an empty `webhook_secret` skips verification entirely rather than rejecting requests.

## Annotation Logs entry has `success = No`, error is "no Grafana dashboard mapping found"

The plugin received and parsed the event correctly, but couldn't figure out which Grafana dashboard it belongs to. Neither of the two mapping paths matched:

- No `grafana_dashboard_uid` custom field is set on the object (or its parent, for a child object type like Interface).
- No Grafana dashboard is tagged with the expected `netbox:{object_type}:{object_name}` tag.

Double check the exact tag string against what `tag_template` would produce — a typo in the tag (missing colon, wrong case) is the most common cause here. See [Setup Guide, step 3](setup-guide.md#Step-3--Choose-your-mapping-strategy).

For a child object type (Interface), remember the mapping is resolved against the *parent device's* name, not the interface's own name — tagging a dashboard `netbox:dcim.interface:GigabitEthernet0` won't match anything, since there's no such lookup; it needs to be `netbox:dcim.device:<the device's name>`.

## Annotation Logs entry has `success = No`, error mentions connection refused / timeout (to Grafana)

`grafana_url` isn't reachable from wherever NetBox's *web* process runs (this call happens synchronously inside the webhook view, unlike the NetBox→plugin delivery which is worker-mediated). Or `grafana_token` is invalid, expired, or lacks permission — a `401`/`403` from Grafana will also surface here since the plugin treats any non-2xx response as a failure with the response body in `error_detail`.

## Grafana annotation created, but on the wrong dashboard or panel

- If you're using the custom-field override, double check you set it on the right object (and, for Interface events, on the *device*, not the interface itself).
- If you're using tag search and multiple dashboards share the same tag, the plugin uses the *first* match from Grafana's search results — tag more specifically, or switch that object to the custom-field override for a guaranteed target.
- Panel-level targeting only happens when either (a) the matched dashboard has exactly one panel, or (b) `panel_id_field` is set on the object. Otherwise the annotation applies to the whole dashboard (no `panelId` sent), which still renders as a marker on every panel — just not scoped to one specific panel.

## Tests fail locally but pass in CI (or vice versa)

See [TESTING.md](../TESTING.md) for the local test setup — the test suite runs against a real NetBox instance's Django test runner (`manage.py test`), not a mocked framework, so a mismatched NetBox version or missing `testing/configuration.py` settings are the usual culprits.
