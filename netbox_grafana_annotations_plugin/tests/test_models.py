"""
Test cases for NetBox Grafana Annotations Plugin models.
"""
from datetime import timedelta

from django.utils import timezone

from ..models import AnnotationLog
from ..testing import PluginModelTestCase


class AnnotationLogTestCase(PluginModelTestCase):
    """Test AnnotationLog model."""

    @classmethod
    def setUpTestData(cls):
        AnnotationLog.objects.create(
            triggered_at=timezone.now(),
            object_type="dcim.device",
            event_type="updated",
            object_repr="dmi01-scranton-sw01",
            dashboard_uid="netbox-spike-test",
            panel_id=1,
            annotation_text="netbox: role changed to 'Core Switch' (was 'Access Switch')",
            success=True,
            grafana_response_status=200,
        )

    def test_str_includes_object_and_event(self):
        instance = AnnotationLog.objects.first()
        self.assertIn(instance.object_repr, str(instance))
        self.assertIn(instance.event_type, str(instance))

    def test_absolute_url(self):
        instance = AnnotationLog.objects.first()
        url = instance.get_absolute_url()
        self.assertIn(str(instance.pk), url)

    def test_default_ordering_is_most_recent_first(self):
        older = AnnotationLog.objects.create(
            triggered_at=timezone.now() - timedelta(hours=1),
            object_type="dcim.device",
            event_type="updated",
            object_repr="older-device",
        )
        newest = AnnotationLog.objects.create(
            triggered_at=timezone.now() + timedelta(hours=1),
            object_type="dcim.device",
            event_type="updated",
            object_repr="newest-device",
        )

        ordered = list(AnnotationLog.objects.all())
        self.assertEqual(ordered[0], newest)
        self.assertIn(older, ordered)

    def test_success_defaults_to_false(self):
        instance = AnnotationLog.objects.create(
            triggered_at=timezone.now(),
            object_type="dcim.device",
            event_type="deleted",
            object_repr="gone-device",
        )
        self.assertFalse(instance.success)
        self.assertIsNone(instance.grafana_response_status)
