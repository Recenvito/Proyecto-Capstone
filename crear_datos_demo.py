"""
Datos de prueba para desarrollo.
Ejecutar con:  ./venv/bin/python manage.py shell < crear_datos_demo.py

ATENCION: las contrasenias de este archivo son SOLO para desarrollo local.
Nunca usar estos usuarios en el sistema real de la consulta.
"""
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.utils import timezone

from agenda.models import Cita, Disponibilidad
from pacientes.models import (AsignacionProfesional, AntecedentesNeurologicos,
                              Diagnostico, Paciente, Tutor)
from usuarios.models import Usuario

if not settings.DEBUG:
    raise RuntimeError('Los datos ficticios solo se pueden cargar con DEBUG=1.')

# ---------- Usuarios ----------
admin, creado = Usuario.objects.get_or_create(
    username='admin',
    defaults={'first_name': 'Administrador', 'last_name': 'Sistema',
              'email': 'admin@ejemplo.test',
              'rol': Usuario.Rol.ADMIN, 'is_staff': True, 'is_superuser': True},
)
if not admin.email:
    admin.email = 'admin@ejemplo.test'
    admin.save(update_fields=['email'])
if creado:
    admin.set_password('admin123')
    admin.save()

doctora, creado = Usuario.objects.get_or_create(
    username='dra.neuro',
    defaults={'first_name': 'Maria Jose', 'last_name': 'Rivas',
              'email': 'dra.neuro@ejemplo.test',
              'rol': Usuario.Rol.MEDICO, 'is_staff': True,
              'especialidad': 'Neurologia infantil'},
)
if not doctora.email:
    doctora.email = 'dra.neuro@ejemplo.test'
    doctora.save(update_fields=['email'])
if creado:
    doctora.set_password('demo1234')
    doctora.save()

doctora_dos, creado = Usuario.objects.get_or_create(
    username='dra.psico',
    defaults={'first_name': 'Camila', 'last_name': 'Fuentes',
              'email': 'dra.psico@ejemplo.test',
              'rol': Usuario.Rol.MEDICO, 'is_staff': True,
              'especialidad': 'Psicologia infantil'},
)
if not doctora_dos.email:
    doctora_dos.email = 'dra.psico@ejemplo.test'
    doctora_dos.save(update_fields=['email'])
if creado:
    doctora_dos.set_password('demo1234')
    doctora_dos.save()

secretaria, creado = Usuario.objects.get_or_create(
    username='secretaria',
    defaults={'first_name': 'Carolina', 'last_name': 'Soto',
              'email': 'secretaria@ejemplo.test',
              'rol': Usuario.Rol.SECRETARIA},
)
if not secretaria.email:
    secretaria.email = 'secretaria@ejemplo.test'
    secretaria.save(update_fields=['email'])
if creado:
    secretaria.set_password('demo1234')
    secretaria.save()

# ---------- Horario de atencion ----------
for dia in [Disponibilidad.DiaSemana.LUNES, Disponibilidad.DiaSemana.MIERCOLES,
            Disponibilidad.DiaSemana.JUEVES]:
    Disponibilidad.objects.get_or_create(
        profesional=doctora, dia_semana=dia,
        defaults={'hora_inicio': time(15, 0), 'hora_fin': time(19, 0),
                  'duracion_cita_minutos': 30, 'lugar': 'Consulta particular'},
    )

# ---------- Pacientes ----------
from pacientes.datos_prueba import PACIENTES_DEMO as demo

pacientes_demo = []
for indice, (rut, nom, ap, am, fnac, sexo, tutor, parent, fono, diag, cie) in enumerate(demo, start=1):
    p, creado = Paciente.objects.get_or_create(
        rut=rut,
        defaults={'nombres': nom, 'apellido_paterno': ap, 'apellido_materno': am,
                  'fecha_nacimiento': fnac, 'sexo': sexo, 'comuna': 'Santiago',
                  'direccion': f'{100 + indice} Calle de Prueba',
                  'prevision': 'FONASA', 'colegio': f'Escuela de Prueba {indice:02}',
                  'curso': f'{1 + (indice % 8)}° básico',
                  'derivado_por': 'Pediatra tratante'},
    )
    if (p.nombres, p.apellido_paterno, p.apellido_materno, p.fecha_nacimiento) != (nom, ap, am, fnac):
        raise RuntimeError(f'El RUT {rut} ya está asociado a un paciente distinto; se canceló la carga.')
    pacientes_demo.append(p)

    # Completar ficha de demostración existente sin sobrescribir campos poblados.
    for campo, valor in {
        'direccion': f'{100 + indice} Calle de Prueba',
        'comuna': 'Santiago',
        'prevision': 'FONASA',
        'colegio': f'Escuela de Prueba {indice:02}',
        'curso': f'{1 + (indice % 8)}° básico',
        'derivado_por': 'Pediatra tratante (dato ficticio)',
    }.items():
        if not getattr(p, campo):
            setattr(p, campo, valor)
    p.save()

    if creado:
        AntecedentesNeurologicos.objects.create(
            paciente=p, semanas_gestacion=38, peso_nacimiento_gramos=3200 + indice * 8,
            tipo_parto='VAGINAL', edad_marcha=13, edad_primeras_palabras=12,
            antecedentes_familiares='Sin antecedentes familiares relevantes (dato ficticio)',
            antecedentes_morbidos='Sin antecedentes mórbidos referidos (dato ficticio)',
            alergias='Sin alergias conocidas (dato ficticio)',
            medicamentos_actuales='Sin medicamentos actuales (dato ficticio)')
    else:
        antecedentes, _ = AntecedentesNeurologicos.objects.get_or_create(
            paciente=p,
            defaults={'semanas_gestacion': 38,
                      'peso_nacimiento_gramos': 3200 + indice * 8,
                      'tipo_parto': 'VAGINAL', 'edad_marcha': 13,
                      'edad_primeras_palabras': 12},
        )
        for campo, valor in {
            'semanas_gestacion': 38,
            'peso_nacimiento_gramos': 3200 + indice * 8,
            'edad_marcha': 13,
            'edad_primeras_palabras': 12,
            'antecedentes_familiares': 'Sin antecedentes familiares relevantes (dato ficticio)',
            'antecedentes_morbidos': 'Sin antecedentes mórbidos referidos (dato ficticio)',
            'alergias': 'Sin alergias conocidas (dato ficticio)',
            'medicamentos_actuales': 'Sin medicamentos actuales (dato ficticio)',
        }.items():
            if not getattr(antecedentes, campo):
                setattr(antecedentes, campo, valor)
        antecedentes.save()
    Tutor.objects.get_or_create(
        paciente=p,
        es_principal=True,
        defaults={'nombre_completo': tutor, 'parentesco': parent, 'telefono': fono,
                  'email': f'apoderado{indice:02}@ejemplo.test',
                  'rut': f'99{indice:06}-0'},
    )
    tutor_obj = Tutor.objects.get(paciente=p, es_principal=True)
    campos_tutor = []
    if not tutor_obj.email:
        tutor_obj.email = f'apoderado{indice:02}@ejemplo.test'
        campos_tutor.append('email')
    if not tutor_obj.rut:
        tutor_obj.rut = f'99{indice:06}-0'
        campos_tutor.append('rut')
    if campos_tutor:
        tutor_obj.save(update_fields=campos_tutor)
    Diagnostico.objects.get_or_create(
        paciente=p,
        codigo_cie10=cie,
        defaults={'descripcion': diag,
                  'fecha_diagnostico': date.today() - timedelta(days=120),
                  'registrado_por': doctora,
                  'notas': 'Registro ficticio de prueba; requiere validación clínica.'},
    )

# ---------- Asignacion de los pacientes demo ----------
# Sin esto la doctora no puede abrir ninguna ficha: el acceso clinico exige
# que el profesional tenga asignado al paciente.
for indice, p in enumerate(pacientes_demo):
    profesional = doctora if indice % 2 == 0 else doctora_dos
    AsignacionProfesional.objects.update_or_create(
        paciente=p, profesional=profesional, defaults={'activa': True})

# ---------- Citas de hoy ----------
tz = timezone.get_current_timezone()
hoy = timezone.localdate()
pacientes = pacientes_demo[:3]

for i, p in enumerate(pacientes):
    inicio = timezone.make_aware(
        datetime.combine(hoy, datetime.min.time().replace(hour=15)), tz)
    momento = inicio + timedelta(minutes=30 * i)
    if not Cita.objects.filter(profesional=doctora, fecha_hora=momento).exists():
        Cita.objects.create(
            paciente=p, profesional=doctora, fecha_hora=momento,
            tipo=Cita.Tipo.CONTROL if i else Cita.Tipo.PRIMERA_VEZ,
            estado=Cita.Estado.CONFIRMADA if i == 0 else Cita.Estado.AGENDADA,
            motivo='Control de tratamiento', creada_por=secretaria)

print('=' * 55)
print('DATOS DE PRUEBA CREADOS')
print('=' * 55)
print(f'Pacientes : {Paciente.objects.count()}')
print(f'Citas     : {Cita.objects.count()}')
print(f'Usuarios  : {Usuario.objects.count()}')
print(f'Asignaciones: {AsignacionProfesional.objects.count()}')
print(f'Pacientes de prueba preparados: {len(pacientes_demo)}')
print()
print('Usuarios para entrar al sistema (SOLO desarrollo local):')
print('  admin       / admin123    -> administrador')
print('  dra.neuro   / demo1234    -> medico (ve la ficha clinica)')
print('  dra.psico   / demo1234    -> medico (ve sus pacientes asignados)')
print('  secretaria  / demo1234    -> secretaria (NO ve la ficha clinica)')
