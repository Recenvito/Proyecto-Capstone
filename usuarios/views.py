from datetime import timedelta

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from agenda.models import Cita
from pacientes.models import Paciente


class LoginAuditoriaView(auth_views.LoginView):
  """Login de Django con registro de auditoria."""

  template_name = 'registration/login.html'

  def form_valid(self, form):
    from .models import AuditoriaAcceso

    usuario = form.get_user()

    AuditoriaAcceso.objects.create(
      usuario=usuario,
      accion=AuditoriaAcceso.Accion.INICIO,
      ip=self.request.META.get('REMOTE_ADDR'),
    )

    return super().form_valid(form)


@login_required
def inicio(request):
  """Pantalla principal: resumen del dia."""
  ahora = timezone.now()
  hoy = timezone.localdate()

  citas_hoy = (
    Cita.objects
    .filter(fecha_hora__date=hoy)
    .exclude(estado=Cita.Estado.CANCELADA)
    .select_related('paciente', 'profesional')
    .order_by('fecha_hora')
  )

  proximas = (
    Cita.objects
    .filter(fecha_hora__gt=ahora, fecha_hora__lte=ahora + timedelta(days=7))
    .exclude(fecha_hora__date=hoy)
    .exclude(estado=Cita.Estado.CANCELADA)
    .select_related('paciente')
    .order_by('fecha_hora')[:8]
  )

  contexto = {
    'citas_hoy': citas_hoy,
    'proximas': proximas,
    'total_pacientes': Paciente.objects.filter(activo=True).count(),
    'atendidas_hoy': citas_hoy.filter(
      estado=Cita.Estado.ATENDIDA
    ).count(),
    'hoy': hoy,
    'rol': request.user.get_rol_display(),
  }

  return render(request, 'inicio.html', contexto)