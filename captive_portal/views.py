from datetime import datetime, timedelta
from ipware import get_client_ip
from django.core.files import File
from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from captive_portal.helper_functions import captive_portal
from pytz import timezone
from django.conf import settings
from .tasks import remove_wifi_qr, add_remote_user
from .models import WiFiQR
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
        return render(request, 'captive_portal/create_qr.html')


def authenticate(request):
    if request.method == 'GET':
        token = request.GET['token']
    else:
        token = request.POST['token']

    is_valid = WiFiQR.objects.filter(token=token).exists()
    if is_valid:
        qr = WiFiQR.objects.get(token=token)
        if qr.max_connected == 0 or qr.current_connected < qr.max_connected:
            qr.current_connected += 1
            user_ip = get_client_ip(request)[0]
            qr.save()
            if 'error' in request.session:
                del request.session['error']
            kl_timezone = timezone(settings.TIME_ZONE)
            delay = datetime.now(kl_timezone)+timedelta(seconds=2)
            add_remote_user.apply_async(args=[user_ip, qr.id], eta=delay)
            return redirect('captive_portal:success')
        else:
            request.session['error'] = 'Maximum number of connected device reached'
            return redirect('captive_portal:login')
    else:
        request.session['error'] = 'Invalid token'
        return redirect('captive_portal:login')


def generate_otp():
    time_otp = pyotp.TOTP(pyotp.random_base32())
    return time_otp.now()


def create_wifi_user(token, qr_code, max_connected):
    wifi_user_instance = WiFiQR()
    wifi_user_instance.token = token
    kl_timezone = timezone(settings.TIME_ZONE)
    expiration_time = datetime.now(kl_timezone) + timedelta(minutes=5)
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
    while True:
        token = generate_otp()
        if WiFiQR.objects.filter(token=token).count() == 0:
            break
    server_ip = captive_portal.IP_ADDRESS
    qr_code = pyqrcode.create('http://{}:{}/login/authenticate/?token={}'.format(server_ip, captive_portal.PORT, token))
    max_connected = request.POST['max_connected']
    wifi_user = create_wifi_user(token, qr_code, max_connected)
    context = {
        'qr': wifi_user.qr_code.url,
        'web_url': captive_portal.IP_ADDRESS+":"+str(captive_portal.PORT)+"/login/",
        'token': wifi_user.token,
        'expiration_time': wifi_user.expiration_time,
    }
    request.session['max_connected'] = max_connected
    return render(request, 'captive_portal/create_qr.html', context)
