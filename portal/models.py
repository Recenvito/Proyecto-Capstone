import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class VerificacionCorreo(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='verificacion_portal'
    )
    token_hash = models.CharField(max_length=64)
    expira_en = models.DateTimeField()
    consumida_en = models.DateTimeField(null=True, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def generar_token():
        token = secrets.token_urlsafe(32)
        return token, hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def expiracion():
        return timezone.now() + timedelta(hours=24)

    class Meta:
        verbose_name = 'Verificación de correo del portal'
        verbose_name_plural = 'Verificaciones de correo del portal'
