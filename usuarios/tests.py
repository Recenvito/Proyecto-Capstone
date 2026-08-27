"""
Pruebas del control de acceso por rol.

Verifican que la ficha clinica solo sea accesible para el personal medico,
que es el requisito de confidencialidad mas importante del sistema.

Ejecutar con:  ./venv/bin/python manage.py test
"""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from pacientes.models import Paciente
from usuarios.models import Usuario


class ControlDeAccesoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.medico = Usuario.objects.create_user(
            username='medico_test', password='clave-de-prueba',
            rol=Usuario.Rol.MEDICO, first_name='Doctora', last_name='Prueba')
        cls.secretaria = Usuario.objects.create_user(
            username='secretaria_test', password='clave-de-prueba',
            rol=Usuario.Rol.SECRETARIA)
        cls.paciente = Paciente.objects.create(
            rut='11111111-1', nombres='Paciente', apellido_paterno='De',
            apellido_materno='Prueba', fecha_nacimiento=date(2018, 5, 10), sexo='M')

    # --- Sin iniciar sesion ---

    def test_visitante_anonimo_es_redirigido_al_login(self):
        respuesta = self.client.get(reverse('pacientes:detalle', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta.url)

    def test_visitante_anonimo_no_entra_a_la_agenda(self):
        respuesta = self.client.get(reverse('agenda:calendario'))
        self.assertEqual(respuesta.status_code, 302)

    # --- Rol medico ---

    def test_medico_ve_la_ficha_clinica(self):
        self.client.force_login(self.medico)
        respuesta = self.client.get(reverse('pacientes:detalle', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Diagnosticos')

    def test_medico_puede_registrar_una_atencion(self):
        self.client.force_login(self.medico)
        respuesta = self.client.get(
            reverse('pacientes:crear_atencion', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 200)

    def test_medico_puede_editar_antecedentes(self):
        self.client.force_login(self.medico)
        respuesta = self.client.get(
            reverse('pacientes:antecedentes', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 200)

    # --- Rol secretaria ---

    def test_secretaria_no_ve_el_contenido_clinico_de_la_ficha(self):
        self.client.force_login(self.secretaria)
        respuesta = self.client.get(reverse('pacientes:detalle', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'Diagnosticos')
        self.assertNotContains(respuesta, 'Historial de atenciones')

    def test_secretaria_tiene_prohibido_registrar_atenciones(self):
        self.client.force_login(self.secretaria)
        respuesta = self.client.get(
            reverse('pacientes:crear_atencion', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 403)

    def test_secretaria_tiene_prohibido_editar_antecedentes(self):
        self.client.force_login(self.secretaria)
        respuesta = self.client.get(
            reverse('pacientes:antecedentes', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 403)

    def test_secretaria_si_puede_usar_la_agenda(self):
        self.client.force_login(self.secretaria)
        respuesta = self.client.get(reverse('agenda:calendario'))
        self.assertEqual(respuesta.status_code, 200)
