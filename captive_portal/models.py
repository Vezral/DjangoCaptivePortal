from django.db import models
from django.conf import settings


class WiFiUser(models.Model):
    token = models.CharField(max_length=100)
    expiration_time = models.DateTimeField()
    qr_code = models.FileField(upload_to=settings.MEDIA_ROOT)

    def __str__(self):
        return '{} {}'.format(self.token, self.expiration_time)
