from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from agenda.models import Cita
from pacientes.models import Paciente


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
        'atendidas_hoy': citas_hoy.filter(estado=Cita.Estado.ATENDIDA).count(),
        'hoy': hoy,
    }
    return render(request, 'inicio.html', contexto)
