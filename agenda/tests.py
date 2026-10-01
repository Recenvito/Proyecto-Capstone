"""
Pruebas de las reglas de negocio de la agenda.

Ejecutar con:  ./venv/bin/python manage.py test
"""
from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pacientes.models import Paciente
from usuarios.models import Usuario

from .forms import CitaForm
from .models import Bloqueo, Cita, Disponibilidad


class VistasAgendaPorProfesionalTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.medico = Usuario.objects.create_user(
            username='medico_agenda_vista', password='Clave-Prueba-2026!',
            rol=Usuario.Rol.MEDICO,
        )
        cls.otro_medico = Usuario.objects.create_user(
            username='otro_agenda_vista', password='Clave-Prueba-2026!',
            rol=Usuario.Rol.MEDICO,
        )
        cls.paciente_asignado = Paciente.objects.create(
            rut='12345678-5', nombres='Ana', apellido_paterno='Asignada',
            fecha_nacimiento=date(2017, 5, 1), sexo='F',
        )
        cls.paciente_ajeno = Paciente.objects.create(
            rut='98765432-0', nombres='Ana', apellido_paterno='Ajena',
            fecha_nacimiento=date(2016, 2, 1), sexo='F',
        )
        from pacientes.models import AsignacionProfesional
        AsignacionProfesional.objects.create(
            paciente=cls.paciente_asignado, profesional=cls.medico,
        )

    def test_inicio_muestra_conteo_asignado_y_solo_citas_del_medico(self):
        hoy = timezone.localdate()
        cita_hoy = timezone.make_aware(
            datetime.combine(hoy, time(12, 0)), timezone.get_current_timezone()
        )
        Cita.objects.create(
            paciente=self.paciente_asignado, profesional=self.medico,
            fecha_hora=cita_hoy, motivo='Control asignado',
        )
        Cita.objects.create(
            paciente=self.paciente_ajeno, profesional=self.otro_medico,
            fecha_hora=cita_hoy + timedelta(minutes=30), motivo='Privada',
        )
        self.client.force_login(self.medico)
        respuesta = self.client.get(reverse('inicio'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['total_pacientes'], 1)
        self.assertEqual(list(respuesta.context['citas_hoy'].values_list('profesional_id', flat=True)), [self.medico.pk])

    def test_agenda_muestra_citas_aunque_no_haya_horario_y_no_permite_cambiar_medico(self):
        fecha = timezone.localdate() + timedelta(days=3)
        hora = timezone.make_aware(
            datetime.combine(fecha, time(11, 0)), timezone.get_current_timezone()
        )
        cita = Cita.objects.create(
            paciente=self.paciente_asignado, profesional=self.medico,
            fecha_hora=hora, motivo='Evaluación inicial',
        )
        Cita.objects.create(
            paciente=self.paciente_ajeno, profesional=self.otro_medico,
            fecha_hora=hora, motivo='No mostrar',
        )
        self.client.force_login(self.medico)
        respuesta = self.client.get(reverse('agenda:calendario'), {
            'fecha': fecha.isoformat(), 'profesional': self.otro_medico.pk,
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['profesional'], self.medico)
        self.assertContains(respuesta, self.paciente_asignado.nombre_completo)
        self.assertNotContains(respuesta, self.paciente_ajeno.nombre_completo)
        self.assertEqual(respuesta.context['proximas'].get(pk=cita.pk), cita)

    def test_busqueda_de_pacientes_filtra_por_asignacion_del_medico(self):
        self.client.force_login(self.medico)
        respuesta = self.client.get(reverse('pacientes:buscar'), {'q': 'Ana'})
        self.assertEqual(respuesta.status_code, 200)
        pacientes = respuesta.json()['pacientes']
        self.assertEqual([item['id'] for item in pacientes], [self.paciente_asignado.pk])

    def test_formulario_de_cita_limita_al_medico_a_pacientes_asignados(self):
        form = CitaForm(user=self.medico)
        self.assertEqual(
            list(form.fields['paciente'].queryset), [self.paciente_asignado]
        )
        self.assertEqual(list(form.fields['profesional'].queryset), [self.medico])
        self.assertTrue(form.fields['profesional'].disabled)

    def test_busqueda_de_agenda_encuentra_citas_de_otras_fechas_solo_del_medico(self):
        fecha = timezone.localdate() - timedelta(days=20)
        hora = timezone.make_aware(
            datetime.combine(fecha, time(10, 0)), timezone.get_current_timezone()
        )
        propia = Cita.objects.create(
            paciente=self.paciente_asignado, profesional=self.medico,
            fecha_hora=hora, motivo='Consulta de seguimiento',
        )
        Cita.objects.create(
            paciente=self.paciente_ajeno, profesional=self.otro_medico,
            fecha_hora=hora, motivo='Consulta de seguimiento',
        )
        self.client.force_login(self.medico)
        respuesta = self.client.get(reverse('agenda:calendario'), {'q': 'seguimiento'})
        self.assertContains(respuesta, self.paciente_asignado.nombre_completo)
        self.assertNotContains(respuesta, self.paciente_ajeno.nombre_completo)
        self.assertEqual(respuesta.context['resultados_busqueda'].get(pk=propia.pk), propia)


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
