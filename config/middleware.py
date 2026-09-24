from django.core.exceptions import PermissionDenied
from django.shortcuts import render


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