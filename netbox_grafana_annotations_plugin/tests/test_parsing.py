"""
Test cases for NetBox Grafana Annotations Plugin payload parsing.

Payload shape confirmed against a live NetBox v4.6.4 instance (2026-07-12
spike, see spec/02-technical-design.md): snapshots.prechange/postchange
store raw FK ids, only `data` has resolved display names for the current
(post-change) value.
"""
from datetime import datetime

from django.test import TestCase

from .. import parsing
from ..testing.utils import create_test_device


class ParseTimestampTestCase(TestCase):
    def test_parses_iso_with_offset(self):
        result = parsing.parse_timestamp("2026-07-12T18:15:35.897561+00:00")
        self.assertEqual(result.year, 2026)
        self.assertIsNotNone(result.tzinfo)

    def test_falls_back_to_now_on_missing_timestamp(self):
        result = parsing.parse_timestamp(None)
        self.assertIsInstance(result, datetime)


class SummarizeChangeTestCase(TestCase):
    def test_resolves_fk_before_and_after_display_names(self):
        """
        This is the case the v0 spike couldn't handle (spec/02-technical-design.md):
        resolving the *before* value of a changed FK field to a human-readable
        name, only possible because this code runs in-process with ORM access.
        """
        from dcim.models import DeviceRole

        device = create_test_device()
        core_role, _ = DeviceRole.objects.get_or_create(
            name="Core Switch", slug="core-switch", defaults={"color": "f44336"}
        )

        payload = {
            "event": "updated",
            "object_type": "dcim.device",
            "data": {
                "id": device.pk,
                "display": device.name,
                "role": {"id": core_role.pk, "display": core_role.name},
                "custom_fields": {},
            },
            "snapshots": {
                "prechange": {"role": device.role.pk},
                "postchange": {"role": core_role.pk},
            },
        }

        summary = parsing.summarize_change(payload)
        self.assertEqual(summary, f"role changed to 'Core Switch' (was '{device.role.name}')")

    def test_falls_back_to_raw_id_when_before_unresolvable(self):
        payload = {
            "event": "updated",
            "object_type": "dcim.device",
            "data": {
                "id": 999,
                "display": "test-device",
                "role": {"id": 2, "display": "Core Switch"},
                "custom_fields": {},
            },
            "snapshots": {
                "prechange": {"role": 999999},  # no DeviceRole with this pk
                "postchange": {"role": 2},
            },
        }
        summary = parsing.summarize_change(payload)
        self.assertEqual(summary, "role changed to 'Core Switch' (was 999999)")

    def test_no_snapshots_falls_back_to_event_name(self):
        self.assertEqual(parsing.summarize_change({"event": "created"}), "created")

    def test_no_changed_fields_falls_back_to_event_name(self):
        payload = {
            "event": "updated",
            "snapshots": {"prechange": {"status": "active"}, "postchange": {"status": "active"}},
        }
        self.assertEqual(parsing.summarize_change(payload), "updated")

    def test_non_relation_field_change_uses_raw_values(self):
        payload = {
            "event": "updated",
            "object_type": "dcim.device",
            "data": {"id": 1, "display": "test-device", "custom_fields": {}},
            "snapshots": {
                "prechange": {"status": "active"},
                "postchange": {"status": "offline"},
            },
        }
        summary = parsing.summarize_change(payload)
        self.assertEqual(summary, "status changed to 'offline' (was 'active')")


class ParseEventTestCase(TestCase):
    def test_extracts_expected_fields(self):
        payload = {
            "event": "updated",
            "object_type": "dcim.device",
            "timestamp": "2026-07-12T18:15:35.897561+00:00",
            "data": {"id": 22, "display": "dmi01-scranton-sw01", "custom_fields": {}},
            "snapshots": {"prechange": {"status": "active"}, "postchange": {"status": "offline"}},
        }
        event = parsing.parse_event(payload)

        self.assertEqual(event.object_type, "dcim.device")
        self.assertEqual(event.event, "updated")
        self.assertEqual(event.object_repr, "dmi01-scranton-sw01")
        self.assertEqual(event.object_id, 22)
        self.assertIn("status changed", event.summary)
        self.assertEqual(event.data["custom_fields"], {})

    def test_defaults_when_fields_missing(self):
        event = parsing.parse_event({})
        self.assertEqual(event.object_type, "unknown")
        self.assertEqual(event.event, "unknown")
        self.assertEqual(event.object_repr, "unknown")
        self.assertIsNone(event.object_id)

    def test_top_level_object_maps_to_its_own_identity(self):
        """Device (and other top-level objects like Circuit) map to themselves."""
        payload = {
            "event": "updated",
            "object_type": "dcim.device",
            "data": {"id": 22, "display": "dmi01-scranton-sw01", "custom_fields": {"grafana_dashboard_uid": "abc"}},
        }
        event = parsing.parse_event(payload)

        self.assertEqual(event.mapping_object_type, "dcim.device")
        self.assertEqual(event.mapping_object_name, "dmi01-scranton-sw01")
        self.assertEqual(event.mapping_custom_fields, {"grafana_dashboard_uid": "abc"})


class ResolveMappingIdentityTestCase(TestCase):
    """Interface is a child object -- it should map through to its parent device."""

    def test_interface_resolves_to_parent_device(self):
        from ..testing.utils import create_test_device

        device = create_test_device()
        device.custom_field_data = {"grafana_dashboard_uid": "device-dashboard"}
        device.save()

        data = {
            "id": 1,
            "display": "GigabitEthernet0/0/1",
            "device": {"id": device.pk, "name": device.name, "display": device.name},
            "custom_fields": {},
        }
        mapping_type, mapping_name, mapping_cf = parsing.resolve_mapping_identity("dcim.interface", data)

        self.assertEqual(mapping_type, "dcim.device")
        self.assertEqual(mapping_name, device.name)
        self.assertEqual(mapping_cf, {"grafana_dashboard_uid": "device-dashboard"})

    def test_interface_without_device_ref_falls_back_to_its_own_identity(self):
        data = {"id": 1, "display": "GigabitEthernet0/0/1", "custom_fields": {}}
        mapping_type, mapping_name, mapping_cf = parsing.resolve_mapping_identity("dcim.interface", data)

        self.assertEqual(mapping_type, "dcim.interface")
        self.assertEqual(mapping_name, "GigabitEthernet0/0/1")

    def test_unknown_parent_device_id_yields_empty_custom_fields(self):
        data = {
            "id": 1,
            "display": "GigabitEthernet0/0/1",
            "device": {"id": 999999, "name": "ghost-device", "display": "ghost-device"},
            "custom_fields": {},
        }
        mapping_type, mapping_name, mapping_cf = parsing.resolve_mapping_identity("dcim.interface", data)

        self.assertEqual(mapping_type, "dcim.device")
        self.assertEqual(mapping_name, "ghost-device")
        self.assertEqual(mapping_cf, {})
