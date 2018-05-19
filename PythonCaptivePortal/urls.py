"""captive_portal URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path, re_path
from django.conf import settings
from django.views.generic.base import RedirectView
from django.conf.urls.static import static
from django.db import utils
from captive_portal.helper_functions.captive_portal import captive_portal_init, check_remove_wifi_token_scheduler, check_allocated_bandwidth, remove_all_wifi_qr
from captive_portal.models import RemoveWiFiTokenScheduler

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', include('captive_portal.urls')),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    re_path(r'^.*$', RedirectView.as_view(url='/login/'), name='index'),
]

try:
    RemoveWiFiTokenScheduler.objects.filter(pk=1).exists()  # just checking if sqlite database has been created yet
    check_remove_wifi_token_scheduler()
    check_allocated_bandwidth()
    captive_portal_init()
# if database doesn't exist (i.e. during makemigrations after deleting sqlite)
except utils.OperationalError:
    pass
