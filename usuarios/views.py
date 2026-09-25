from datetime import timedelta

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from .models import Auditoria, Usuario
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

class LogoutAuditoriaView(auth_views.LogoutView):
  def dispatch(self, request, *args, **kwargs):
    if request.user.is_authenticated:
      from .models import AuditoriaAcceso

      AuditoriaAcceso.objects.create(
        usuario=request.user,
        accion=AuditoriaAcceso.Accion.CIERRE,
        ip=request.META.get('REMOTE_ADDR'),
      )

    return super().dispatch(request, *args, **kwargs)

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

@login_required
def lista_auditoria(request):
    """Muestra los registros de auditoría solo a administradores."""

    if request.user.rol != Usuario.Rol.ADMIN:
        return render(request, '403.html', status=403)

    from .models import AuditoriaAcceso

    usuario = request.GET.get('usuario', '').strip()
    accion = request.GET.get('accion', '').strip()
    modelo = request.GET.get('modelo', '').strip()

    # Registros de acciones del sistema
    acciones = Auditoria.objects.select_related('usuario').all()

    if usuario:
        acciones = acciones.filter(
            usuario__username__icontains=usuario
        )

    if accion:
        acciones = acciones.filter(accion=accion)

    if modelo:
        acciones = acciones.filter(modelo__icontains=modelo)

    registros = []

    for registro in acciones:
        registros.append({
            'fecha_hora': registro.fecha_hora,
            'usuario': registro.usuario.username if registro.usuario else 'Usuario desconocido',
            'accion': registro.get_accion_display(),
            'modelo': registro.modelo,
            'registro_id': registro.registro_id,
            'ip': registro.ip,
            'detalle': registro.detalle,
        })

    # Registros de inicio y cierre de sesión
    accesos = AuditoriaAcceso.objects.select_related('usuario').all()

    if usuario:
        accesos = accesos.filter(
            usuario__username__icontains=usuario
        )

    if accion:
        accesos = accesos.filter(accion=accion)

    if modelo:
        accesos = accesos.none()

    for acceso in accesos:
        registros.append({
            'fecha_hora': acceso.fecha_hora,
            'usuario': acceso.usuario.username if acceso.usuario else 'Usuario desconocido',
            'accion': acceso.get_accion_display(),
            'modelo': 'Autenticación',
            'registro_id': '—',
            'ip': acceso.ip,
            'detalle': {},
        })

    registros.sort(
        key=lambda registro: registro['fecha_hora'],
        reverse=True,
    )

    acciones_disponibles = list(Auditoria.Accion.choices) + list(
        AuditoriaAcceso.Accion.choices
    )

    contexto = {
        'registros': registros,
        'acciones': acciones_disponibles,
        'usuario_filtro': usuario,
        'accion_filtro': accion,
        'modelo_filtro': modelo,
    }

    return render(
        request,
        'usuarios/auditoria.html',
        contexto,
    )