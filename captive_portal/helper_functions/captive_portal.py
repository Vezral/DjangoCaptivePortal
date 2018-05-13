import subprocess
import netifaces as netif
import ipaddress
from captive_portal.models import RemoveWiFiQRScheduler
from captive_portal.tasks import remove_remote_user, remove_all_wifi_qr
from datetime import datetime, timedelta
from pytz import timezone
from django.conf import settings

# These variables are used as settings
PORT = 8000  # the port in which the captive portal web server listens
HTTPS_PORT = 8001  # the port in which the captive portal web server listens
IFACE = "wlan0"  # the interface that captive portal protects
wifi_interface = netif.ifaddresses(IFACE)[netif.AF_INET][0]
IP_ADDRESS = wifi_interface['addr']  # the ip address of the captive portal (it can be the IP of IFACE)
NETMASK = wifi_interface['netmask']  # the netmask of the captive portal
NET_ID_WITH_PREFIX = str(ipaddress.IPv4Interface(IP_ADDRESS + '/' + NETMASK).network)


def captive_portal_init():
    kl_timezone = timezone(settings.TIME_ZONE)
    date_to_delete_wifi_qr = datetime.now(kl_timezone).replace(hour=0, minute=0, second=0, microsecond=0)+timedelta(days=1)
    wifi_qr_scheduler_is_exist = RemoveWiFiQRScheduler.objects.filter(pk=1).exists()
    if wifi_qr_scheduler_is_exist:
        wifi_qr_scheduler = RemoveWiFiQRScheduler.objects.get(pk=1)
        if wifi_qr_scheduler.scheduled_time.time() < date_to_delete_wifi_qr.time():
            remove_all_wifi_qr()
            remove_all_wifi_qr.apply_async(eta=date_to_delete_wifi_qr)
            wifi_qr_scheduler.scheduled_time = date_to_delete_wifi_qr
            wifi_qr_scheduler.save()
    else:
        remove_all_wifi_qr.apply_async(eta=date_to_delete_wifi_qr)
        wifi_qr_scheduler = RemoveWiFiQRScheduler.objects.create(scheduled_time=date_to_delete_wifi_qr)
        wifi_qr_scheduler.save()

    print("***************************************************************************")
    print("* Based on nikosfet's captive portal script, available at                  *")
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
