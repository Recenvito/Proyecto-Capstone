"""Pruebas del modelo Paciente."""
from datetime import date, timedelta

from django.test import TestCase

from .forms import PacienteForm, TutorForm
from .models import Paciente


class PacienteTest(TestCase):
    def _crear(self, fecha_nacimiento, rut='44444444-4'):
        return Paciente.objects.create(
            rut=rut, nombres='Test', apellido_paterno='Paciente',
            fecha_nacimiento=fecha_nacimiento, sexo='M')

    def test_calcula_bien_la_edad_en_anios(self):
        hace_8_anios = date.today().replace(year=date.today().year - 8)
        paciente = self._crear(hace_8_anios)
        self.assertEqual(paciente.edad, 8)

    def test_un_lactante_muestra_la_edad_en_meses(self):
        hace_6_meses = date.today() - timedelta(days=182)
        paciente = self._crear(hace_6_meses, rut='55555555-5')
        self.assertIn('meses', paciente.edad_texto)

    def test_un_escolar_muestra_la_edad_en_anios(self):
        hace_7_anios = date.today().replace(year=date.today().year - 7)
        paciente = self._crear(hace_7_anios, rut='66666666-6')
        self.assertIn('anios', paciente.edad_texto)

    def test_el_nombre_completo_junta_nombres_y_apellidos(self):
        paciente = Paciente.objects.create(
            rut='77777777-7', nombres='Juan Pablo', apellido_paterno='Soto',
            apellido_materno='Lira', fecha_nacimiento=date(2015, 6, 1), sexo='M')
        self.assertEqual(paciente.nombre_completo, 'Juan Pablo Soto Lira')

    def test_el_nombre_completo_funciona_sin_apellido_materno(self):
        paciente = Paciente.objects.create(
            rut='88888888-8', nombres='Ana', apellido_paterno='Vega',
            fecha_nacimiento=date(2015, 6, 1), sexo='F')
        self.assertEqual(paciente.nombre_completo, 'Ana Vega')


class ValidacionesFichaTest(TestCase):
    def test_valida_rut_nombre_y_fecha_de_nacimiento(self):
        datos = {
            'rut': '12.345.678-5',
            'nombres': 'María José',
            'apellido_paterno': 'Muñoz-López',
            'apellido_materno': 'D’Ávila',
            'fecha_nacimiento': '2018-05-10',
            'sexo': Paciente.Sexo.FEMENINO,
            'prevision': Paciente.Prevision.FONASA,
        }
        self.assertTrue(PacienteForm(data=datos).is_valid())

        datos['rut'] = '12.345.678-1'
        self.assertIn('rut', PacienteForm(data=datos).errors)
        datos['rut'] = '12.345.678-5'
        datos['nombres'] = 'María123'
        self.assertIn('nombres', PacienteForm(data=datos).errors)
        datos['nombres'] = 'María'
        datos['fecha_nacimiento'] = '2099-01-01'
        self.assertIn('fecha_nacimiento', PacienteForm(data=datos).errors)

    def test_valida_telefono_y_correo_del_tutor(self):
        datos = {
            'nombre_completo': 'Camila Muñoz',
            'rut': '11.111.111-1',
            'parentesco': 'MADRE',
            'telefono': 'solo palabras',
            'email': 'no-es-correo',
            'es_principal': 'on',
        }
        form = TutorForm(data=datos)
        self.assertFalse(form.is_valid())
        self.assertIn('telefono', form.errors)
        self.assertIn('email', form.errors)
