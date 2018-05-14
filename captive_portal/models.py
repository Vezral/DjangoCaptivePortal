from django.db import models
import os


# Determine the upload_directory for uploaded question file (including answer) in MEDIA_ROOT
def upload_directory(instance, filename):
    path = os.path.join(str(instance.expiration_time.date()).replace('-', '_'), filename)
    return path


class WiFiToken(models.Model):
    token = models.CharField(max_length=100, unique=True)
    expiration_time = models.DateTimeField()
    qr_code = models.FileField(upload_to=upload_directory)
    current_connected = models.IntegerField(default=0)
    max_connected = models.IntegerField(default=0)

    def __str__(self):
        return '{} {}'.format(self.token, self.expiration_time)


class WifiTokenAssociatedIPAddress(models.Model):
    token = models.ForeignKey(WiFiToken, on_delete=models.CASCADE)
    ip_address = models.CharField(max_length=100, unique=True)


class RemoveWiFiTokenScheduler(models.Model):
    scheduled_time = models.DateTimeField()
