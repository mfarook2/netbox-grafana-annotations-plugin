# Architecture

## Request flow

```
NetBox object changes
      │
      ▼
NetBox Event Rule (built-in) ──POST──▶ WebhookReceiverView
                                          /plugins/netbox_grafana_annotations_plugin/webhook/
                                              │
                                              ▼
                                   verify_signature(): HMAC-SHA512 of the raw
                                   request body, keyed with `webhook_secret`,
                                   compared against the X-Hook-Signature header
                                              │
                                              ▼
                                   parsing.parse_event(): extract object type,
                                   event type, changed fields, timestamp;
                                   resolve_mapping_identity() walks child
                                   objects (e.g. Interface) up to their parent
                                              │
                                              ▼
                                   mapping.resolve_target():
                                     1. grafana_dashboard_uid custom field
                                        override, if set
                                     2. else grafana_client.search_dashboards_by_tag()
                                        (cached in Django's cache framework)
                                              │
                                              ▼
                                   grafana_client.post_annotation()
                                              │
                                              ▼
                                   AnnotationLog.save() — success/failure,
                                   Grafana's response status, error detail
```

Every step above is a separate, independently unit-tested module (`webhook.py` orchestrates; `parsing.py`, `mapping.py`, `grafana_client.py` do the actual work), so the whole path is testable without a live NetBox or Grafana instance except for the top-level integration test.

## Why a plain, unauthenticated Django view

`WebhookReceiverView` deliberately does **not** inherit any of NetBox's `LoginRequiredMixin` / `ConditionalLoginRequiredMixin` generic view classes. NetBox enforces login on a per-view basis via these mixins, not through a blanket middleware over every URL — confirmed by reading NetBox's own `netbox/middleware.py` and `netbox/views/generic/feature_views.py`. That means a plain `django.views.View` is reachable with no session at all, which is exactly what's needed: NetBox's webhook-delivery worker has no user session to present.

Authenticity is instead verified by replicating NetBox's own webhook-signing convention (`extras/webhooks.py`'s `generate_signature()`): `hmac.new(key=secret, msg=body, digestmod=hashlib.sha512).hexdigest()`, sent as `X-Hook-Signature` whenever a Webhook object has a Secret configured. This means setup is just "put the same string in NetBox's Webhook Secret field and the plugin's `webhook_secret` setting" — no NetBox API token, no user account, no `AUTH_EXEMPT_PATHS` configuration required.

## Why `AnnotationLog` is a `BaseModel`, not a `NetBoxModel`

This looks like an odd choice at first glance — most NetBox plugin models inherit `NetBoxModel` for the tags/custom-fields/change-log features that come with it. `AnnotationLog` can't, for a specific reason: NetBox's automatic change-logging (`core.signals.handle_changed_object`) fires on every save of a model exposing `to_objectchange` (which `NetBoxModel` provides), and tries to record `request.user` on the resulting `ObjectChange`. Since the webhook receiver is deliberately unauthenticated, `request.user` is `AnonymousUser` — and assigning that to `ObjectChange.user` (a real foreign key to a `User`) raises a `ValueError` and 500s the request.

`netbox.models.BaseModel` provides the parts that actually matter for a log record — a permission-aware `RestrictedQuerySet`, so NetBox's object-permission system still governs who can view/delete entries — without the change-logging machinery that assumes every save happens inside an authenticated request. This cascades through a few other files: `AnnotationLogFilterSet` uses `BaseFilterSet` (not `NetBoxModelFilterSet`, which assumes `created`/`last_updated` fields), the serializer uses `BaseModelSerializer`, there's no changelog URL/view (nothing to show), and the table's `ActionsColumn` explicitly limits itself to `actions=("delete",)` since there's no edit or changelog view to link to.

## Object → dashboard mapping: two shapes

Not every NetBox object type maps to a dashboard the same way:

- **Top-level objects** (Device, Circuit) have their own identity and their own dashboard. Mapping resolves directly against the object's own type/name — no special handling needed.
- **Child objects** (Interface, and any other type added to `parsing.PARENT_OBJECT_MAP`) don't have their own dashboard — the dashboard that matters is the parent's. `resolve_mapping_identity()` walks up to the parent (using the nested summary NetBox includes in the webhook payload, e.g. `data.device`) for mapping purposes, while `AnnotationLog` still records the actual child object that changed, for an accurate audit trail. See the README's "Which NetBox object types should I cover?" section for the reasoning behind this design and how to extend it to other object types (e.g. Cable).

Getting a parent object's custom-field override requires one extra database lookup (`parsing._fetch_custom_fields()`), since NetBox's webhook payload only includes the parent's `id`/`name`/`display` inline, not its full custom field data. This is a small, deliberate tradeoff: it's only possible because the plugin runs in-process inside NetBox with direct ORM access — a standalone script polling the REST API would need a separate round-trip per event.

## Known limitation: intent vs. deployment

The trigger for an annotation is a NetBox database change, not a confirmed device configuration change. NetBox is a store of *intended* state — a NetBox Event Rule fires the moment a record is saved in NetBox's own database, which isn't necessarily the same moment a device's actual behavior changes. For teams that deploy close-in-time to NetBox edits (the plugin's intended audience — teams disciplined enough to run NetBox as source of truth, paired with automation), that gap is usually minutes, not weeks. Don't market or rely on this plugin as "shows exactly when the device changed" — the honest framing is "shows when the intended change was recorded."
