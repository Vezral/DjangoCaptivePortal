from __future__ import absolute_import, unicode_literals
from celery import task
from datetime import datetime, timedelta
from pytz import timezone
from django.conf import settings
from captive_portal.helper_functions import captive_portal
from captive_portal.models import WiFiQR, RemoveWiFiQRScheduler
import subprocess
import os


@task
def add_remote_user(remote_IP, qr_id):
    subprocess.call(["iptables","-t", "nat", "-I", "PREROUTING", "1", "-s", remote_IP, "-j", "ACCEPT"])
    subprocess.call(["iptables", "-I", "FORWARD", "-s", remote_IP, "-i", captive_portal.IFACE, "-j", "ACCEPT"])
    qr = WiFiQR.objects.get(pk=qr_id)
    kl_timezone = timezone(settings.TIME_ZONE)
    expiration_time = qr.expiration_time.astimezone(kl_timezone)
    remove_remote_user.apply_async(args=[remote_IP], eta=expiration_time)

@task
def remove_remote_user(remote_IP):
    subprocess.call(["iptables", "-t", "nat", "-D", "PREROUTING", "-s", remote_IP, "-j", "ACCEPT"])
    subprocess.call(["iptables", "-D", "FORWARD", "-s", remote_IP, "-i", captive_portal.IFACE, "-j", "ACCEPT"])
    print(".. Deleted {} from iptables".format(remote_IP))


@task
def remove_wifi_qr(token):
    is_valid = WiFiQR.objects.filter(token=token).exists()
    if is_valid:
        wifi_qr = WiFiQR.objects.get(token=token)
        os.remove(wifi_qr.qr_code.path)
        wifi_qr.delete()
        print(".. Deleted token: {}".format(token))


@task
def remove_all_wifi_qr():
    kl_timezone = timezone(settings.TIME_ZONE)
    date_to_delete_wifi_qr = datetime.now(kl_timezone).replace(hour=0, minute=0, second=0, microsecond=0)+timedelta(days=1)
    for wifi_qr in WiFiQR.objects.all():
        wifi_qr.delete()
    remove_all_wifi_qr.apply_async(eta=date_to_delete_wifi_qr)
    wifi_qr_scheduler = RemoveWiFiQRScheduler.objects.get(pk=1)
    wifi_qr_scheduler.scheduled_time = date_to_delete_wifi_qr
    wifi_qr_scheduler.save()
