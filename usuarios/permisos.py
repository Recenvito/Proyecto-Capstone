"""Control de acceso por rol."""
from functools import wraps

from django.core.exceptions import PermissionDenied


def solo_clinico(vista):
    """
    Protege las paginas con contenido clinico.
    La secretaria puede agendar y ver datos de contacto, pero NO la ficha medica.
    """
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        if not request.user.puede_ver_ficha_clinica:
            raise PermissionDenied(
                'Tu rol no tiene acceso a la ficha clinica del paciente.')
        return vista(request, *args, **kwargs)
    return envoltura
