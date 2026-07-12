"""
Payload parsing for NetBox Grafana Annotations Plugin.

Parses NetBox Event Rule webhook payloads. Confirmed shape against a live
NetBox v4.6.4 instance (2026-07-12 spike, see spec/02-technical-design.md):
top-level object_type/event/timestamp/data/snapshots -- `snapshots` stores
raw FK ids, only `data` has resolved display names, and only for the
*current* (post-change) value.
"""
from dataclasses import dataclass
from datetime import UTC, datetime

from django.contrib.contenttypes.models import ContentType

# Object types that don't have their own Grafana dashboard -- there's no such
# thing as a "per-interface dashboard" -- so dashboard mapping should resolve
# through to the named parent field instead. Extend this as more child object
# types are added to the Event Rule (e.g. front/rear ports, power ports).
PARENT_OBJECT_MAP = {
    "dcim.interface": {"field": "device", "object_type": "dcim.device"},
}


@dataclass
class ParsedEvent:
    object_type: str
    event: str
    object_repr: str
    object_id: int | None
    timestamp: datetime
    summary: str
    data: dict
    # The object type/name/custom_fields to use for *dashboard mapping*.
    # Equal to object_type/object_repr/data["custom_fields"] for top-level
    # objects (Device, Circuit); resolved to the parent's for child objects
    # (Interface -> its Device) via PARENT_OBJECT_MAP.
    mapping_object_type: str
    mapping_object_name: str
    mapping_custom_fields: dict


def parse_timestamp(raw) -> datetime:
    if raw:
        try:
            return datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            pass
    return datetime.now(UTC)


def _resolve_related_display(object_type: str, field_name: str, pk) -> str | None:
    """
    Best-effort resolution of a raw FK id (as stored in `snapshots`) to a
    human-readable string, via NetBox's own Django ORM -- something only
    possible because this code runs in-process inside NetBox, unlike the v0
    spike's standalone receiver script (see spec/02-technical-design.md).
    Returns None if resolution isn't possible for any reason; callers must
    tolerate that and fall back to showing the raw id.
    """
    if pk is None:
        return None
    try:
        app_label, model_name = object_type.split(".", 1)
        model = ContentType.objects.get_by_natural_key(app_label, model_name).model_class()
        if not model._meta.get_field(field_name).is_relation:
            return None
        related = model._meta.get_field(field_name).related_model.objects.filter(pk=pk).first()
        return str(related) if related is not None else None
    except Exception:
        return None


def summarize_change(payload: dict) -> str:
    """
    Best-effort one-line summary of what changed, e.g.
    "role changed to 'Core Switch' (was 'Access Switch')".
    """
    snapshots = payload.get("snapshots") or {}
    before = snapshots.get("prechange") or {}
    after = snapshots.get("postchange") or {}
    if not before or not after:
        return payload.get("event", "changed")

    changed_fields = [k for k in after if before.get(k) != after.get(k)]
    if not changed_fields:
        return payload.get("event", "changed")

    field_name = changed_fields[0]
    before_val = before.get(field_name)
    after_val = after.get(field_name)
    object_type = payload.get("object_type", "")

    resolved_after = (payload.get("data") or {}).get(field_name)
    if isinstance(resolved_after, dict) and "display" in resolved_after:
        after_val = resolved_after["display"]
        resolved_before = _resolve_related_display(object_type, field_name, before_val)
        if resolved_before is not None:
            before_val = resolved_before

    return f"{field_name} changed to {after_val!r} (was {before_val!r})"


def _fetch_custom_fields(object_type: str, object_id) -> dict:
    """
    Look up an object's custom_field_data via the ORM. Used for parent
    resolution, where the nested summary in `data` (e.g. `data["device"]`)
    doesn't include the parent's custom fields -- only its id/name/display.
    """
    if object_id is None:
        return {}
    try:
        app_label, model_name = object_type.split(".", 1)
        model = ContentType.objects.get_by_natural_key(app_label, model_name).model_class()
        obj = model.objects.filter(pk=object_id).first()
        return obj.custom_field_data if obj is not None else {}
    except Exception:
        return {}


def resolve_mapping_identity(object_type: str, data: dict) -> tuple[str, str, dict]:
    """
    Returns (mapping_object_type, mapping_object_name, mapping_custom_fields)
    -- the identity to use for Grafana dashboard mapping. For child object
    types listed in PARENT_OBJECT_MAP (e.g. dcim.interface), this resolves to
    the parent object (e.g. its device) instead of the child's own identity,
    since there's no such thing as a per-interface Grafana dashboard.
    """
    parent = PARENT_OBJECT_MAP.get(object_type)
    if parent is None:
        return object_type, data.get("display") or data.get("name") or "unknown", data.get("custom_fields") or {}

    parent_ref = data.get(parent["field"]) or {}
    parent_name = parent_ref.get("display") or parent_ref.get("name")
    if not parent_name:
        # Parent reference missing from the payload -- fall back to the
        # child's own identity rather than mapping against an unknown name.
        return object_type, data.get("display") or data.get("name") or "unknown", data.get("custom_fields") or {}

    parent_custom_fields = _fetch_custom_fields(parent["object_type"], parent_ref.get("id"))
    return parent["object_type"], parent_name, parent_custom_fields


def parse_event(payload: dict) -> ParsedEvent:
    object_type = payload.get("object_type", "unknown")
    data = payload.get("data") or {}
    mapping_object_type, mapping_object_name, mapping_custom_fields = resolve_mapping_identity(object_type, data)

    return ParsedEvent(
        object_type=object_type,
        event=payload.get("event", "unknown"),
        object_repr=data.get("display") or data.get("name") or "unknown",
        object_id=data.get("id"),
        timestamp=parse_timestamp(payload.get("timestamp")),
        summary=summarize_change(payload),
        data=data,
        mapping_object_type=mapping_object_type,
        mapping_object_name=mapping_object_name,
        mapping_custom_fields=mapping_custom_fields,
    )
