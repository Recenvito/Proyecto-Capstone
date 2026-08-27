from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
    medicos = Usuario.objects.filter(rol=Usuario.Rol.MEDICO, is_active=True)

    profesional_id = request.GET.get('profesional')
    if profesional_id:
        profesional = medicos.filter(pk=profesional_id).first()
    elif request.user.es_medico:
        profesional = request.user
    else:
        profesional = medicos.first()

    bloques = []
    if profesional:
        citas = {
            c.fecha_hora: c
            for c in Cita.objects.filter(
                profesional=profesional, fecha_hora__date=dia
            ).exclude(estado=Cita.Estado.CANCELADA).select_related('paciente')
        }

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

    return render(request, 'agenda/calendario.html', {
        'dia': dia,
        'dia_anterior': dia - timedelta(days=1),
        'dia_siguiente': dia + timedelta(days=1),
        'hoy': timezone.localdate(),
        'bloques': bloques,
        'medicos': medicos,
        'profesional': profesional,
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
    if request.GET.get('paciente'):
        inicial['paciente'] = request.GET['paciente']

    if request.method == 'POST':
        form = CitaForm(request.POST)
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
        form = CitaForm(initial=inicial)

    return render(request, 'agenda/agendar.html', {'form': form})


@login_required
def cambiar_estado(request, pk):
    """Marcar una cita como confirmada, atendida, no asistio o cancelada."""
    cita = get_object_or_404(Cita, pk=pk)
    nuevo = request.POST.get('estado')

    if nuevo in Cita.Estado.values:
        cita.estado = nuevo
        cita.save()
        messages.success(request, f'Cita marcada como "{cita.get_estado_display()}".')
    else:
        messages.error(request, 'Estado no valido.')

    return redirect(f'/agenda/?fecha={cita.fecha_hora.date():%Y-%m-%d}')
