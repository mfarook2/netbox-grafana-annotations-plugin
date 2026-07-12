"""
Webhook event orchestration for NetBox Grafana Annotations Plugin.

Ties together: signature verification -> payload parsing -> dashboard/panel
mapping -> Grafana annotation POST -> AnnotationLog. Called by
views.WebhookReceiverView; kept separate from the view so it's unit-testable
without going through Django's request/response cycle.
"""
import hashlib
import hmac
import logging

from . import grafana_client, mapping, parsing
from .models import AnnotationLog
from .settings import get_settings

logger = logging.getLogger("netbox_grafana_annotations_plugin")


def verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """
    Verify NetBox's X-Hook-Signature header: HMAC-SHA512 hex digest of the
    raw request body, keyed with the Webhook object's configured Secret.
    Matches NetBox's own `extras.webhooks.generate_signature` exactly (see
    spec/02-technical-design.md).
    """
    if not signature_header:
        return False
    expected = hmac.new(key=secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def process_event(payload: dict, *, raw_body: bytes = b"", signature_header: str = None) -> dict:
    """
    Returns a plain dict describing the outcome (JSON-serializable), for the
    view to return as the HTTP response body. Always creates an AnnotationLog
    entry unless signature verification fails (an unverified request isn't
    trusted enough to log as a real event).
    """
    settings = get_settings()

    if settings.webhook_secret:
        if not verify_signature(raw_body, signature_header, settings.webhook_secret):
            logger.warning("Rejected webhook with invalid or missing X-Hook-Signature")
            return {"success": False, "error": "invalid_signature"}
    else:
        logger.warning(
            "webhook_secret is not configured -- accepting webhook without signature verification. "
            "Set PLUGINS_CONFIG['netbox_grafana_annotations_plugin']['webhook_secret'] and a matching "
            "Secret on the NetBox Webhook object before using this in production."
        )

    event = parsing.parse_event(payload)

    # For child objects (e.g. an Interface), mapping resolves to the parent
    # device -- but the annotation text/tags should still say which specific
    # child object changed, since that's the useful detail on the device's
    # dashboard (see spec/02-technical-design.md).
    is_child_object = event.mapping_object_name != event.object_repr
    text = f"netbox: {event.object_repr} — {event.summary}" if is_child_object else f"netbox: {event.summary}"
    tags = [*settings.default_tags, f"device-{event.event}", event.mapping_object_name]
    if is_child_object:
        tags.append(event.object_repr)

    log_entry = AnnotationLog(
        triggered_at=event.timestamp,
        object_type=event.object_type,
        event_type=event.event,
        object_repr=event.object_repr,
        annotation_text=text,
    )

    target = mapping.resolve_target(
        settings, event.mapping_object_type, event.mapping_object_name, {"custom_fields": event.mapping_custom_fields}
    )
    if target is None:
        log_entry.success = False
        log_entry.error_detail = "no Grafana dashboard mapping found (no custom field override, no tag match)"
        log_entry.save()
        logger.info(
            "No dashboard mapping for %s %s (from %s %s) -- skipping annotation",
            event.mapping_object_type, event.mapping_object_name, event.object_type, event.object_repr,
        )
        # Not a failure of the receiver itself -- the event was received and
        # handled correctly, there's just nothing to annotate. The view maps
        # this to HTTP 200 rather than an error status.
        return {"success": False, "skipped": True, "error": "no_mapping"}

    log_entry.dashboard_uid = target.dashboard_uid
    log_entry.panel_id = target.panel_id

    time_ms = int(event.timestamp.timestamp() * 1000)
    try:
        status_code, response_body = grafana_client.post_annotation(
            settings,
            dashboard_uid=target.dashboard_uid,
            panel_id=target.panel_id,
            time_ms=time_ms,
            tags=tags,
            text=text,
        )
    except grafana_client.GrafanaClientError as exc:
        log_entry.success = False
        log_entry.error_detail = str(exc)
        log_entry.save()
        logger.exception("Could not reach Grafana while posting annotation for %s", event.object_repr)
        return {"success": False, "error": "grafana_unreachable"}

    log_entry.grafana_response_status = status_code
    log_entry.success = 200 <= status_code < 300
    if not log_entry.success:
        log_entry.error_detail = str(response_body)
    log_entry.save()

    return {
        "success": log_entry.success,
        "dashboard_uid": target.dashboard_uid,
        "panel_id": target.panel_id,
        "grafana_response_status": status_code,
    }
