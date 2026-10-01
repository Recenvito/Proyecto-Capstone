from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from usuarios.models import Usuario

from .forms import CitaForm
from .models import Cita, Disponibilidad


def _fecha_desde_get(request):
    """Lee ?fecha=AAAA-MM-DD de la URL; si no viene, usa hoy."""
    texto = request.GET.get('fecha')
    if texto:
        try:
            return datetime.strptime(texto, '%Y-%m-%d').date()
        except ValueError:
            pass
    return timezone.localdate()


@login_required
def calendario(request):
    """
    Agenda del dia: muestra todos los bloques del horario del profesional
    y cuales estan ocupados.
    """
    dia = _fecha_desde_get(request)
    inicio_dia = timezone.make_aware(
        datetime.combine(dia, datetime.min.time()), timezone.get_current_timezone()
    )
    inicio_dia_siguiente = inicio_dia + timedelta(days=1)
    medicos = Usuario.objects.filter(rol=Usuario.Rol.MEDICO, is_active=True)
    busqueda = request.GET.get('q', '').strip()

    profesional_id = request.GET.get('profesional')
    if request.user.es_medico:
        profesional = request.user if request.user.is_active else None
    elif profesional_id:
        profesional = medicos.filter(pk=profesional_id).first()
    else:
        profesional = medicos.first()

    bloques = []
    proximas = Cita.objects.none()
    resultados_busqueda = Cita.objects.none()
    if profesional:
        citas_profesional = Cita.objects.filter(profesional=profesional).select_related(
            'paciente', 'profesional'
        )
        citas_dia = Cita.objects.filter(
                profesional=profesional,
                fecha_hora__gte=inicio_dia,
                fecha_hora__lt=inicio_dia_siguiente,
            ).select_related('paciente', 'profesional').order_by('fecha_hora')
        proximas = Cita.objects.filter(
            profesional=profesional,
            fecha_hora__gt=timezone.now(),
            fecha_hora__lte=timezone.now() + timedelta(days=30),
        ).exclude(estado=Cita.Estado.CANCELADA).select_related(
            'paciente', 'profesional'
        ).order_by('fecha_hora')

        if busqueda:
            filtro = (
                Q(paciente__nombres__icontains=busqueda)
                | Q(paciente__apellido_paterno__icontains=busqueda)
                | Q(paciente__apellido_materno__icontains=busqueda)
                | Q(paciente__rut__icontains=busqueda)
                | Q(motivo__icontains=busqueda)
            )
            citas_dia = citas_dia.filter(filtro)
            proximas = proximas.filter(filtro)
            resultados_busqueda = citas_profesional.filter(filtro).order_by('-fecha_hora')

        citas = {}
        for cita in citas_dia.exclude(estado=Cita.Estado.CANCELADA):
            hora_local = timezone.localtime(cita.fecha_hora).replace(second=0, microsecond=0)
            citas[hora_local] = cita

        for disp in Disponibilidad.objects.filter(profesional=profesional, activo=True):
            for cupo in disp.generar_cupos(dia):
                bloques.append({
                    'hora': cupo,
                    'cita': citas.get(cupo),
                    'lugar': disp.lugar,
                })
        bloques.sort(key=lambda b: b['hora'])

        # Citas que quedaron fuera del horario regular (agendadas a mano)
        horas_en_bloques = {b['hora'] for b in bloques}
        for hora, cita in sorted(citas.items()):
            if hora not in horas_en_bloques:
                bloques.append({'hora': hora, 'cita': cita, 'lugar': ''})
        bloques.sort(key=lambda b: b['hora'])
        if busqueda:
            bloques = [bloque for bloque in bloques if bloque['cita']]

    return render(request, 'agenda/calendario.html', {
        'dia': dia,
        'dia_anterior': dia - timedelta(days=1),
        'dia_siguiente': dia + timedelta(days=1),
        'hoy': timezone.localdate(),
        'bloques': bloques,
        'medicos': medicos,
        'profesional': profesional,
        'busqueda': busqueda,
        'proximas': proximas,
        'resultados_busqueda': resultados_busqueda,
        'ocupados': sum(1 for b in bloques if b['cita']),
        'libres': sum(1 for b in bloques if not b['cita']),
    })


@login_required
def agendar(request):
    """Tomar una hora. Puede venir precargada desde el calendario."""
    inicial = {}
    if request.GET.get('hora'):
        try:
            inicial['fecha_hora'] = datetime.fromisoformat(request.GET['hora'])
        except ValueError:
            pass
    if request.GET.get('profesional'):
        inicial['profesional'] = request.GET['profesional']
    if request.user.es_medico:
        inicial['profesional'] = request.user.pk
    if request.GET.get('paciente'):
        inicial['paciente'] = request.GET['paciente']

    if request.method == 'POST':
        form = CitaForm(request.POST, user=request.user)
        if form.is_valid():
            cita = form.save(commit=False)
            cita.creada_por = request.user
            cita.save()
            messages.success(
                request,
                f'Hora agendada para {cita.paciente.nombre_completo} '
                f'el {cita.fecha_hora:%d/%m/%Y a las %H:%M}.')
            return redirect(f'/agenda/?fecha={cita.fecha_hora.date():%Y-%m-%d}')
    else:
        form = CitaForm(initial=inicial, user=request.user)

    return render(request, 'agenda/agendar.html', {'form': form})


@login_required
@require_POST
def cambiar_estado(request, pk):
    """Marcar una cita como confirmada, atendida, no asistio o cancelada."""
    cita = get_object_or_404(Cita, pk=pk)
    if request.user.es_medico and cita.profesional_id != request.user.pk:
        return render(request, '403.html', status=403)
    if request.user.rol not in (Usuario.Rol.ADMIN, Usuario.Rol.SECRETARIA, Usuario.Rol.MEDICO):
        return render(request, '403.html', status=403)
    nuevo = request.POST.get('estado')

    if nuevo in Cita.Estado.values:
        cita.estado = nuevo
        cita.save()
        messages.success(request, f'Cita marcada como "{cita.get_estado_display()}".')
    else:
        messages.error(request, 'Estado no valido.')

    return redirect(f'/agenda/?fecha={cita.fecha_hora.date():%Y-%m-%d}')
