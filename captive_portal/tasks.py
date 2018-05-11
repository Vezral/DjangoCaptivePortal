from __future__ import absolute_import, unicode_literals
from celery import task
from datetime import datetime
from pytz import timezone
from django.conf import settings
from captive_portal.helper_functions import captive_portal
from captive_portal.models import WiFiQR, RemoveWiFiQRScheduler
import subprocess


@task
def remove_remote_user(remote_IP):
    subprocess.call(["iptables", "-t", "nat", "-D", "PREROUTING", "-s", remote_IP, "-j", "ACCEPT"])
    subprocess.call(["iptables", "-D", "FORWARD", "-s", remote_IP, "-i", captive_portal.IFACE, "-j", "ACCEPT"])
    print(".. Deleted {} from iptables".format(remote_IP))


@task
def remove_all_wifi_qr():
    kl_timezone = timezone(settings.TIME_ZONE)
    date_to_delete_wifi_qr = datetime.now(kl_timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    for wifi_qr in WiFiQR.objects.all():
        wifi_qr.delete()
    remove_all_wifi_qr.apply_async(eta=date_to_delete_wifi_qr)
    wifi_qr_scheduler = RemoveWiFiQRScheduler.objects.get(pk=1)
    wifi_qr_scheduler.scheduled_time = date_to_delete_wifi_qr
    wifi_qr_scheduler.save()
