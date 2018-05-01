from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from datetime import datetime, timedelta
from django.core.files import File
from .models import WiFiUser
import pyqrcode
import pyotp
import socket
import os


class LoginPage(TemplateView):

    def get(self, request, *args, **kwargs):
        return render(request, 'captive_portal/login.html')


class CreateQRPage(TemplateView):

    def get(self, request, *args, **kwargs):
        return render(request, 'captive_portal/create_qr.html')


def authenticate(request):
    if request.method == 'GET':
        token = request.GET['token']
    else:
        token = request.POST['token']

    if WiFiUser.objects.get(token=token):
        return redirect('captive_portal:success')
    else:
        return redirect('captive_portal:login')


def generate_otp():
    time_otp = pyotp.TOTP(pyotp.random_base32())
    return time_otp.now()


def create_wifi_user(token, qr_code):
    wifi_user_instance = WiFiUser()
    wifi_user_instance.token = token
    wifi_user_instance.expiration_time = datetime.now() + timedelta(hours=2)
    qr_image_name = '{}.png'.format(token)
    qr_code.png(qr_image_name, scale=5)
    wifi_user_instance.qr_code = File(open(qr_image_name, 'rb'))
    wifi_user_instance.save()
    os.remove(open(qr_image_name).name)


def create_qr(request):
    token = generate_otp()
    server_ip = '192.168.207.1'
    qr_code = pyqrcode.create('http://{}/login/authenticate?token={}'.format(server_ip, token))
    create_wifi_user(token, qr_code)
    request.session['token'] = 'http://{}/media/{}.png'.format(server_ip, token)
    return redirect('captive_portal:create_qr_page')
