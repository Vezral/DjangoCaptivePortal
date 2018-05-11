from datetime import datetime, timedelta
from ipware import get_client_ip
from django.core.files import File
from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from captive_portal.helper_functions import captive_portal
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
        user = WiFiQR.objects.get(token=token)
        if user.max_connected == 0 or user.current_connected < user.max_connected:
            user.current_connected += 1
            user_ip = get_client_ip(request)
            captive_portal.add_remote_user(user_ip[0], user.expiration_time)
            user.save()
            if 'error' in request.session:
                del request.session['error']
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
    wifi_user_instance.expiration_time = datetime.now() + timedelta(minutes=5)
    qr_image_name = '{}.png'.format(token)
    qr_code.png(qr_image_name, scale=5)
    wifi_user_instance.qr_code = File(open(qr_image_name, 'rb'))
    wifi_user_instance.max_connected = max_connected
    wifi_user_instance.save()
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
        'token': wifi_user.token,
        'expiration_time': wifi_user.expiration_time,
    }
    request.session['max_connected'] = max_connected
    return render(request, 'captive_portal/create_qr.html', context)
