from __future__ import absolute_import, unicode_literals
from celery import task
from datetime import datetime, timedelta
from pytz import timezone
from django.conf import settings
from captive_portal.helper_functions import captive_portal
from captive_portal.models import WiFiToken, RemoveWiFiTokenScheduler, WifiTokenAssociatedIPAddress, AllocatedBandwidth
import subprocess
import redis


@task
def add_remote_user(remote_IP, wifi_token_id):
    with redis.Redis().lock('iptables'):
        allocated_bandwidth = AllocatedBandwidth.objects.get(pk=1)
        download_speed = allocated_bandwidth.download_speed_in_Kbps
        upload_speed = allocated_bandwidth.upload_speed_in_Kbps
        # set iptables for internet access
        subprocess.call(["iptables", "-t", "nat", "-I", "PREROUTING", "1", "-s", remote_IP, "-j", "ACCEPT", "-w", "1"])
        subprocess.call(["iptables", "-I", "FORWARD", "-s", remote_IP, "-i", captive_portal.IFACE, "-j", "ACCEPT", "-w", "1"])
        # set tcconfig for rate control
        if download_speed != 0:
            subprocess.call(["tcset", "--device", captive_portal.IFACE, "--rate", str(download_speed)+"Kbps", "--direction", "outgoing", "--network", remote_IP, "--add"])
        if upload_speed != 0:
            subprocess.call(["tcset", "--device", captive_portal.IFACE, "--rate", str(upload_speed)+"Kbps", "--direction", "ingoing", "--src-network", remote_IP, "--add"])
        # add remote user IP to sqlite database
        wifi_token = WiFiToken.objects.get(pk=wifi_token_id)
        remote_user = WifiTokenAssociatedIPAddress(token=wifi_token, ip_address=remote_IP)
        remote_user.save()
        # set schedule to remove remote user after token expire
        kl_timezone = timezone(settings.TIME_ZONE)
        expiration_time = wifi_token.expiration_time.astimezone(kl_timezone)
        remove_remote_user.apply_async(args=[remote_IP], eta=expiration_time)
        print(".. Added remote user {}".format(remote_IP))

@task
def remove_remote_user(remote_IP):
    with redis.Redis().lock('iptables'):
        # delete iptables entry to revoke internet access
        subprocess.call(["iptables", "-t", "nat", "-D", "PREROUTING", "-s", remote_IP, "-j", "ACCEPT", "-w", "1"])
        subprocess.call(["iptables", "-D", "FORWARD", "-s", remote_IP, "-i", captive_portal.IFACE, "-j", "ACCEPT", "-w", "1"])
        # delete tcconfig to remove rate control for the revoked user
        subprocess.call(["tcdel", "--device", captive_portal.IFACE, "--direction", "outgoing", "--network", remote_IP])
        subprocess.call(["tcdel", "--device", captive_portal.IFACE, "--direction", "incoming", "--src-network", remote_IP])
        print(".. Deleted {} from iptables and tc".format(remote_IP))


@task
def remove_wifi_qr(token):
    with redis.Redis().lock('iptables'):
        is_valid = WiFiToken.objects.filter(token=token).exists()
        if is_valid:
            wifi_token = WiFiToken.objects.get(token=token)
            wifi_token.delete()
            print(".. Deleted token: {}".format(token))


@task
def remove_all_wifi_qr():
    with redis.Redis().lock('iptables'):
        kl_timezone = timezone(settings.TIME_ZONE)
        date_to_delete_wifi_qr = datetime.now(kl_timezone).replace(hour=0, minute=0, second=0, microsecond=0)+timedelta(days=1)
        for wifi_token in WiFiToken.objects.all():
            wifi_token.delete()
        remove_all_wifi_qr.apply_async(eta=date_to_delete_wifi_qr)
        wifi_token_scheduler = RemoveWiFiTokenScheduler.objects.get(pk=1)
        wifi_token_scheduler.scheduled_time = date_to_delete_wifi_qr
        wifi_token_scheduler.save()
        print(".. Remove all QR")
