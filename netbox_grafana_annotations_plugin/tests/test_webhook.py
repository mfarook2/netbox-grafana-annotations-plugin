"""
Test cases for NetBox Grafana Annotations Plugin's webhook processing and
receiver view (signature verification, orchestration, AnnotationLog writes).
"""
import hashlib
import hmac
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .. import grafana_client, webhook
from ..models import AnnotationLog

TEST_SECRET = "test-webhook-secret"

TEST_PLUGIN_CONFIG = {
    "netbox_grafana_annotations_plugin": {
        "grafana_url": "http://grafana.test",
        "grafana_token": "test-token",
        "webhook_secret": TEST_SECRET,
    }
}

SAMPLE_PAYLOAD = {
    "event": "updated",
    "object_type": "dcim.device",
    "timestamp": "2026-07-12T18:15:35.897561+00:00",
    "username": "admin",
    "data": {
        "id": 22,
        "display": "dmi01-scranton-sw01",
        "name": "dmi01-scranton-sw01",
        "custom_fields": {},
    },
    "snapshots": {
        "prechange": {"status": "active"},
        "postchange": {"status": "offline"},
    },
}


def sign(body: bytes, secret: str = TEST_SECRET) -> str:
    return hmac.new(key=secret.encode("utf-8"), msg=body, digestmod=hashlib.sha512).hexdigest()


class VerifySignatureTestCase(TestCase):
    def test_valid_signature_accepted(self):
        body = b'{"a": 1}'
        self.assertTrue(webhook.verify_signature(body, sign(body), TEST_SECRET))

    def test_invalid_signature_rejected(self):
        body = b'{"a": 1}'
        self.assertFalse(webhook.verify_signature(body, "not-a-real-signature", TEST_SECRET))

    def test_missing_signature_rejected(self):
        body = b'{"a": 1}'
        self.assertFalse(webhook.verify_signature(body, None, TEST_SECRET))


@override_settings(PLUGINS_CONFIG=TEST_PLUGIN_CONFIG)
class ProcessEventTestCase(TestCase):
    def setUp(self):
        # All tests here share SAMPLE_PAYLOAD's object_type/object_repr, so
        # they'd otherwise share a mapping.py tag-search cache key too --
        # clear it so each test's mock is actually exercised.
        cache.clear()

    def _call(self, payload=SAMPLE_PAYLOAD, secret=TEST_SECRET):
        body = json.dumps(payload).encode()
        return webhook.process_event(payload, raw_body=body, signature_header=sign(body, secret))

    def test_rejects_invalid_signature(self):
        result = webhook.process_event(SAMPLE_PAYLOAD, raw_body=b"x", signature_header="bad")

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "invalid_signature")
        self.assertEqual(AnnotationLog.objects.count(), 0)

    @patch.object(grafana_client, "search_dashboards_by_tag", return_value=[])
    def test_no_mapping_logs_skip_not_failure(self, mock_search):
        result = self._call()

        self.assertFalse(result["success"])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["error"], "no_mapping")

        log_entry = AnnotationLog.objects.get()
        self.assertFalse(log_entry.success)
        self.assertIn("no Grafana dashboard mapping", log_entry.error_detail)

    @patch.object(grafana_client, "post_annotation", return_value=(200, {"id": 1, "message": "Annotation added"}))
    @patch.object(grafana_client, "get_dashboard_panel_ids", return_value=[1])
    @patch.object(grafana_client, "search_dashboards_by_tag", return_value=[{"uid": "found-uid"}])
    def test_successful_annotation_logs_success(self, mock_search, mock_panels, mock_post):
        result = self._call()

        self.assertTrue(result["success"])
        self.assertEqual(result["dashboard_uid"], "found-uid")

        log_entry = AnnotationLog.objects.get()
        self.assertTrue(log_entry.success)
        self.assertEqual(log_entry.dashboard_uid, "found-uid")
        self.assertEqual(log_entry.grafana_response_status, 200)
        self.assertIn("status changed", log_entry.annotation_text)

    @patch.object(grafana_client, "post_annotation", side_effect=grafana_client.GrafanaClientError("connection refused"))
    @patch.object(grafana_client, "get_dashboard_panel_ids", return_value=[1])
    @patch.object(grafana_client, "search_dashboards_by_tag", return_value=[{"uid": "found-uid"}])
    def test_grafana_unreachable_logs_failure(self, mock_search, mock_panels, mock_post):
        result = self._call()

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "grafana_unreachable")

        log_entry = AnnotationLog.objects.get()
        self.assertFalse(log_entry.success)
        self.assertIn("connection refused", log_entry.error_detail)

    @patch.object(grafana_client, "post_annotation", return_value=(500, "internal server error"))
    @patch.object(grafana_client, "get_dashboard_panel_ids", return_value=[1])
    @patch.object(grafana_client, "search_dashboards_by_tag", return_value=[{"uid": "found-uid"}])
    def test_grafana_non_2xx_response_logs_failure(self, mock_search, mock_panels, mock_post):
        result = self._call()

        self.assertFalse(result["success"])
        log_entry = AnnotationLog.objects.get()
        self.assertFalse(log_entry.success)
        self.assertEqual(log_entry.grafana_response_status, 500)

    def test_no_secret_configured_skips_verification(self):
        insecure_config = {
            "netbox_grafana_annotations_plugin": {
                "grafana_url": "http://grafana.test", "grafana_token": "x", "webhook_secret": "",
            }
        }
        with override_settings(PLUGINS_CONFIG=insecure_config):
            with patch.object(grafana_client, "search_dashboards_by_tag", return_value=[]):
                result = webhook.process_event(SAMPLE_PAYLOAD, raw_body=b"anything", signature_header=None)

        # Got past the (skipped) signature check and reached normal processing.
        self.assertEqual(result["error"], "no_mapping")


@override_settings(PLUGINS_CONFIG=TEST_PLUGIN_CONFIG)
class InterfaceEventMapsToParentDeviceTestCase(TestCase):
    """
    Interface is a child object type -- its dashboard mapping should resolve
    through to its parent device (added 2026-07-12 alongside DCIM > Interface
    and Circuits > Circuit support). See spec/02-technical-design.md.
    """

    def setUp(self):
        cache.clear()

    def _interface_payload(self, device):
        return {
            "event": "updated",
            "object_type": "dcim.interface",
            "timestamp": "2026-07-12T21:05:22.987096+00:00",
            "username": "admin",
            "data": {
                "id": 626,
                "display": "GigabitEthernet0",
                "name": "GigabitEthernet0",
                "device": {"id": device.pk, "name": device.name, "display": device.name},
                "custom_fields": {},
            },
            "snapshots": {
                "prechange": {"description": ""},
                "postchange": {"description": "uplink to core"},
            },
        }

    @patch.object(grafana_client, "post_annotation", return_value=(200, {"id": 1}))
    def test_annotation_text_and_tags_mention_both_interface_and_device(self, mock_post):
        from ..testing.utils import create_test_device

        device = create_test_device()
        device.custom_field_data = {"grafana_dashboard_uid": "device-dashboard"}
        device.save()

        payload = self._interface_payload(device)
        body = json.dumps(payload).encode()
        result = webhook.process_event(payload, raw_body=body, signature_header=sign(body))

        self.assertTrue(result["success"])
        self.assertEqual(result["dashboard_uid"], "device-dashboard")

        # Grafana was called with the *device's* dashboard, not anything
        # named after the interface.
        _, call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs["dashboard_uid"], "device-dashboard")
        self.assertIn("GigabitEthernet0", call_kwargs["text"])
        self.assertIn(device.name, call_kwargs["tags"])
        self.assertIn("GigabitEthernet0", call_kwargs["tags"])

        # AnnotationLog still records the *interface* as the object that
        # actually changed, for accurate auditing.
        log_entry = AnnotationLog.objects.get()
        self.assertEqual(log_entry.object_type, "dcim.interface")
        self.assertEqual(log_entry.object_repr, "GigabitEthernet0")
        self.assertEqual(log_entry.dashboard_uid, "device-dashboard")

    @patch.object(grafana_client, "search_dashboards_by_tag")
    def test_no_device_custom_field_falls_back_to_device_tag_search(self, mock_search):
        from ..testing.utils import create_test_device

        device = create_test_device(name="untagged-device")
        mock_search.return_value = []

        payload = self._interface_payload(device)
        body = json.dumps(payload).encode()
        webhook.process_event(payload, raw_body=body, signature_header=sign(body))

        mock_search.assert_called_once_with(mock_search.call_args[0][0], f"netbox:dcim.device:{device.name}")


@override_settings(PLUGINS_CONFIG=TEST_PLUGIN_CONFIG)
class WebhookReceiverViewTestCase(TestCase):
    """
    Confirms the receiver endpoint works *without* any login/session --
    the whole point of it being a plain view authenticated by HMAC signature
    rather than one of NetBox's login-required view classes.
    """

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.url = reverse("plugins:netbox_grafana_annotations_plugin:webhook")

    def test_unauthenticated_request_with_valid_signature_is_processed(self):
        body = json.dumps(SAMPLE_PAYLOAD).encode()

        with patch.object(grafana_client, "search_dashboards_by_tag", return_value=[]):
            response = self.client.post(
                self.url, data=body, content_type="application/json",
                HTTP_X_HOOK_SIGNATURE=sign(body),
            )

        # No mapping found is a handled outcome (200), not a receiver failure.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AnnotationLog.objects.count(), 1)

    @patch.object(grafana_client, "post_annotation", side_effect=grafana_client.GrafanaClientError("boom"))
    @patch.object(grafana_client, "get_dashboard_panel_ids", return_value=[1])
    @patch.object(grafana_client, "search_dashboards_by_tag", return_value=[{"uid": "found-uid"}])
    def test_actual_grafana_failure_returns_502(self, mock_search, mock_panels, mock_post):
        body = json.dumps(SAMPLE_PAYLOAD).encode()

        response = self.client.post(
            self.url, data=body, content_type="application/json",
            HTTP_X_HOOK_SIGNATURE=sign(body),
        )

        self.assertEqual(response.status_code, 502)

    def test_invalid_signature_returns_403(self):
        body = json.dumps(SAMPLE_PAYLOAD).encode()

        response = self.client.post(
            self.url, data=body, content_type="application/json",
            HTTP_X_HOOK_SIGNATURE="wrong",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(AnnotationLog.objects.count(), 0)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            self.url, data=b"not json", content_type="application/json",
            HTTP_X_HOOK_SIGNATURE=sign(b"not json"),
        )
        self.assertEqual(response.status_code, 400)

    def test_get_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
