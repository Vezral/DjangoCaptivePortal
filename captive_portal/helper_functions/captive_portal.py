from captive_portal.models import RemoveWiFiTokenScheduler, WiFiToken, AllocatedBandwidth
from captive_portal.tasks import remove_all_wifi_qr
from datetime import datetime, timedelta
from pytz import timezone
from django.conf import settings
import subprocess
import netifaces as netif
import ipaddress
import redis

# These variables are used as settings
PORT = 8000  # the port in which the HTTP captive portal web server listens
HTTPS_PORT = 8001  # the port in which the HTTPS captive portal web server listens
IFACE = "wlan0"  # the interface that captive portal protects
wifi_interface = netif.ifaddresses(IFACE)[netif.AF_INET][0]
IP_ADDRESS = wifi_interface['addr']  # the ip address of the captive portal (it can be the IP of IFACE)
NETMASK = wifi_interface['netmask']  # the netmask of the captive portal
NET_ID_WITH_PREFIX = str(ipaddress.IPv4Interface(IP_ADDRESS + '/' + NETMASK).network)


# check if iptables is empty; if empty, populate it
def captive_portal_init():
    compare_string = "-d {}".format(IP_ADDRESS)
    current_iptable_output = subprocess.check_output(["iptables", "-S"]).decode('utf-8')
    if compare_string not in current_iptable_output:
        print("***************************************************************************")
        print("* Based on nikosft's captive portal script, available at                  *")
        print("* https://github.com/nikosft/captive-portal/blob/master/captive_portal.py *")
        print("***************************************************************************")
        print("Updating iptables")
        print(".. Flushing iptables")
        subprocess.call(["iptables", "-F"])
        print(".. Flushing nat tables")
        subprocess.call(["iptables", "-t", "nat", "-F"])
        print(".. Adding MASQUERADE to share local Internet")
        subprocess.call(["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", NET_ID_WITH_PREFIX, "!", "-d", NET_ID_WITH_PREFIX, "-j", "MASQUERADE"])
        print(".. Allow TCP DNS")
        subprocess.call(["iptables", "-A", "FORWARD", "-i", IFACE, "-p", "tcp", "--dport", "53", "-j", "ACCEPT"])
        print(".. Allow UDP DNS")
        subprocess.call(["iptables", "-A", "FORWARD", "-i", IFACE, "-p", "udp", "--dport", "53", "-j", "ACCEPT"])
        print(".. Allow traffic to captive portal")
        subprocess.call(["iptables", "-A", "FORWARD", "-i", IFACE, "-p", "tcp", "--dport", str(PORT), "-d", IP_ADDRESS, "-j", "ACCEPT"])
        print(".. Block all other traffic")
        subprocess.call(["iptables", "-A", "FORWARD", "-i", IFACE, "-j", "REJECT"])
        print("Redirecting HTTP traffic to captive portal")
        subprocess.call(["iptables", "-t", "nat", "-I", "PREROUTING", "-i", IFACE, "-p", "tcp", "--dport", "80", "-j", "DNAT", "--to-destination", IP_ADDRESS+":"+str(PORT)])
        print("Starting celery ..")
        subprocess.Popen(["celery", "-A", "PythonCaptivePortal", "worker", "-l", "info"])


# check if remove_all_wifi_qr scheduler has been set; if not then set it
def check_remove_wifi_token_scheduler():
    if RemoveWiFiTokenScheduler.objects.filter(pk=1).exists() is False:
        kl_timezone = timezone(settings.TIME_ZONE)
        date_to_delete_wifi_qr = datetime.now(kl_timezone).replace(hour=0, minute=0, second=0, microsecond=0)+timedelta(days=1)
        remove_all_wifi_qr.apply_async(eta=date_to_delete_wifi_qr)
        remove_wifi_token_scheduler = RemoveWiFiTokenScheduler.objects.create(scheduled_time=date_to_delete_wifi_qr)
        remove_wifi_token_scheduler.save()
        print("Added remove_wifi_token_scheduler")


def check_allocated_bandwidth():
    # check if AllocatedTable exists; if not then create it
    if AllocatedBandwidth.objects.filter(pk=1).exists() is False:
        allocated_bandwith = AllocatedBandwidth()
        allocated_bandwith.save()
        print("Added allocated_bandiwdth object")
    # else alter download / upload speed to match value in database
    else:
        allocated_bandwith = AllocatedBandwidth.objects.get(pk=1)
        limit_download_speed(allocated_bandwith.download_speed_in_Kbps)
        limit_upload_speed(allocated_bandwith.upload_speed_in_Kbps)


# get all ip address from all existing wifi tokens, delete them from tc, and add new tc if download != 0
def limit_download_speed(download_speed_in_Kbps):
    with redis.Redis().lock('iptables'):
        # altering tc table for all existing user
        for wifi_token in WiFiToken.objects.all():
            for remote_IP in wifi_token.wifitokenassociatedipaddress_set.all():
                subprocess.call(["tcdel", "--device", IFACE, "--direction", "outgoing", "--network", remote_IP.ip_address])
                if download_speed_in_Kbps != 0:
                    subprocess.call(["tcset", "--device", IFACE, "--rate", str(download_speed_in_Kbps) + "Kbps", "--direction", "outgoing", "--network", remote_IP.ip_address, "--add"])


# get all ip address from all existing wifi tokens, delete them from tc, and add new tc if upload_speed != 0
def limit_upload_speed(upload_speed_in_Kbps):
    with redis.Redis().lock('iptables'):
        # altering tc table for all existing user
        for wifi_token in WiFiToken.objects.all():
            for remote_IP in wifi_token.wifitokenassociatedipaddress_set.all():
                subprocess.call(["tcdel", "--device", IFACE, "--direction", "incoming", "--src-network", remote_IP.ip_address])
                if upload_speed_in_Kbps != 0:
                    subprocess.call(["tcset", "--device", IFACE, "--rate", str(upload_speed_in_Kbps) + "Kbps", "--direction", "incoming", "--src-network", remote_IP.ip_address, "--add"])
