# Screenshots

The main [README.md](../../README.md) references four images by these exact filenames, all currently present in this directory. This table is kept as a reference for recapturing any of them later (e.g. after a NetBox/Grafana UI change) — see the README's "Setup workflow" section to get a live setup running.

| Filename | Capture from | What to show |
|---|---|---|
| `annotation-tooltip.png` | Your Grafana dashboard | Hover the dashed annotation marker so its tooltip (timestamp, text, tags) is visible, then screenshot the panel. |
| `annotation-logs-list.png` | `/plugins/netbox_grafana_annotations_plugin/annotation-logs/` in NetBox | The list view, after at least one event has fired — ideally with a couple of rows so `success`/`dashboard_uid` columns are visible. |
| `netbox-webhook-config.png` | A Webhook's edit page in NetBox (Operations → Webhooks) | The URL and Secret fields visible (blur/redact the actual secret value before committing). |
| `netbox-event-rule-config.png` | An Event Rule's edit page in NetBox (Operations → Event Rules) | Object types, event types, and the Webhook selected as the action. |
