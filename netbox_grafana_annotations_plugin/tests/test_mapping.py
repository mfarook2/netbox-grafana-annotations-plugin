"""
Test cases for NetBox Grafana Annotations Plugin's object -> dashboard mapping.

Resolution order under test (spec/02-technical-design.md, resolved 2026-07-12):
custom field override first, then live Grafana tag-search with caching.
"""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from .. import grafana_client, mapping
from ..settings import get_settings

TEST_PLUGIN_CONFIG = {
    "netbox_grafana_annotations_plugin": {
        "grafana_url": "http://grafana.test",
        "grafana_token": "test-token",
    }
}


@override_settings(PLUGINS_CONFIG=TEST_PLUGIN_CONFIG)
class ResolveTargetTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.settings = get_settings()

    def test_custom_field_override_wins_without_calling_grafana(self):
        data = {"custom_fields": {"grafana_dashboard_uid": "manual-uid", "grafana_panel_id": 4}}

        with patch.object(grafana_client, "search_dashboards_by_tag") as mock_search:
            result = mapping.resolve_target(self.settings, "dcim.device", "test-device", data)

        mock_search.assert_not_called()
        self.assertEqual(result.dashboard_uid, "manual-uid")
        self.assertEqual(result.panel_id, 4)

    @patch.object(grafana_client, "get_dashboard_panel_ids")
    @patch.object(grafana_client, "search_dashboards_by_tag")
    def test_tag_search_used_when_no_override(self, mock_search, mock_panels):
        mock_search.return_value = [{"uid": "found-uid"}]
        mock_panels.return_value = [7]

        result = mapping.resolve_target(self.settings, "dcim.device", "test-device", {"custom_fields": {}})

        mock_search.assert_called_once_with(self.settings, "netbox:dcim.device:test-device")
        self.assertEqual(result.dashboard_uid, "found-uid")
        self.assertEqual(result.panel_id, 7)

    @patch.object(grafana_client, "get_dashboard_panel_ids")
    @patch.object(grafana_client, "search_dashboards_by_tag")
    def test_panel_id_omitted_when_dashboard_has_multiple_panels(self, mock_search, mock_panels):
        mock_search.return_value = [{"uid": "found-uid"}]
        mock_panels.return_value = [1, 2, 3]

        result = mapping.resolve_target(self.settings, "dcim.device", "test-device", {"custom_fields": {}})

        self.assertEqual(result.dashboard_uid, "found-uid")
        self.assertIsNone(result.panel_id)

    @patch.object(grafana_client, "search_dashboards_by_tag")
    def test_no_match_returns_none(self, mock_search):
        mock_search.return_value = []

        result = mapping.resolve_target(self.settings, "dcim.device", "test-device", {"custom_fields": {}})

        self.assertIsNone(result)

    @patch.object(grafana_client, "search_dashboards_by_tag")
    def test_search_result_is_cached(self, mock_search):
        mock_search.return_value = [{"uid": "cached-uid"}]

        with patch.object(grafana_client, "get_dashboard_panel_ids", return_value=[1]):
            mapping.resolve_target(self.settings, "dcim.device", "test-device", {"custom_fields": {}})
            mapping.resolve_target(self.settings, "dcim.device", "test-device", {"custom_fields": {}})

        mock_search.assert_called_once()

    @patch.object(grafana_client, "search_dashboards_by_tag")
    def test_negative_result_is_also_cached(self, mock_search):
        mock_search.return_value = []

        mapping.resolve_target(self.settings, "dcim.device", "test-device", {"custom_fields": {}})
        mapping.resolve_target(self.settings, "dcim.device", "test-device", {"custom_fields": {}})

        mock_search.assert_called_once()

    @patch.object(grafana_client, "search_dashboards_by_tag", side_effect=grafana_client.GrafanaClientError("boom"))
    def test_grafana_unreachable_returns_none_not_raises(self, mock_search):
        result = mapping.resolve_target(self.settings, "dcim.device", "test-device", {"custom_fields": {}})
        self.assertIsNone(result)
