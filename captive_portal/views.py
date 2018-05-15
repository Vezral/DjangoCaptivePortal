from datetime import datetime, timedelta
from ipware import get_client_ip
from django.core.files import File
from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from captive_portal.helper_functions import captive_portal
from pytz import timezone
from django.conf import settings
from .tasks import remove_wifi_qr, add_remote_user
from .models import WiFiToken, AllocatedBandwidth, WifiTokenAssociatedIPAddress
import pyqrcode
import pyotp
import os


class LoginPage(TemplateView):

    def get(self, request, *args, **kwargs):
        if 'token' in request.GET:
            return authenticate(request)
        else:
            return render(request, 'captive_portal/login.html')


class CreateQRPage(TemplateView):

    def get(self, request, *args, **kwargs):
        allocated_bandwidth = AllocatedBandwidth.objects.get(pk=1)
        context = {
            'current_download_speed': allocated_bandwidth.download_speed_in_Kbps / 8,
            'current_upload_speed': allocated_bandwidth.upload_speed_in_Kbps / 8,
        }
        return render(request, 'captive_portal/create_qr.html', context)


def authenticate(request):
    if request.method == 'GET':
        token = request.GET['token']
    else:
        token = request.POST['token']

    # check for token validity
    if WiFiToken.objects.filter(token=token).exists():
        wifi_token = WiFiToken.objects.get(token=token)
        # check for connected counter
        if wifi_token.max_connected == 0 or wifi_token.current_connected < wifi_token.max_connected:
            user_ip = get_client_ip(request)[0]
            # check if IP already authenticated
            if WifiTokenAssociatedIPAddress.objects.filter(ip_address=user_ip).exists() is False:
                wifi_token.current_connected += 1
                wifi_token.save()
                if 'error' in request.session:
                    del request.session['error']
                kl_timezone = timezone(settings.TIME_ZONE)
                delay = datetime.now(kl_timezone)+timedelta(seconds=2)
                add_remote_user.apply_async(args=[user_ip, wifi_token.id], eta=delay)
                return redirect('captive_portal:success')
            else:
                request.session['error'] = 'You are already authenticated!'
                return redirect('captive_portal:login')
        else:
            request.session['error'] = 'Maximum number of connected device reached'
            return redirect('captive_portal:login')
    else:
        request.session['error'] = 'Invalid token'
        return redirect('captive_portal:login')


def generate_otp():
    time_otp = pyotp.TOTP(pyotp.random_base32())
    return time_otp.now()


def create_wifi_user(token, qr_code, max_connected, hour, minute):
    wifi_user_instance = WiFiToken()
    wifi_user_instance.token = token
    kl_timezone = timezone(settings.TIME_ZONE)
    expiration_time = datetime.now(kl_timezone) + timedelta(hours=hour, minutes=minute)
    wifi_user_instance.expiration_time = expiration_time
    qr_image_name = '{}.png'.format(token)
    qr_code.png(qr_image_name, scale=5)
    wifi_user_instance.qr_code = File(open(qr_image_name, 'rb'))
    wifi_user_instance.max_connected = max_connected
    wifi_user_instance.save()
    remove_wifi_qr.apply_async(args=[token], eta=expiration_time)
    os.remove(open(qr_image_name).name)
    return wifi_user_instance


def create_qr(request):
    max_connected = int(request.POST['max_connected'])
    hour = int(request.POST['hour'])
    minute = int(request.POST['minute'])
    request.session['max_connected'] = max_connected
    request.session['hour'] = hour
    request.session['minute'] = minute
    allocated_bandwidth = AllocatedBandwidth.objects.get(pk=1)
    if hour == 0 and minute == 0:
        context = {
            'error': "00 hours 00 minutes is invalid!",
            'current_download_speed': allocated_bandwidth.download_speed_in_Kbps / 8,
            'current_upload_speed': allocated_bandwidth.upload_speed_in_Kbps / 8,
        }
        return render(request, 'captive_portal/create_qr.html', context)
    else:
        while True:
            token = generate_otp()
            if WiFiToken.objects.filter(token=token).exists() is False:
                break
        server_ip = captive_portal.IP_ADDRESS
        qr_code = pyqrcode.create('http://{}:{}/login/authenticate/?token={}'.format(server_ip, captive_portal.PORT, token))
        wifi_user = create_wifi_user(token, qr_code, max_connected, hour, minute)
        context = {
            'qr': wifi_user.qr_code.url,
            'web_url': captive_portal.IP_ADDRESS+":"+str(captive_portal.PORT)+"/login/",
            'token': wifi_user.token,
            'expiration_time': wifi_user.expiration_time,
            'current_download_speed': allocated_bandwidth.download_speed_in_Kbps / 8,
            'current_upload_speed': allocated_bandwidth.upload_speed_in_Kbps / 8,
        }
        return render(request, 'captive_portal/create_qr.html', context)


def set_download_speed(request):
    download_speed_in_Kbps = float(request.POST['download_speed']) * 8
    captive_portal.limit_download_speed(download_speed_in_Kbps)
    allocated_bandwidth = AllocatedBandwidth.objects.get(pk=1)
    allocated_bandwidth.download_speed_in_Kbps = download_speed_in_Kbps
    allocated_bandwidth.save()
    return redirect('captive_portal:create_qr_page')


def set_upload_speed(request):
    upload_speed_in_Kbps = float(request.POST['upload_speed']) * 8
    captive_portal.limit_upload_speed(upload_speed_in_Kbps)
    allocated_bandwidth = AllocatedBandwidth.objects.get(pk=1)
    allocated_bandwidth.upload_speed_in_Kbps = upload_speed_in_Kbps
    allocated_bandwidth.save()
    return redirect('captive_portal:create_qr_page')
