from django.conf import settings


def soporte_contacto(request):
    return {
        'soporte_email': settings.SOPORTE_EMAIL,
        'soporte_telefono': settings.SOPORTE_TELEFONO,
    }
