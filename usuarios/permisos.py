"""Control de acceso por rol y asignacion profesional."""

from functools import wraps
from django.core.exceptions import PermissionDenied
from .models import Usuario


def puede_acceder_ficha(usuario, paciente):
  """Determina si el usuario puede acceder a la ficha clinica."""
  if not usuario.is_authenticated:
    return False
  if usuario.rol == Usuario.Rol.ADMIN:
    return True
  if not usuario.es_medico:
    return False
  return paciente.asignaciones_profesionales.filter(
    profesional=usuario,
    activa=True,
  ).exists()

def puede_gestionar_paciente(usuario):
  """Determina si el usuario puede crear o modificar datos administrativos."""
  if not usuario.is_authenticated:
    return False

  return usuario.rol in (
    Usuario.Rol.ADMIN,
    Usuario.Rol.SECRETARIA,
  )


def solo_clinico(vista):
  """Protege vistas con contenido clinico y exige asignacion al paciente."""
  @wraps(vista)
  def envoltura(request, *args, **kwargs):
    if not request.user.is_authenticated:
      raise PermissionDenied

    paciente = None
    if 'pk' in kwargs:
      from pacientes.models import Paciente
      paciente = Paciente.objects.filter(pk=kwargs['pk']).first()
    if paciente is not None and not puede_acceder_ficha(request.user, paciente):
      raise PermissionDenied(
        'No tienes acceso a la ficha clinica de este paciente.'
      )
    if paciente is None and not request.user.puede_ver_ficha_clinica:
      raise PermissionDenied(
        'Tu rol no tiene acceso a la ficha clinica.'
      )
    return vista(request, *args, **kwargs)

  return envoltura