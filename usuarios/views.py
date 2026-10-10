from datetime import datetime, timedelta

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from urllib.parse import urlencode
from .models import Auditoria, Usuario
from agenda.models import Cita
from pacientes.models import AsignacionProfesional, Paciente
from .forms import PerfilUsuarioForm, UsuarioEdicionAdminForm


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
  inicio_hoy = timezone.make_aware(
    datetime.combine(hoy, datetime.min.time()), timezone.get_current_timezone()
  )
  inicio_manana = inicio_hoy + timedelta(days=1)

  citas_hoy = (
    Cita.objects
    .filter(fecha_hora__gte=inicio_hoy, fecha_hora__lt=inicio_manana)
    .exclude(estado=Cita.Estado.CANCELADA)
    .select_related('paciente', 'profesional')
    .order_by('fecha_hora')
  )
  if request.user.es_medico:
    citas_hoy = citas_hoy.filter(profesional=request.user)

  proximas = (
    Cita.objects
    .filter(fecha_hora__gt=ahora, fecha_hora__lte=ahora + timedelta(days=7))
    .exclude(fecha_hora__date=hoy)
    .exclude(estado=Cita.Estado.CANCELADA)
    .select_related('paciente')
    .order_by('fecha_hora')
  )
  if request.user.es_medico:
    proximas = proximas.filter(profesional=request.user)

  pacientes_activos = Paciente.objects.filter(activo=True)
  if request.user.es_medico:
    pacientes_activos = pacientes_activos.filter(
      asignaciones_profesionales__profesional=request.user,
      asignaciones_profesionales__activa=True,
    ).distinct()

  contexto = {
    'citas_hoy': citas_hoy,
    'proximas': proximas,
    'total_pacientes': pacientes_activos.count(),
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


@login_required
def editar_perfil(request):
    if request.method == 'POST':
        form = PerfilUsuarioForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tu perfil fue actualizado.')
            return redirect('editar_perfil')
    else:
        form = PerfilUsuarioForm(instance=request.user)
    return render(request, 'usuarios/perfil_formulario.html', {
        'form': form,
        'usuario': request.user,
        'es_edicion_admin': False,
    })


@login_required
def editar_usuario(request, pk):
    if request.user.rol != Usuario.Rol.ADMIN:
        return render(request, '403.html', status=403)

    usuario = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        form = UsuarioEdicionAdminForm(request.POST, instance=usuario)
        if form.is_valid():
            with transaction.atomic():
                usuario = form.save()
                if usuario.rol != Usuario.Rol.MEDICO:
                    fecha_termino = timezone.now()
                    AsignacionProfesional.objects.filter(
                        profesional=usuario,
                        activa=True,
                    ).update(activa=False, fecha_termino=fecha_termino)
            messages.success(request, 'Los datos del usuario fueron actualizados.')
            url = reverse('pacientes:historial_asignaciones')
            filtros = urlencode({
                'vista': 'medicos',
                'q': request.GET.get('q', ''),
                'page': request.GET.get('page', '1'),
            })
            return redirect(f'{url}?{filtros}')
    else:
        form = UsuarioEdicionAdminForm(instance=usuario)
    return render(request, 'usuarios/perfil_formulario.html', {
        'form': form,
        'usuario': usuario,
        'es_edicion_admin': True,
    })
