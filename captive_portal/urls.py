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
from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'captive_portal'

urlpatterns = [
    path('', views.LoginPage.as_view(), name='login'),
    path('authenticate/', views.authenticate, name='authenticate'),
    path('success/', TemplateView.as_view(template_name='captive_portal/success.html'), name='success'),
    path('create_qr/', views.CreateQRPage.as_view(), name='create_qr_page'),
    path('create_qr/create/', views.create_qr, name='create_qr'),
]