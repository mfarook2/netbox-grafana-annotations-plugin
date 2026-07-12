"""
Test cases for NetBox Grafana Annotations Plugin's AnnotationLog views.

AnnotationLog has no Add/Edit views -- entries are only ever created by the
webhook receiver (see tests/test_webhook.py for that endpoint's tests).
"""
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from ..models import AnnotationLog
from ..testing import PluginViewTestCase
from ..testing.utils import disable_warnings


class AnnotationLogViewTestCase(PluginViewTestCase):
    """Test AnnotationLog list/detail/delete views."""

    @classmethod
    def setUpTestData(cls):
        AnnotationLog.objects.create(
            triggered_at=timezone.now(),
            object_type="dcim.device",
            event_type="updated",
            object_repr="View Test 1",
        )
        AnnotationLog.objects.create(
            triggered_at=timezone.now(),
            object_type="dcim.device",
            event_type="created",
            object_repr="View Test 2",
        )

    def setUp(self):
        super().setUp()
        self.base_url = "plugins:netbox_grafana_annotations_plugin:annotationlog"

    def test_list_view(self):
        self.add_permissions("netbox_grafana_annotations_plugin.view_annotationlog")

        url = reverse("plugins:netbox_grafana_annotations_plugin:annotationlog_list")
        response = self.client.get(url)

        self.assertHttpStatus(response, 200)

    def test_list_view_without_permission(self):
        url = reverse("plugins:netbox_grafana_annotations_plugin:annotationlog_list")

        with disable_warnings("django.request"):
            response = self.client.get(url)
            self.assertHttpStatus(response, 403)

    def test_detail_view(self):
        self.add_permissions("netbox_grafana_annotations_plugin.view_annotationlog")

        instance = AnnotationLog.objects.first()
        url = reverse("plugins:netbox_grafana_annotations_plugin:annotationlog", kwargs={"pk": instance.pk})
        response = self.client.get(url)

        self.assertHttpStatus(response, 200)
        self.assertEqual(response.context["object"], instance)

    def test_delete_view(self):
        self.add_permissions(
            "netbox_grafana_annotations_plugin.delete_annotationlog",
            "netbox_grafana_annotations_plugin.view_annotationlog",
        )

        instance = AnnotationLog.objects.first()
        url = reverse("plugins:netbox_grafana_annotations_plugin:annotationlog_delete", kwargs={"pk": instance.pk})

        response = self.client.post(url, {"confirm": True}, follow=True)
        self.assertHttpStatus(response, 200)
        self.assertFalse(AnnotationLog.objects.filter(pk=instance.pk).exists())

    def test_delete_view_without_permission(self):
        instance = AnnotationLog.objects.first()
        url = reverse("plugins:netbox_grafana_annotations_plugin:annotationlog_delete", kwargs={"pk": instance.pk})

        with disable_warnings("django.request"):
            response = self.client.get(url)
            self.assertHttpStatus(response, 403)

    def test_no_add_or_edit_urls_registered(self):
        """AnnotationLog entries are system-generated only -- confirm there's no add/edit route."""
        for url_name in ("annotationlog_add", "annotationlog_edit"):
            with self.assertRaises(NoReverseMatch):
                reverse(f"plugins:netbox_grafana_annotations_plugin:{url_name}")
