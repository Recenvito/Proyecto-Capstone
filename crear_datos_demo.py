"""
Datos de prueba para desarrollo.
Ejecutar con:  ./venv/bin/python manage.py shell < crear_datos_demo.py

ATENCION: las contrasenias de este archivo son SOLO para desarrollo local.
Nunca usar estos usuarios en el sistema real de la consulta.
"""
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from agenda.models import Cita, Disponibilidad
from pacientes.models import AntecedentesNeurologicos, Diagnostico, Paciente, Tutor
from usuarios.models import Usuario

# ---------- Usuarios ----------
admin, creado = Usuario.objects.get_or_create(
    username='admin',
    defaults={'first_name': 'Administrador', 'last_name': 'Sistema',
              'rol': Usuario.Rol.ADMIN, 'is_staff': True, 'is_superuser': True},
)
if creado:
    admin.set_password('admin123')
    admin.save()

doctora, creado = Usuario.objects.get_or_create(
    username='dra.neuro',
    defaults={'first_name': 'Maria Jose', 'last_name': 'Rivas',
              'rol': Usuario.Rol.MEDICO, 'is_staff': True,
              'especialidad': 'Neurologia infantil'},
)
if creado:
    doctora.set_password('demo1234')
    doctora.save()

secretaria, creado = Usuario.objects.get_or_create(
    username='secretaria',
    defaults={'first_name': 'Carolina', 'last_name': 'Soto',
              'rol': Usuario.Rol.SECRETARIA},
)
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
demo = [

    # 1
    ('20123456-7', 'Matias Ignacio', 'Perez', 'Gonzalez', date(2017, 3, 14), 'M',
     'Ana Maria Gonzalez', 'MADRE', '+56 9 8765 4321',
     'Trastorno por deficit atencional', 'F90.0'),

    # 2
    ('21987654-3', 'Sofia Antonia', 'Munoz', 'Lara', date(2019, 8, 2), 'F',
     'Pedro Munoz', 'PADRE', '+56 9 1234 5678',
     'Epilepsia focal', 'G40.2'),

    # 3
    ('22456789-1', 'Benjamin', 'Rojas', 'Castro', date(2023, 11, 20), 'M',
     'Claudia Castro', 'MADRE', '+56 9 5555 1234',
     'Retraso del desarrollo psicomotor', 'F82'),

    # 4
    ('20543218-6', 'Isidora Fernanda', 'Soto', 'Navarro', date(2018, 5, 21), 'F',
     'Carolina Navarro', 'MADRE', '+56 9 6123 4587',
     'Trastorno del lenguaje', 'F80.9'),

    # 5
    ('21784563-2', 'Vicente Alejandro', 'Contreras', 'Molina', date(2016, 9, 8), 'M',
     'Jorge Contreras', 'PADRE', '+56 9 7345 2198',
     'Trastorno por deficit atencional', 'F90.0'),

    # 6
    ('22653147-8', 'Emilia Josefa', 'Araya', 'Fuentes', date(2020, 1, 17), 'F',
     'Marcela Fuentes', 'MADRE', '+56 9 8456 3271',
     'Retraso del desarrollo psicomotor', 'F82'),

    # 7
    ('19876543-5', 'Tomas Ignacio', 'Silva', 'Paredes', date(2015, 7, 29), 'M',
     'Daniela Paredes', 'MADRE', '+56 9 9234 6712',
     'Epilepsia focal', 'G40.2'),

    # 8
    ('21345678-9', 'Florencia Paz', 'Vargas', 'Reyes', date(2018, 12, 4), 'F',
     'Rodrigo Vargas', 'PADRE', '+56 9 4567 8912',
     'Trastorno del lenguaje', 'F80.9'),

    # 9
    ('22874561-4', 'Agustin', 'Castillo', 'Bravo', date(2021, 4, 13), 'M',
     'Patricia Bravo', 'MADRE', '+56 9 6789 2341',
     'Retraso del desarrollo psicomotor', 'F82'),

    # 10
    ('20431876-3', 'Catalina Sofia', 'Herrera', 'Diaz', date(2017, 10, 25), 'F',
     'Luis Herrera', 'PADRE', '+56 9 8123 4567',
     'Trastorno por deficit atencional', 'F90.0'),

    # 11
    ('21654328-7', 'Joaquin Andres', 'Navarro', 'Torres', date(2016, 2, 11), 'M',
     'Paula Torres', 'MADRE', '+56 9 5678 1234',
     'Epilepsia focal', 'G40.2'),

    # 12
    ('22317894-5', 'Antonia Paz', 'Espinoza', 'Rojas', date(2019, 6, 30), 'F',
     'Miguel Espinoza', 'PADRE', '+56 9 7456 2189',
     'Trastorno del lenguaje', 'F80.9'),

    # 13
    ('20987631-2', 'Lucas Benjamin', 'Pino', 'Morales', date(2020, 9, 16), 'M',
     'Andrea Morales', 'MADRE', '+56 9 6345 7891',
     'Retraso del desarrollo psicomotor', 'F82'),

    # 14
    ('22154367-8', 'Martina Ignacia', 'Salazar', 'Vega', date(2018, 3, 7), 'F',
     'Cristian Salazar', 'PADRE', '+56 9 8234 5671',
     'Trastorno por deficit atencional', 'F90.0'),

    # 15
    ('20765432-1', 'Gabriel Antonio', 'Leiva', 'Mendoza', date(2015, 11, 19), 'M',
     'Valentina Mendoza', 'MADRE', '+56 9 9123 6745',
     'Epilepsia focal', 'G40.2'),

    # 16
    ('21893245-6', 'Agustina Maria', 'Fuentes', 'Carrasco', date(2021, 7, 23), 'F',
     'Sebastian Carrasco', 'PADRE', '+56 9 5346 7812',
     'Retraso del desarrollo psicomotor', 'F82'),

    # 17
    ('22567134-9', 'Maximiliano', 'Reyes', 'Sanhueza', date(2017, 1, 28), 'M',
     'Marcela Sanhueza', 'MADRE', '+56 9 6874 2315',
     'Trastorno del lenguaje', 'F80.9'),

    # 18
    ('20345671-5', 'Josefa Fernanda', 'Molina', 'Cortes', date(2019, 10, 12), 'F',
     'Felipe Molina', 'PADRE', '+56 9 7564 1892',
     'Trastorno por deficit atencional', 'F90.0'),

    # 19
    ('21456783-4', 'Diego Nicolas', 'Paredes', 'Guzman', date(2016, 6, 5), 'M',
     'Carolina Guzman', 'MADRE', '+56 9 8345 6721',
     'Epilepsia focal', 'G40.2'),

    # 20
    ('22913456-7', 'Valentina Sofia', 'Bravo', 'Cisternas', date(2020, 12, 9), 'F',
     'Rodrigo Cisternas', 'PADRE', '+56 9 6234 8951',
     'Retraso del desarrollo psicomotor', 'F82'),

]

for rut, nom, ap, am, fnac, sexo, tutor, parent, fono, diag, cie in demo:
    p, creado = Paciente.objects.get_or_create(
        rut=rut,
        defaults={'nombres': nom, 'apellido_paterno': ap, 'apellido_materno': am,
                  'fecha_nacimiento': fnac, 'sexo': sexo, 'comuna': 'Santiago',
                  'derivado_por': 'Pediatra tratante'},
    )
    if creado:
        Tutor.objects.create(paciente=p, nombre_completo=tutor, parentesco=parent,
                             telefono=fono, es_principal=True)
        AntecedentesNeurologicos.objects.create(
            paciente=p, semanas_gestacion=38, peso_nacimiento_gramos=3200,
            tipo_parto='VAGINAL', edad_marcha=13, edad_primeras_palabras=12)
        Diagnostico.objects.create(paciente=p, descripcion=diag, codigo_cie10=cie,
                                   fecha_diagnostico=date.today() - timedelta(days=120),
                                   registrado_por=doctora)

# ---------- Citas de hoy ----------
tz = timezone.get_current_timezone()
hoy = timezone.localdate()
pacientes = list(Paciente.objects.all()[:3])

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
print()
print('Usuarios para entrar al sistema (SOLO desarrollo local):')
print('  admin       / admin123    -> administrador')
print('  dra.neuro   / demo1234    -> medico (ve la ficha clinica)')
print('  secretaria  / demo1234    -> secretaria (NO ve la ficha clinica)')
