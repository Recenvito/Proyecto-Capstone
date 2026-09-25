from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse
from usuarios.permisos import (
  puede_acceder_ficha,
  puede_gestionar_paciente,
  solo_clinico,
)
from .forms import AntecedentesForm, AtencionForm, PacienteForm, TutorFormSet
from .models import AntecedentesNeurologicos, Atencion, Paciente
from usuarios.models import Auditoria


@login_required
def lista(request):
  """Listado de pacientes segun el acceso del usuario."""
  busqueda = request.GET.get('q', '').strip()

  pacientes = Paciente.objects.filter(activo=True)

  if request.user.es_medico:
    pacientes = pacientes.filter(
      asignaciones_profesionales__profesional=request.user,
      asignaciones_profesionales__activa=True,
    )

  pacientes = pacientes.order_by('nombres').distinct()

  if busqueda:
    pacientes = pacientes.filter(
      Q(rut__icontains=busqueda)
      | Q(nombres__icontains=busqueda)
      | Q(apellido_paterno__icontains=busqueda)
      | Q(apellido_materno__icontains=busqueda)
    )

  paginator = Paginator(pacientes, 15)
  pagina = request.GET.get('page')
  pacientes_pagina = paginator.get_page(pagina)

  return render(request, 'pacientes/lista.html', {
    'pacientes': pacientes_pagina,
    'busqueda': busqueda,
    'total': pacientes.count(),
  })

@login_required
def detalle(request, pk):
  """Ficha del paciente segun el acceso del usuario."""
  paciente = get_object_or_404(Paciente, pk=pk)

  if request.user.es_medico and not puede_acceder_ficha(
    request.user, paciente
  ):
    raise PermissionDenied(
      'No tienes acceso a este paciente porque no esta asignado a tu equipo tratante.'
    )

  acceso_clinico = puede_acceder_ficha(request.user, paciente)
  if acceso_clinico:
    Auditoria.objects.create(
      usuario=request.user,
      accion=Auditoria.Accion.CONSULTAR,
      modelo='Ficha clínica',
      registro_id=paciente.pk,
      ip=request.META.get('REMOTE_ADDR'),
      detalle={
        'evento': 'Acceso a ficha clínica',
      },
    )  

  contexto = {
    'paciente': paciente,
    'tutores': paciente.tutores.all(),
    'citas': paciente.citas.order_by('-fecha_hora')[:10],
    'acceso_clinico': acceso_clinico,
    'diagnosticos': [],
    'atenciones': [],
    'antecedentes': None,
  }

  if acceso_clinico:
    contexto.update({
      'diagnosticos': paciente.diagnosticos.all(),
      'atenciones': paciente.atenciones.select_related('profesional')[:20],
      'antecedentes': getattr(paciente, 'antecedentes', None),
    })

  return render(request, 'pacientes/detalle.html', contexto)

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

      AntecedentesNeurologicos.objects.get_or_create(
        paciente=paciente
      )

      Auditoria.objects.create(
        usuario=request.user,
        accion=Auditoria.Accion.CREAR,
        modelo='Paciente',
        registro_id=paciente.pk,
        ip=request.META.get('REMOTE_ADDR'),
        detalle={
          'rut': paciente.rut,
          'nombres': paciente.nombres,
          'apellido_paterno': paciente.apellido_paterno,
          'apellido_materno': paciente.apellido_materno,
          'fecha_nacimiento': paciente.fecha_nacimiento.isoformat(),
          'sexo': paciente.sexo,
          'prevision': paciente.prevision,
          'direccion': paciente.direccion,
          'comuna': paciente.comuna,
          'colegio': paciente.colegio,
          'curso': paciente.curso,
          'derivado_por': paciente.derivado_por,
        },
      )

      messages.success(
        request,
        f'Paciente {paciente.nombre_completo} creado.'
      )
      return redirect('pacientes:detalle', pk=paciente.pk)

  else:
    form = PacienteForm()
    formset = TutorFormSet()

  return render(request, 'pacientes/formulario.html', {
    'form': form,
    'formset': formset,
    'titulo': 'Nuevo paciente',
  })


@login_required
def editar(request, pk):
  if not puede_gestionar_paciente(request.user):
    raise PermissionDenied(
      'No tienes permiso para modificar los datos administrativos del paciente.'
    )

  paciente = get_object_or_404(Paciente, pk=pk)

  if request.method == 'POST':
    form = PacienteForm(request.POST, instance=paciente)
    formset = TutorFormSet(request.POST, instance=paciente)

    if form.is_valid() and formset.is_valid():
      paciente = form.save()

      tutores_eliminados = [
        form_tutor.instance.pk
        for form_tutor in formset.forms
        if form_tutor.cleaned_data.get('DELETE')
        and form_tutor.instance.pk
      ]

      formset.save()

      for tutor in formset.new_objects:
        Auditoria.objects.create(
          usuario=request.user,
          accion=Auditoria.Accion.CREAR,
          modelo='Tutor',
          registro_id=tutor.pk,
          ip=request.META.get('REMOTE_ADDR'),
          detalle={'paciente_id': paciente.pk},
        )

      for tutor, campos_modificados in formset.changed_objects:
        Auditoria.objects.create(
          usuario=request.user,
          accion=Auditoria.Accion.MODIFICAR,
          modelo='Tutor',
          registro_id=tutor.pk,
          ip=request.META.get('REMOTE_ADDR'),
          detalle={
            'paciente_id': paciente.pk,
            'campos_modificados': campos_modificados,
          },
        )

      for tutor_id in tutores_eliminados:
        Auditoria.objects.create(
          usuario=request.user,
          accion=Auditoria.Accion.ELIMINAR,
          modelo='Tutor',
          registro_id=tutor_id,
          ip=request.META.get('REMOTE_ADDR'),
          detalle={'paciente_id': paciente.pk},
        )

      Auditoria.objects.create(
        usuario=request.user,
        accion=Auditoria.Accion.MODIFICAR,
        modelo='Paciente',
        registro_id=paciente.pk,
        ip=request.META.get('REMOTE_ADDR'),
        detalle={
          'rut': paciente.rut,
          'nombres': paciente.nombres,
          'apellido_paterno': paciente.apellido_paterno,
          'apellido_materno': paciente.apellido_materno,
          'fecha_nacimiento': paciente.fecha_nacimiento.isoformat(),
          'sexo': paciente.sexo,
          'prevision': paciente.prevision,
          'direccion': paciente.direccion,
          'comuna': paciente.comuna,
          'colegio': paciente.colegio,
          'curso': paciente.curso,
          'derivado_por': paciente.derivado_por,
        },
      )

      messages.success(request, 'Datos actualizados.')
      return redirect('pacientes:detalle', pk=paciente.pk)

  else:
    form = PacienteForm(instance=paciente)
    formset = TutorFormSet(instance=paciente)

  return render(request, 'pacientes/formulario.html', {
    'form': form,
    'formset': formset,
    'paciente': paciente,
    'titulo': f'Editar a {paciente.nombre_completo}',
  })

@login_required
@solo_clinico
def editar_antecedentes(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    antecedentes, _ = AntecedentesNeurologicos.objects.get_or_create(
        paciente=paciente
    )
    if request.method == 'POST':
        form = AntecedentesForm(
            request.POST,
            instance=antecedentes
        )
        if form.is_valid():
            form.save()
            Auditoria.objects.create(
                usuario=request.user,
                accion=Auditoria.Accion.MODIFICAR,
                modelo='AntecedentesNeurologicos',
                registro_id=antecedentes.pk,
                ip=request.META.get('REMOTE_ADDR'),
                detalle={
                    'evento': 'Modificacion de antecedentes clinicos',
                    'paciente_id': paciente.pk,
                },
            )
            messages.success(
                request,
                'Antecedentes guardados.'
            )
            return redirect(
                'pacientes:detalle',
                pk=paciente.pk
            )
    else:
        form = AntecedentesForm(instance=antecedentes)
    return render(
        request,
        'pacientes/antecedentes.html',
        {
            'form': form,
            'paciente': paciente,
        }
    )


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

            Auditoria.objects.create(
                usuario=request.user,
                accion=Auditoria.Accion.CREAR,
                modelo='Atencion',
                registro_id=atencion.pk,
                ip=request.META.get('REMOTE_ADDR'),
                detalle={
                    'paciente_id': paciente.pk,
                    'fecha': atencion.fecha.isoformat(),
                    'evento': 'Registro de atencion clinica',
                },
            )

            messages.success(
                request,
                'Atencion registrada en la ficha.'
            )

            return redirect('pacientes:detalle', pk=paciente.pk)

    else:
        form = AtencionForm(initial={'fecha': timezone.now()})

    return render(request, 'pacientes/atencion_form.html', {
        'form': form,
        'paciente': paciente,
    })

@login_required
def buscar(request):
  """Busqueda de pacientes segun el acceso del usuario."""
  busqueda = request.GET.get('q', '').strip()

  pacientes = Paciente.objects.filter(
    activo=True
  )

  if request.user.es_medico:
    pacientes = pacientes.filter(
      asignaciones_profesionales__profesional=request.user,
      asignaciones_profesionales__activa=True,
    )

  pacientes = pacientes.order_by('nombres').distinct()

  if busqueda:
    pacientes = pacientes.filter(
      Q(rut__icontains=busqueda)
      | Q(nombres__icontains=busqueda)
      | Q(apellido_paterno__icontains=busqueda)
      | Q(apellido_materno__icontains=busqueda)
    )

  pacientes = pacientes[:15]

  resultados = []

  for paciente in pacientes:
    resultados.append({
      'id': paciente.pk,
      'nombre': paciente.nombre_completo,
      'rut': paciente.rut,
      'edad': paciente.edad_texto,
      'prevision': paciente.get_prevision_display(),
    })

  return JsonResponse({
    'pacientes': resultados,
  })


@login_required
def detalle_atencion(request, pk):
  """Detalle de una atencion con acceso segun paciente asignado."""
  atencion = get_object_or_404(
    Atencion.objects.select_related('paciente', 'profesional'),
    pk=pk,
  )

  if not puede_acceder_ficha(request.user, atencion.paciente):
    raise PermissionDenied(
      'No tienes acceso a la ficha clinica de este paciente.'
    )

  return render(request, 'pacientes/atencion_detalle.html', {
    'atencion': atencion,
  })