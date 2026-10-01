from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pacientes.datos_prueba import PACIENTES_DEMO
from pacientes.models import (
    AsignacionProfesional,
    AntecedentesNeurologicos,
    Diagnostico,
    Paciente,
    Tutor,
)
from usuarios.models import Usuario


class Command(BaseCommand):
    help = 'Carga 20 fichas clínicas ficticias y las asigna a médicos activos.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                'Carga bloqueada: activa DEBUG solo en una base de desarrollo.'
            )

        medicos = list(
            Usuario.objects.filter(rol=Usuario.Rol.MEDICO, is_active=True)
            .order_by('pk')
        )
        if not medicos:
            raise CommandError('No hay médicos activos a quienes asignar los pacientes.')

        ruts = [item[0] for item in PACIENTES_DEMO]
        existentes = {
            paciente.rut: paciente
            for paciente in Paciente.objects.filter(rut__in=ruts)
        }
        for item in PACIENTES_DEMO:
            rut, nombres, apellido_paterno, apellido_materno, nacimiento = item[:5]
            paciente = existentes.get(rut)
            if paciente and (
                paciente.nombres != nombres
                or paciente.apellido_paterno != apellido_paterno
                or paciente.apellido_materno != apellido_materno
                or paciente.fecha_nacimiento != nacimiento
            ):
                raise CommandError(
                    f'El RUT {rut} ya pertenece a otro paciente. No se hicieron cambios.'
                )

        creados = 0
        with transaction.atomic():
            for indice, item in enumerate(PACIENTES_DEMO, start=1):
                (rut, nombres, ap_paterno, ap_materno, nacimiento, sexo,
                 nombre_tutor, parentesco, telefono, descripcion, cie10) = item
                paciente, creado = Paciente.objects.get_or_create(
                    rut=rut,
                    defaults={
                        'nombres': nombres,
                        'apellido_paterno': ap_paterno,
                        'apellido_materno': ap_materno,
                        'fecha_nacimiento': nacimiento,
                        'sexo': sexo,
                    },
                )
                creados += int(creado)
                self._completar_ficha(paciente, indice)
                self._completar_tutor(
                    paciente, indice, nombre_tutor, parentesco, telefono
                )
                self._completar_antecedentes(paciente, indice)
                Diagnostico.objects.get_or_create(
                    paciente=paciente,
                    codigo_cie10=cie10,
                    defaults={
                        'descripcion': descripcion,
                        'fecha_diagnostico': date.today() - timedelta(days=120),
                        'registrado_por': medicos[(indice - 1) % len(medicos)],
                        'notas': (
                            'Dato ficticio de demostración; no corresponde a una '
                            'evaluación clínica real.'
                        ),
                    },
                )
                AsignacionProfesional.objects.update_or_create(
                    paciente=paciente,
                    profesional=medicos[(indice - 1) % len(medicos)],
                    defaults={'activa': True},
                )

        self.stdout.write(self.style.SUCCESS(
            f'20 pacientes ficticios listos; {creados} nuevos. '
            f'Asignados en rotación entre {len(medicos)} médicos activos.'
        ))

    @staticmethod
    def _completar_ficha(paciente, indice):
        valores = {
            'direccion': f'{100 + indice} Calle de Prueba',
            'comuna': 'Santiago',
            'prevision': 'FONASA',
            'colegio': f'Escuela de Prueba {indice:02}',
            'curso': f'{1 + indice % 8}° básico',
            'derivado_por': 'Pediatra tratante (dato ficticio)',
        }
        cambios = []
        for campo, valor in valores.items():
            if not getattr(paciente, campo):
                setattr(paciente, campo, valor)
                cambios.append(campo)
        if cambios:
            paciente.save(update_fields=cambios + ['actualizado_en'])

    @staticmethod
    def _completar_tutor(paciente, indice, nombre, parentesco, telefono):
        tutor, _ = Tutor.objects.get_or_create(
            paciente=paciente,
            es_principal=True,
            defaults={
                'nombre_completo': nombre,
                'parentesco': parentesco,
                'telefono': telefono,
                'rut': f'99{indice:06}-0',
                'email': f'apoderado{indice:02}@ejemplo.test',
            },
        )
        cambios = []
        for campo, valor in {
            'rut': f'99{indice:06}-0',
            'email': f'apoderado{indice:02}@ejemplo.test',
        }.items():
            if not getattr(tutor, campo):
                setattr(tutor, campo, valor)
                cambios.append(campo)
        if cambios:
            tutor.save(update_fields=cambios)

    @staticmethod
    def _completar_antecedentes(paciente, indice):
        antecedentes, _ = AntecedentesNeurologicos.objects.get_or_create(
            paciente=paciente,
            defaults={
                'semanas_gestacion': 38,
                'peso_nacimiento_gramos': 3200 + indice * 8,
                'tipo_parto': AntecedentesNeurologicos.TipoParto.VAGINAL,
                'edad_marcha': 13,
                'edad_primeras_palabras': 12,
            },
        )
        valores = {
            'semanas_gestacion': 38,
            'peso_nacimiento_gramos': 3200 + indice * 8,
            'antecedentes_familiares': 'Sin antecedentes referidos (dato ficticio)',
            'antecedentes_morbidos': 'Sin antecedentes referidos (dato ficticio)',
            'alergias': 'Sin alergias conocidas (dato ficticio)',
            'medicamentos_actuales': 'Sin medicamentos actuales (dato ficticio)',
        }
        cambios = []
        for campo, valor in valores.items():
            if not getattr(antecedentes, campo):
                setattr(antecedentes, campo, valor)
                cambios.append(campo)
        if cambios:
            antecedentes.save(update_fields=cambios + ['actualizado_en'])
