from django.contrib import admin
from .models import WiFiToken, WifiTokenAssociatedIPAddress, AllocatedBandwidth, RemoveWiFiTokenScheduler

admin.site.register(WiFiToken)
admin.site.register(WifiTokenAssociatedIPAddress)
admin.site.register(AllocatedBandwidth)
admin.site.register(RemoveWiFiTokenScheduler)