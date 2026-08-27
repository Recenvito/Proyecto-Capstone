"""
Pruebas de las reglas de negocio de la agenda.

Ejecutar con:  ./venv/bin/python manage.py test
"""
from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from pacientes.models import Paciente
from usuarios.models import Usuario

from .models import Bloqueo, Cita, Disponibilidad


class ReglasDeAgendaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.medico = Usuario.objects.create_user(
            username='medico_agenda', password='clave-de-prueba',
            rol=Usuario.Rol.MEDICO)
        cls.paciente_a = Paciente.objects.create(
            rut='22222222-2', nombres='Ana', apellido_paterno='Uno',
            fecha_nacimiento=date(2016, 1, 1), sexo='F')
        cls.paciente_b = Paciente.objects.create(
            rut='33333333-3', nombres='Bruno', apellido_paterno='Dos',
            fecha_nacimiento=date(2015, 1, 1), sexo='M')

    def _momento(self, hora=15, dias=7):
        """Una fecha futura a una hora concreta."""
        futuro = timezone.localdate() + timedelta(days=dias)
        return timezone.make_aware(
            datetime.combine(futuro, datetime.min.time().replace(hour=hora)),
            timezone.get_current_timezone())

    def test_no_se_pueden_agendar_dos_pacientes_a_la_misma_hora(self):
        momento = self._momento()
        Cita.objects.create(paciente=self.paciente_a, profesional=self.medico,
                            fecha_hora=momento, duracion_minutos=30)

        with self.assertRaises(ValidationError):
            Cita.objects.create(paciente=self.paciente_b, profesional=self.medico,
                                fecha_hora=momento, duracion_minutos=30)

    def test_no_se_permite_una_cita_que_se_solapa_parcialmente(self):
        momento = self._momento()
        Cita.objects.create(paciente=self.paciente_a, profesional=self.medico,
                            fecha_hora=momento, duracion_minutos=30)

        # Empieza 15 minutos despues: pisa la segunda mitad de la anterior.
        with self.assertRaises(ValidationError):
            Cita.objects.create(paciente=self.paciente_b, profesional=self.medico,
                                fecha_hora=momento + timedelta(minutes=15),
                                duracion_minutos=30)

    def test_si_se_puede_agendar_justo_despues_de_otra_cita(self):
        momento = self._momento()
        Cita.objects.create(paciente=self.paciente_a, profesional=self.medico,
                            fecha_hora=momento, duracion_minutos=30)

        seguida = Cita.objects.create(
            paciente=self.paciente_b, profesional=self.medico,
            fecha_hora=momento + timedelta(minutes=30), duracion_minutos=30)
        self.assertIsNotNone(seguida.pk)

    def test_una_cita_cancelada_libera_el_cupo(self):
        momento = self._momento()
        cita = Cita.objects.create(paciente=self.paciente_a, profesional=self.medico,
                                   fecha_hora=momento, duracion_minutos=30)
        cita.estado = Cita.Estado.CANCELADA
        cita.save()

        reemplazo = Cita.objects.create(
            paciente=self.paciente_b, profesional=self.medico,
            fecha_hora=momento, duracion_minutos=30)
        self.assertIsNotNone(reemplazo.pk)

    def test_no_se_agenda_dentro_de_un_bloqueo(self):
        momento = self._momento()
        Bloqueo.objects.create(profesional=self.medico,
                               inicio=momento - timedelta(hours=1),
                               fin=momento + timedelta(hours=3),
                               motivo='Vacaciones')

        with self.assertRaises(ValidationError):
            Cita.objects.create(paciente=self.paciente_a, profesional=self.medico,
                                fecha_hora=momento, duracion_minutos=30)

    def test_la_disponibilidad_genera_la_cantidad_correcta_de_cupos(self):
        disponibilidad = Disponibilidad.objects.create(
            profesional=self.medico, dia_semana=0,  # lunes
            hora_inicio=time(15, 0), hora_fin=time(19, 0), duracion_cita_minutos=30)

        # Buscamos el proximo lunes
        dia = timezone.localdate()
        while dia.weekday() != 0:
            dia += timedelta(days=1)

        cupos = disponibilidad.generar_cupos(dia)
        self.assertEqual(len(cupos), 8)  # 4 horas / 30 min

    def test_no_genera_cupos_en_un_dia_que_no_atiende(self):
        disponibilidad = Disponibilidad.objects.create(
            profesional=self.medico, dia_semana=0,  # lunes
            hora_inicio=time(15, 0), hora_fin=time(19, 0))

        dia = timezone.localdate()
        while dia.weekday() != 2:  # un miercoles
            dia += timedelta(days=1)

        self.assertEqual(disponibilidad.generar_cupos(dia), [])
