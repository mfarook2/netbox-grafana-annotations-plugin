"""
Views for NetBox Grafana Annotations Plugin.

For more information on NetBox views, see:
https://docs.netbox.dev/en/stable/plugins/development/views/
"""
import json
import logging

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from netbox.views import generic

from . import filtersets, tables
from .models import AnnotationLog
from .webhook import process_event

logger = logging.getLogger("netbox_grafana_annotations_plugin")


class AnnotationLogView(generic.ObjectView):
    queryset = AnnotationLog.objects.all()


class AnnotationLogListView(generic.ObjectListView):
    queryset = AnnotationLog.objects.all()
    table = tables.AnnotationLogTable
    filterset = filtersets.AnnotationLogFilterSet


class AnnotationLogDeleteView(generic.ObjectDeleteView):
    queryset = AnnotationLog.objects.all()


@method_decorator(csrf_exempt, name="dispatch")
class WebhookReceiverView(View):
    """
    Receives NetBox Event Rule webhook POSTs and turns them into Grafana
    annotations. Deliberately a plain Django View -- not one of NetBox's
    generic/login-required view classes -- since this endpoint is called by
    NetBox's own webhook worker (no user session exists to authenticate).
    Authenticity is instead verified via the X-Hook-Signature HMAC header
    NetBox itself sends when a Secret is configured on the Webhook object
    (see spec/02-technical-design.md for why this approach was chosen over
    relying on AUTH_EXEMPT_PATHS or a NetBox API token).
    """

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"detail": "invalid JSON body"}, status=400)

        result = process_event(payload, raw_body=request.body, signature_header=request.headers.get("X-Hook-Signature"))

        if result.get("error") == "invalid_signature":
            return JsonResponse({"detail": "invalid signature"}, status=403)

        # "skipped" (no dashboard mapping) is a handled outcome, not a
        # receiver failure -- only an actual Grafana post failure should
        # surface as a failed delivery in NetBox's own webhook tracking.
        status = 200 if (result.get("success") or result.get("skipped")) else 502
        return JsonResponse(result, status=status)

    def get(self, request, *args, **kwargs):
        return JsonResponse({"detail": "POST required"}, status=405)
