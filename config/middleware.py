from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from usuarios.models import Usuario


class AccesoDenegadoMiddleware:
  """Muestra una pantalla amigable para errores de autorizacion."""

  def __init__(self, get_response):
    self.get_response = get_response

  def __call__(self, request):
    return self.get_response(request)

  def process_exception(self, request, exception):
    if isinstance(exception, PermissionDenied):
      return render(
        request,
        '403.html',
        {'exception': exception},
        status=403,
      )

    return None


class AccesoPortalTutorMiddleware:
  """Aísla cuentas familiares de las vistas internas del equipo clínico."""

  RUTAS_PUBLICAS = (
    '/portal/', '/login/', '/logout/', '/password-change/', '/password-reset/',
    '/reset/', '/perfil/', '/static/',
  )

  def __init__(self, get_response):
    self.get_response = get_response

  def __call__(self, request):
    usuario = getattr(request, 'user', None)
    ruta_permitida = request.path_info == '/' or any(
      request.path_info.startswith(ruta) for ruta in self.RUTAS_PUBLICAS
    )
    if usuario and usuario.is_authenticated and usuario.rol == Usuario.Rol.TUTOR and not ruta_permitida:
      return render(request, '403.html', status=403)
    return self.get_response(request)
