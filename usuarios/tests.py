"""
Pruebas del control de acceso por rol.

Verifican el requisito de confidencialidad mas importante del sistema:
la ficha clinica solo es accesible para el personal medico, y ademas solo
para el profesional que tiene asignado a ese paciente.

Ejecutar con:  ./venv/bin/python manage.py test
"""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from pacientes.models import AsignacionProfesional, Paciente
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
        cls.otro_medico = Usuario.objects.create_user(
            username='otro_medico_test', password='clave-de-prueba',
            rol=Usuario.Rol.MEDICO, first_name='Otro', last_name='Medico')
        cls.paciente = Paciente.objects.create(
            rut='11111111-1', nombres='Paciente', apellido_paterno='De',
            apellido_materno='Prueba', fecha_nacimiento=date(2018, 5, 10), sexo='M')

        # El acceso clinico exige que el profesional tenga asignado al paciente.
        # cls.medico lo tiene; cls.otro_medico no, a proposito.
        AsignacionProfesional.objects.create(
            paciente=cls.paciente, profesional=cls.medico, activa=True)

    # --- Sin iniciar sesion ---

    def test_visitante_anonimo_es_redirigido_al_login(self):
        respuesta = self.client.get(reverse('pacientes:detalle', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta.url)

    def test_visitante_anonimo_no_entra_a_la_agenda(self):
        respuesta = self.client.get(reverse('agenda:calendario'))
        self.assertEqual(respuesta.status_code, 302)

    # --- Rol medico CON el paciente asignado ---

    def test_medico_asignado_ve_la_ficha_clinica(self):
        self.client.force_login(self.medico)
        respuesta = self.client.get(reverse('pacientes:detalle', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Diagnosticos')

    def test_medico_asignado_puede_registrar_una_atencion(self):
        self.client.force_login(self.medico)
        respuesta = self.client.get(
            reverse('pacientes:crear_atencion', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 200)

    def test_medico_asignado_puede_editar_antecedentes(self):
        self.client.force_login(self.medico)
        respuesta = self.client.get(
            reverse('pacientes:antecedentes', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 200)

    # --- Rol medico SIN el paciente asignado ---

    def test_medico_no_asignado_no_ve_la_ficha(self):
        """Un medico no puede entrar a la ficha de un paciente que no trata."""
        self.client.force_login(self.otro_medico)
        respuesta = self.client.get(reverse('pacientes:detalle', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 403)

    def test_medico_no_asignado_no_puede_registrar_atenciones(self):
        self.client.force_login(self.otro_medico)
        respuesta = self.client.get(
            reverse('pacientes:crear_atencion', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 403)

    def test_una_asignacion_desactivada_revoca_el_acceso(self):
        """Al dar de baja la asignacion, el medico pierde el acceso a la ficha."""
        AsignacionProfesional.objects.filter(
            paciente=self.paciente, profesional=self.medico).update(activa=False)
        self.client.force_login(self.medico)
        respuesta = self.client.get(reverse('pacientes:detalle', args=[self.paciente.pk]))
        self.assertEqual(respuesta.status_code, 403)

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
