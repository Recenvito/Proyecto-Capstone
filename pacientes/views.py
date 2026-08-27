from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from usuarios.permisos import solo_clinico

from .forms import AntecedentesForm, AtencionForm, PacienteForm, TutorFormSet
from .models import AntecedentesNeurologicos, Atencion, Paciente


@login_required
def lista(request):
    """Listado de pacientes con buscador por nombre o RUT."""
    busqueda = request.GET.get('q', '').strip()
    pacientes = Paciente.objects.filter(activo=True)

    if busqueda:
        pacientes = pacientes.filter(
            Q(rut__icontains=busqueda)
            | Q(nombres__icontains=busqueda)
            | Q(apellido_paterno__icontains=busqueda)
            | Q(apellido_materno__icontains=busqueda)
        )

    return render(request, 'pacientes/lista.html', {
        'pacientes': pacientes[:100],
        'busqueda': busqueda,
        'total': pacientes.count(),
    })


@login_required
def detalle(request, pk):
    """Ficha del paciente. El contenido clinico se oculta segun el rol."""
    paciente = get_object_or_404(Paciente, pk=pk)
    return render(request, 'pacientes/detalle.html', {
        'paciente': paciente,
        'tutores': paciente.tutores.all(),
        'diagnosticos': paciente.diagnosticos.all(),
        'atenciones': paciente.atenciones.select_related('profesional')[:20],
        'citas': paciente.citas.order_by('-fecha_hora')[:10],
        'antecedentes': getattr(paciente, 'antecedentes', None),
    })


@login_required
def crear(request):
    """Alta de un paciente nuevo, junto con sus tutores."""
    if request.method == 'POST':
        form = PacienteForm(request.POST)
        formset = TutorFormSet(request.POST)
        if form.is_valid():
            paciente = form.save()
            formset = TutorFormSet(request.POST, instance=paciente)
            if formset.is_valid():
                formset.save()
            AntecedentesNeurologicos.objects.get_or_create(paciente=paciente)
            messages.success(request, f'Paciente {paciente.nombre_completo} creado.')
            return redirect('pacientes:detalle', pk=paciente.pk)
    else:
        form = PacienteForm()
        formset = TutorFormSet()

    return render(request, 'pacientes/formulario.html', {
        'form': form, 'formset': formset, 'titulo': 'Nuevo paciente',
    })


@login_required
def editar(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == 'POST':
        form = PacienteForm(request.POST, instance=paciente)
        formset = TutorFormSet(request.POST, instance=paciente)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Datos actualizados.')
            return redirect('pacientes:detalle', pk=paciente.pk)
    else:
        form = PacienteForm(instance=paciente)
        formset = TutorFormSet(instance=paciente)

    return render(request, 'pacientes/formulario.html', {
        'form': form, 'formset': formset, 'paciente': paciente,
        'titulo': f'Editar a {paciente.nombre_completo}',
    })


@login_required
@solo_clinico
def editar_antecedentes(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    antecedentes, _ = AntecedentesNeurologicos.objects.get_or_create(paciente=paciente)

    if request.method == 'POST':
        form = AntecedentesForm(request.POST, instance=antecedentes)
        if form.is_valid():
            form.save()
            messages.success(request, 'Antecedentes guardados.')
            return redirect('pacientes:detalle', pk=paciente.pk)
    else:
        form = AntecedentesForm(instance=antecedentes)

    return render(request, 'pacientes/antecedentes.html', {
        'form': form, 'paciente': paciente,
    })


@login_required
@solo_clinico
def crear_atencion(request, pk):
    """Registrar una consulta atendida en la ficha."""
    paciente = get_object_or_404(Paciente, pk=pk)

    if request.method == 'POST':
        form = AtencionForm(request.POST)
        if form.is_valid():
            atencion = form.save(commit=False)
            atencion.paciente = paciente
            atencion.profesional = request.user
            atencion.save()
            messages.success(request, 'Atencion registrada en la ficha.')
            return redirect('pacientes:detalle', pk=paciente.pk)
    else:
        form = AtencionForm(initial={'fecha': timezone.now()})

    return render(request, 'pacientes/atencion_form.html', {
        'form': form, 'paciente': paciente,
    })


@login_required
@solo_clinico
def detalle_atencion(request, pk):
    atencion = get_object_or_404(
        Atencion.objects.select_related('paciente', 'profesional'), pk=pk)
    return render(request, 'pacientes/atencion_detalle.html', {'atencion': atencion})
