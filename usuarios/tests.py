"""
Pruebas del control de acceso por rol.

Verifican el requisito de confidencialidad mas importante del sistema:
la ficha clinica solo es accesible para el personal medico, y ademas solo
para el profesional que tiene asignado a ese paciente.

Ejecutar con:  ./venv/bin/python manage.py test
"""
from datetime import date
import re
from io import StringIO

from django.core import mail
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from pacientes.models import (
    AsignacionProfesional,
    AntecedentesNeurologicos,
    Diagnostico,
    Paciente,
    Tutor,
)
from usuarios.forms import UsuarioCreationForm
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
        self.assertContains(respuesta, 'Disciplina o servicio')

    def test_medico_asignado_registra_atencion_y_diagnostico_en_historial(self):
        from pacientes.models import Atencion
        from django.utils import timezone

        self.client.force_login(self.medico)
        fecha = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
        respuesta = self.client.post(
            reverse('pacientes:crear_atencion', args=[self.paciente.pk]),
            {
                'fecha': fecha,
                'tipo_atencion': 'Neurología infantil',
                'motivo_consulta': 'Control de seguimiento',
                'anamnesis': 'Sin cambios relevantes',
                'examen_fisico': '',
                'impresion_diagnostica': 'Epilepsia focal en seguimiento',
                'indicaciones': 'Mantener control',
                'examenes_solicitados': '', 'derivaciones': '',
                'proximo_control': '3 meses',
                'peso_kg': '', 'talla_cm': '', 'perimetro_cefalico_cm': '',
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        atencion = Atencion.objects.get(paciente=self.paciente)
        self.assertEqual(atencion.profesional, self.medico)
        self.assertEqual(atencion.tipo_atencion, 'Neurología infantil')
        ficha = self.client.get(reverse('pacientes:detalle', args=[self.paciente.pk]))
        self.assertContains(ficha, 'Control de seguimiento')
        self.assertContains(ficha, 'Epilepsia focal en seguimiento')

    def test_medico_asignado_agrega_diagnostico_y_lo_ve_en_ficha(self):
        self.client.force_login(self.medico)
        respuesta = self.client.post(
            reverse('pacientes:crear_diagnostico', args=[self.paciente.pk]),
            {
                'descripcion': 'Trastorno del neurodesarrollo',
                'codigo_cie10': 'F84.0',
                'fecha_diagnostico': date.today().isoformat(),
                'estado': Diagnostico.Estado.ACTIVO,
                'notas': 'Seguimiento clínico',
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        ficha = self.client.get(reverse('pacientes:detalle', args=[self.paciente.pk]))
        self.assertContains(ficha, 'Trastorno del neurodesarrollo')

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


class RecuperacionContrasenaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(
            username='usuario_recuperacion',
            email='recuperacion@example.test',
            password='Clave-inicial-123',
            is_active=True,
        )

    def test_correo_es_obligatorio_y_unico_al_crear_usuarios(self):
        form_sin_correo = UsuarioCreationForm(data={
            'username': 'sin_correo',
            'password1': 'Clave-segura-456',
            'password2': 'Clave-segura-456',
        })
        self.assertFalse(form_sin_correo.is_valid())
        self.assertIn('email', form_sin_correo.errors)

        form_correo_repetido = UsuarioCreationForm(data={
            'username': 'correo_repetido',
            'email': 'RECUPERACION@example.test',
            'password1': 'Clave-segura-456',
            'password2': 'Clave-segura-456',
        })
        self.assertFalse(form_correo_repetido.is_valid())
        self.assertIn('email', form_correo_repetido.errors)

    def test_pagina_admin_para_agregar_usuario_carga(self):
        administrador = Usuario.objects.create_superuser(
            username='admin_alta_test',
            email='admin_alta@example.test',
            password='Clave-admin-123',
        )
        self.client.force_login(administrador)

        respuesta = self.client.get(reverse('admin:usuarios_usuario_add'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Correo electrónico')
        self.assertContains(respuesta, 'usable_password')

        respuesta = self.client.post(reverse('admin:usuarios_usuario_add'), {
            'username': 'medico_nuevo_admin',
            'usable_password': 'true',
            'password1': 'Clave-segura-Admin-987',
            'password2': 'Clave-segura-Admin-987',
            'first_name': 'Medico',
            'last_name': 'Nuevo',
            'email': 'medico_nuevo@example.test',
            'rut': '12345678-5',
            'telefono': '+56 9 1234 5678',
            'profesion': 'Psicóloga',
            'rol': Usuario.Rol.MEDICO,
        }, follow=True)

        self.assertEqual(respuesta.status_code, 200)
        creado = Usuario.objects.get(username='medico_nuevo_admin')
        self.assertEqual(creado.email, 'medico_nuevo@example.test')
        self.assertTrue(creado.check_password('Clave-segura-Admin-987'))

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='NeuroFicha <no-reply@example.test>',
    )
    def test_solicitud_envia_enlace_de_un_solo_uso(self):
        respuesta = self.client.post(reverse('password_reset'), {
            'email': self.usuario.email,
        })

        self.assertRedirects(respuesta, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.usuario.email])
        enlace = re.search(r'https?://[^\s]+/reset/[^\s]+', mail.outbox[0].body)
        self.assertIsNotNone(enlace)

        confirmacion = self.client.get(enlace.group(0))
        self.assertEqual(confirmacion.status_code, 302)
        url_confirmacion = confirmacion.url
        pagina = self.client.get(url_confirmacion)
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Crear una contraseña nueva')

        respuesta = self.client.post(url_confirmacion, {
            'new_password1': 'Otra-Clave-segura-789',
            'new_password2': 'Otra-Clave-segura-789',
        })
        self.assertRedirects(respuesta, reverse('password_reset_complete'))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('Otra-Clave-segura-789'))


class PoliticaContrasenasTest(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='historial_claves',
            email='historial@example.test',
            password='Inicio-Seguro-000!',
        )

    def test_exige_complejidad_y_no_reutiliza_las_ultimas_cinco(self):
        for debil in (
            'corta',
            'sin-mayuscula-123!',
            'SinNumero-Clave!',
            'SinCaracterEspecial123',
        ):
            with self.subTest(contrasena=debil), self.assertRaises(ValidationError):
                validate_password(debil, self.usuario)

        for indice in range(1, 6):
            nueva = f'Fuerte-Clave-{indice:03d}!'
            validate_password(nueva, self.usuario)
            self.usuario.set_password(nueva)
            self.usuario.save(update_fields=['password'])

        with self.assertRaises(ValidationError):
            validate_password('Fuerte-Clave-001!', self.usuario)
        # La clave inicial es la sexta hacia atrás y queda fuera de la ventana.
        validate_password('Inicio-Seguro-000!', self.usuario)


class CargaPacientesDemoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.medicos = [
            Usuario.objects.create_user(
                username=f'medico_demo_{i}',
                email=f'medico{i}@example.test',
                password='Clave-de-prueba-123',
                rol=Usuario.Rol.MEDICO,
            )
            for i in (1, 2)
        ]

    @override_settings(DEBUG=True)
    def test_carga_veinte_fichas_completas_y_es_idempotente(self):
        call_command('cargar_pacientes_demo', stdout=StringIO())

        self.assertEqual(Paciente.objects.count(), 20)
        self.assertEqual(Tutor.objects.count(), 20)
        self.assertEqual(AntecedentesNeurologicos.objects.count(), 20)
        self.assertEqual(Diagnostico.objects.count(), 20)
        self.assertEqual(AsignacionProfesional.objects.count(), 20)
        self.assertEqual(
            AsignacionProfesional.objects.values('profesional_id').distinct().count(),
            2,
        )
        self.assertTrue(
            all(paciente.edad >= 0 for paciente in Paciente.objects.all())
        )
        self.assertTrue(
            all(paciente.tutores.filter(email__endswith='@ejemplo.test').exists()
                for paciente in Paciente.objects.all())
        )

        call_command('cargar_pacientes_demo', stdout=StringIO())
        self.assertEqual(Paciente.objects.count(), 20)
