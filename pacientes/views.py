from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.urls import reverse
from urllib.parse import urlencode
from usuarios.permisos import (
  puede_acceder_ficha,
  puede_gestionar_paciente,
  solo_clinico,
)
from .forms import AntecedentesForm, AtencionForm, DiagnosticoForm, PacienteForm, TutorFormSet
from .models import AntecedentesNeurologicos, AsignacionProfesional, Atencion, Diagnostico, Paciente
from usuarios.models import Auditoria, Usuario


@login_required
def lista(request):
  """Listado de pacientes segun el acceso del usuario."""
  busqueda = request.GET.get('q', '').strip()

  pacientes = Paciente.objects.all()
  if request.user.rol != 'ADMIN':
    pacientes = pacientes.filter(activo=True)

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
    'es_admin': request.user.rol == 'ADMIN',
  })


@login_required
def cambiar_estado_paciente(request, pk):
  if request.user.rol != 'ADMIN':
    return render(request, '403.html', status=403)
  if request.method != 'POST':
    return redirect('pacientes:lista')

  with transaction.atomic():
    paciente = get_object_or_404(Paciente.objects.select_for_update(), pk=pk)
    paciente.activo = not paciente.activo
    paciente.save(update_fields=['activo', 'actualizado_en'])

    if not paciente.activo:
      fecha_termino = timezone.now()
      AsignacionProfesional.objects.filter(
        paciente=paciente,
        activa=True,
      ).update(activa=False, fecha_termino=fecha_termino)

  if paciente.activo:
    messages.success(request, 'Paciente activado. Debe asignarse nuevamente a los profesionales.')
  else:
    messages.success(request, 'Paciente desactivado y asignaciones activas finalizadas.')
  url = reverse('pacientes:lista')
  filtros = urlencode({
    'q': request.POST.get('q', ''),
    'page': request.POST.get('page', '1'),
  })
  return redirect(f'{url}?{filtros}')

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
    'asignaciones_profesionales': paciente.asignaciones_profesionales.filter(
      activa=True
    ).select_related('profesional').order_by('profesional__first_name', 'profesional__last_name'),
  }

  if acceso_clinico:
    contexto.update({
      'diagnosticos': paciente.diagnosticos.select_related('registrado_por').all(),
      'atenciones': paciente.atenciones.select_related('profesional').order_by('-fecha')[:50],
      'antecedentes': getattr(paciente, 'antecedentes', None),
    })

  return render(request, 'pacientes/detalle.html', contexto)

@login_required
def crear(request):
  """Alta de un paciente nuevo, junto con sus tutores."""
  if not puede_gestionar_paciente(request.user):
    raise PermissionDenied('Solo administración o secretaría puede crear pacientes.')
  if request.method == 'POST':
    form = PacienteForm(request.POST)
    formset = TutorFormSet(request.POST)

    if form.is_valid() and formset.is_valid():
      with transaction.atomic():
        paciente = form.save()
        formset.instance = paciente
        formset.save()
        AntecedentesNeurologicos.objects.get_or_create(paciente=paciente)

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
    if request.method == 'GET':
        Auditoria.objects.create(
            usuario=request.user,
            accion=Auditoria.Accion.CONSULTAR,
            modelo='AntecedentesNeurologicos',
            registro_id=antecedentes.pk,
            ip=request.META.get('REMOTE_ADDR'),
            detalle={'evento': 'Acceso a antecedentes clinicos', 'paciente_id': paciente.pk},
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
@solo_clinico
def crear_diagnostico(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == 'POST':
        form = DiagnosticoForm(request.POST)
        if form.is_valid():
            diagnostico = form.save(commit=False)
            diagnostico.paciente = paciente
            diagnostico.registrado_por = request.user
            diagnostico.save()
            Auditoria.objects.create(
                usuario=request.user,
                accion=Auditoria.Accion.CREAR,
                modelo='Diagnostico',
                registro_id=diagnostico.pk,
                ip=request.META.get('REMOTE_ADDR'),
                detalle={'paciente_id': paciente.pk, 'evento': 'Registro de diagnostico clinico'},
            )
            messages.success(request, 'Diagnóstico registrado en la ficha.')
            return redirect('pacientes:detalle', pk=paciente.pk)
    else:
        form = DiagnosticoForm(initial={'fecha_diagnostico': timezone.localdate()})
    return render(request, 'pacientes/diagnostico_form.html', {
        'form': form,
        'paciente': paciente,
    })

@login_required
def buscar(request):
  """Busqueda de pacientes segun el acceso del usuario."""
  busqueda = request.GET.get('q', '').strip()

  pacientes = Paciente.objects.all()
  if request.user.rol != 'ADMIN':
    pacientes = pacientes.filter(activo=True)

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
    resultado = {
      'id': paciente.pk,
      'nombre': paciente.nombre_completo,
      'rut': paciente.rut,
      'edad': paciente.edad_texto,
      'prevision': paciente.get_prevision_display(),
      'activo': paciente.activo,
      'url_detalle': reverse('pacientes:detalle', args=[paciente.pk]),
    }
    if request.user.rol == 'ADMIN':
      resultado['url_estado'] = reverse(
        'pacientes:cambiar_estado_paciente', args=[paciente.pk]
      )
    resultados.append(resultado)

  return JsonResponse({
    'pacientes': resultados,
  })


@login_required
def historial_asignaciones(request):
  if request.user.rol != 'ADMIN':
    return render(request, '403.html', status=403)

  vista = request.GET.get('vista', 'medicos')
  if vista not in ('asignaciones', 'medicos'):
    vista = 'medicos'
  busqueda = request.GET.get('q', '').strip()

  asignaciones = AsignacionProfesional.objects.select_related(
    'paciente', 'profesional'
  )
  medicos = Usuario.objects.filter(rol=Usuario.Rol.MEDICO)

  if busqueda and vista == 'asignaciones':
    asignaciones = asignaciones.filter(
      Q(paciente__nombres__icontains=busqueda)
      | Q(paciente__apellido_paterno__icontains=busqueda)
      | Q(paciente__apellido_materno__icontains=busqueda)
      | Q(paciente__rut__icontains=busqueda)
      | Q(profesional__first_name__icontains=busqueda)
      | Q(profesional__last_name__icontains=busqueda)
      | Q(profesional__username__icontains=busqueda)
    )
  if busqueda and vista == 'medicos':
    medicos = medicos.filter(
      Q(first_name__icontains=busqueda)
      | Q(last_name__icontains=busqueda)
      | Q(username__icontains=busqueda)
      | Q(profesion__icontains=busqueda)
      | Q(especialidad__icontains=busqueda)
    )

  asignaciones = asignaciones.order_by('-fecha_asignacion')
  medicos = medicos.order_by('first_name', 'last_name', 'username')
  paginador_asignaciones = Paginator(asignaciones, 15)
  paginador_medicos = Paginator(medicos, 15)
  pagina = request.GET.get('page')
  return render(request, 'pacientes/historial_asignaciones.html', {
    'asignaciones': paginador_asignaciones.get_page(pagina),
    'medicos': paginador_medicos.get_page(pagina),
    'vista': vista,
    'busqueda': busqueda,
  })


@login_required
def cambiar_estado_medico(request, pk):
  if request.user.rol != 'ADMIN':
    return render(request, '403.html', status=403)
  if request.method != 'POST':
    return redirect('pacientes:historial_asignaciones')

  with transaction.atomic():
    medico = get_object_or_404(
      Usuario.objects.select_for_update().filter(rol=Usuario.Rol.MEDICO),
      pk=pk,
    )
    medico.is_active = not medico.is_active
    if medico.is_active:
      medico.fecha_termino = None
    else:
      medico.fecha_termino = timezone.now()
      AsignacionProfesional.objects.filter(
        profesional=medico,
        activa=True,
      ).update(activa=False, fecha_termino=medico.fecha_termino)
    medico.save(update_fields=['is_active', 'fecha_termino'])

  if medico.is_active:
    messages.success(request, 'Cuenta médica activada. Debe asignarse nuevamente a los pacientes.')
  else:
    messages.success(request, 'Cuenta médica desactivada y asignaciones activas finalizadas.')
  url = reverse('pacientes:historial_asignaciones')
  filtros = urlencode({
    'vista': 'medicos',
    'q': request.POST.get('q', ''),
    'page': request.POST.get('page', '1'),
  })
  return redirect(f'{url}?{filtros}')


@login_required
def cambiar_estado_asignacion(request, pk):
  if request.user.rol != 'ADMIN':
    return render(request, '403.html', status=403)
  if request.method != 'POST':
    return redirect('pacientes:historial_asignaciones')

  asignacion = get_object_or_404(AsignacionProfesional, pk=pk)
  if not asignacion.activa and not asignacion.paciente.activo:
    messages.error(request, 'No se puede activar una asignación de un paciente desactivado.')
    url = reverse('pacientes:historial_asignaciones')
    filtros = urlencode({
      'vista': request.POST.get('vista', 'asignaciones'),
      'q': request.POST.get('q', ''),
      'page': request.POST.get('page', '1'),
    })
    return redirect(f'{url}?{filtros}')
  asignacion.activa = not asignacion.activa
  asignacion.fecha_termino = None if asignacion.activa else timezone.now()
  asignacion.save(update_fields=['activa', 'fecha_termino'])

  estado = 'activada' if asignacion.activa else 'desactivada'
  messages.success(request, f'Asignación {estado}.')
  url = reverse('pacientes:historial_asignaciones')
  datos_filtro = {
    'vista': request.POST.get('vista', 'asignaciones'),
    'q': request.POST.get('q', ''),
  }
  if request.POST.get('page'):
    datos_filtro['page'] = request.POST['page']
  filtros = urlencode(datos_filtro)
  return redirect(f'{url}?{filtros}')


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

  Auditoria.objects.create(
    usuario=request.user,
    accion=Auditoria.Accion.CONSULTAR,
    modelo='Atencion',
    registro_id=atencion.pk,
    ip=request.META.get('REMOTE_ADDR'),
    detalle={
      'evento': 'Acceso a detalle de atencion',
      'paciente_id': atencion.paciente_id,
      'profesional_id': atencion.profesional_id,
    },
  )

  return render(request, 'pacientes/atencion_detalle.html', {
    'atencion': atencion,
  })
