from django.urls import path
from .views import *

app_name = 'captive_portal'

urlpatterns = [
    path('', LoginPage.as_view(), name='login'),
    path('authenticate/', authenticate, name='authenticate'),
    path('success/', TemplateView.as_view(template_name='captive_portal/success.html'), name='success'),
    path('create_qr/', CreateQRPage.as_view(), name='create_qr_page'),
    path('create_qr/create/', create_qr, name='create_qr'),
]