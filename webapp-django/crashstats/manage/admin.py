# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import hashlib
from urllib.parse import urlparse

import requests

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db import connection
from django.shortcuts import redirect, render

from crashstats.crashstats.models import GraphicsDevice
from crashstats.manage import forms
from crashstats.manage import utils
from crashstats.manage.decorators import superuser_required
from crashstats.supersearch.models import SuperSearchMissingFields


@superuser_required
def crash_me_now(request):
    # NOTE(willkg): This intentionally throws an error so that we can test
    # unhandled error handling.
    1 / 0  # noqa


@superuser_required
def site_status(request):
    context = {}

    # Get version information for deployed parts
    version_info = {}
    for url in settings.OVERVIEW_VERSION_URLS.split(","):
        hostname = urlparse(url).netloc
        url = url.strip()
        try:
            data = requests.get(url).json()
        except Exception as exc:
            data = {"error": str(exc)}
        version_info[hostname] = data

    context["version_info"] = version_info

    # Get Django migration data
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, app, name, applied FROM django_migrations")
            cols = [col[0] for col in cursor.description]
            django_db_data = [dict(zip(cols, row)) for row in cursor.fetchall()]
            django_db_error = ""
    except Exception as exc:
        django_db_data = []
        django_db_error = "error: %s" % exc
    context["django_db_data"] = django_db_data
    context["django_db_error"] = django_db_error

    context["title"] = "Site status"

    return render(request, "admin/site_status.html", context)


@superuser_required
def analyze_model_fetches(request):
    context = {}
    all_ = cache.get("all_classes") or []
    records = []
    for item in all_:
        itemkey = hashlib.md5(item.encode("utf-8")).hexdigest()

        data = {}
        data["times"] = {}
        data["times"]["hits"] = cache.get("times_HIT_%s" % itemkey, 0)
        data["times"]["misses"] = cache.get("times_MISS_%s" % itemkey, 0)
        data["times"]["both"] = data["times"]["hits"] + data["times"]["misses"]
        data["uses"] = {}
        data["uses"]["hits"] = cache.get("uses_HIT_%s" % itemkey, 0)
        data["uses"]["misses"] = cache.get("uses_MISS_%s" % itemkey, 0)
        data["uses"]["both"] = data["uses"]["hits"] + data["uses"]["misses"]
        data["uses"]["hits_percentage"] = (
            data["uses"]["both"]
            and round(100.0 * data["uses"]["hits"] / data["uses"]["both"], 1)
            or "n/a"
        )
        records.append((item, data))
    context["records"] = records
    context["title"] = "Analyze model fetches"

    return render(request, "admin/analyze-model-fetches.html", context)


@superuser_required
def supersearch_fields_missing(request):
    context = {}
    missing_fields = SuperSearchMissingFields().get()

    context["missing_fields"] = missing_fields["hits"]
    context["missing_fields_count"] = missing_fields["total"]
    context["title"] = "Super search missing fields"

    return render(request, "admin/supersearch_fields_missing.html", context)


@superuser_required
def graphics_devices(request):
    context = {}
    upload_form = forms.GraphicsDeviceUploadForm()

    if request.method == "POST" and "file" in request.FILES:
        upload_form = forms.GraphicsDeviceUploadForm(request.POST, request.FILES)
        if upload_form.is_valid():
            devices = utils.pci_ids__parse_graphics_devices_iterable(
                upload_form.cleaned_data["file"]
            )

            for item in devices:
                obj, _ = GraphicsDevice.objects.get_or_create(
                    vendor_hex=item["vendor_hex"], adapter_hex=item["adapter_hex"]
                )
                obj.vendor_name = item["vendor_name"]
                obj.adapter_name = item["adapter_name"]
                obj.save()

            messages.success(request, "Graphics device CSV upload successfully saved.")
            return redirect("siteadmin:graphics_devices")

    context["title"] = "Graphics devices"
    context["upload_form"] = upload_form
    return render(request, "admin/graphics_devices.html", context)
