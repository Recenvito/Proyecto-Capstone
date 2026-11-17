"""Pruebas de extremo a extremo del navegador con evidencia PNG por caso.

Ejecutar con (ver docs/Fase 2/Plan de Pruebas Selenium.md):
  python manage.py test tests_e2e --settings=config.settings_selenium_browser

Cada caso usa un identificador P-xxx y guarda su captura en
docs/Fase 2/Evidencias Selenium/<SELENIUM_CICLO> (por ejemplo, SELENIUM_CICLO=Ciclo 3)
o en SELENIUM_EVIDENCE_DIR. Sin ninguna de las dos, las capturas van a
tmp/selenium/evidencias, para no sobrescribir la evidencia de un ciclo ya cerrado.
"""

import os
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlencode

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls import reverse
from django.utils import timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

from agenda.models import Cita, Disponibilidad, TarifaServicio
from pacientes.models import AsignacionProfesional, Paciente, Tutor
from usuarios.models import Usuario


class FlujosSeleniumTest(StaticLiveServerTestCase):
    """Casos críticos de interfaz con identidad y datos totalmente ficticios."""

    def _crear_datos_ficticios(self):
        self.admin = Usuario.objects.create_user(
            username='admin_selenium', password='Prueba-Segura-2026!',
            rol=Usuario.Rol.ADMIN, is_staff=True, is_superuser=True,
        )
        self.medico = Usuario.objects.create_user(
            username='medico_selenium', password='Prueba-Segura-2026!',
            first_name='Médico', last_name='Prueba', rol=Usuario.Rol.MEDICO,
        )
        self.medico_ajeno = Usuario.objects.create_user(
            username='medico_ajeno_selenium', password='Prueba-Segura-2026!',
            first_name='Otro', last_name='Médico', rol=Usuario.Rol.MEDICO,
        )
        self.secretaria = Usuario.objects.create_user(
            username='secretaria_selenium', password='Prueba-Segura-2026!',
            rol=Usuario.Rol.SECRETARIA,
        )
        self.tutor = Usuario.objects.create_user(
            username='tutor_selenium', password='Prueba-Segura-2026!',
            first_name='Tutor', last_name='Ficticio', email='tutor.selenium@example.test',
            rut='11111111-1', telefono='+56911112222', rol=Usuario.Rol.TUTOR,
            correo_verificado=True, telefono_verificado=True,
        )
        self.otro_tutor = Usuario.objects.create_user(
            username='otro_tutor_selenium', password='Prueba-Segura-2026!',
            first_name='Otro', last_name='Tutor', email='otro.selenium@example.test',
            rut='33333333-3', telefono='+56933334444', rol=Usuario.Rol.TUTOR,
            correo_verificado=True, telefono_verificado=True,
        )
        self.paciente = Paciente.objects.create(
            rut='22222222-2', nombres='Paciente', apellido_paterno='Selenium',
            apellido_materno='Ficticio', fecha_nacimiento=date(2018, 3, 12),
            sexo=Paciente.Sexo.FEMENINO,
        )
        self.paciente_ajeno = Paciente.objects.create(
            rut='44444444-4', nombres='Ficha', apellido_paterno='NoAutorizada',
            fecha_nacimiento=date(2017, 4, 10), sexo=Paciente.Sexo.MASCULINO,
        )
        AsignacionProfesional.objects.create(
            paciente=self.paciente, profesional=self.medico, activa=True,
        )
        Tutor.objects.create(
            paciente=self.paciente, usuario=self.tutor, rut=self.tutor.rut,
            nombre_completo='Tutor Ficticio', parentesco=Tutor.Parentesco.MADRE,
            telefono=self.tutor.telefono, email=self.tutor.email,
        )
        Tutor.objects.create(
            paciente=self.paciente_ajeno, usuario=self.otro_tutor, rut=self.otro_tutor.rut,
            nombre_completo='Otro Tutor', parentesco=Tutor.Parentesco.PADRE,
            telefono=self.otro_tutor.telefono, email=self.otro_tutor.email,
        )
        self.fecha_reserva = timezone.localdate() + timedelta(days=14)
        Disponibilidad.objects.create(
            profesional=self.medico, dia_semana=self.fecha_reserva.weekday(),
            hora_inicio=time(9, 0), hora_fin=time(11, 0),
            duracion_cita_minutos=30, lugar='Consulta de prueba',
        )
        TarifaServicio.objects.create(tipo=Cita.Tipo.CONTROL, monto_clp=25000)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = webdriver.ChromeOptions()
        if os.environ.get('SELENIUM_HEADLESS', '1') == '1':
            options.add_argument('--headless=new')
        options.add_argument('--window-size=1440,1000')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        browser = os.environ.get('SELENIUM_BROWSER', 'chrome').strip().lower()
        if browser == 'edge':
            edge_options = webdriver.EdgeOptions()
            if os.environ.get('SELENIUM_HEADLESS', '1') == '1':
                edge_options.add_argument('--headless=new')
            edge_options.add_argument('--window-size=1440,1000')
            edge_options.add_argument('--disable-gpu')
            cls.driver = webdriver.Edge(options=edge_options)
        elif browser == 'chrome':
            cls.driver = webdriver.Chrome(options=options)
        else:
            raise ValueError('SELENIUM_BROWSER debe ser chrome o edge.')
        cls.driver.implicitly_wait(2)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'driver', None):
            cls.driver.quit()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self._crear_datos_ficticios()
        self.driver.delete_all_cookies()
        self.case_id = f"P-{self._testMethodName.split('_', 2)[1][1:]}"

    def tearDown(self):
        driver = getattr(self, 'driver', None)
        if not driver:
            return
        project_dir = Path(__file__).resolve().parents[1]
        cycle = os.environ.get('SELENIUM_CICLO', '').strip()
        if os.environ.get('SELENIUM_EVIDENCE_DIR'):
            evidence_dir = Path(os.environ['SELENIUM_EVIDENCE_DIR'])
        elif cycle:
            evidence_dir = project_dir / 'docs' / 'Fase 2' / 'Evidencias Selenium' / cycle
        else:
            evidence_dir = project_dir / 'tmp' / 'selenium' / 'evidencias'
        evidence_dir.mkdir(parents=True, exist_ok=True)
        result = 'OK'
        outcome = getattr(getattr(self, '_outcome', None), 'result', None)
        if outcome:
            if any(test is self for test, _ in outcome.failures):
                result = 'FALLO'
            elif any(test is self for test, _ in outcome.errors):
                result = 'ERROR'
        name = re.sub(r'[^A-Za-z0-9_-]+', '_', f'{self.case_id}_{result}')
        driver.save_screenshot(str(evidence_dir / f'{name}.png'))

    def _login(self, usuario, password='Prueba-Segura-2026!'):
        self.driver.get(f'{self.live_server_url}{reverse("login")}')
        self.driver.find_element(By.ID, 'id_username').send_keys(usuario)
        self.driver.find_element(By.ID, 'id_password').send_keys(password)
        self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        WebDriverWait(self.driver, 8).until(lambda driver: '/login/' not in driver.current_url)

    @tag('selenium', 'P-001')
    def test_P001_inicio_publico_y_acceso_a_login(self):
        self.driver.get(self.live_server_url)
        self.assertIn('NEA Enlaces', self.driver.title)
        self.assertTrue(self.driver.find_elements(By.LINK_TEXT, 'Iniciar sesión'))

    @tag('selenium', 'P-002')
    def test_P002_credenciales_invalidas_muestran_error(self):
        self.driver.get(f'{self.live_server_url}{reverse("login")}')
        self.driver.find_element(By.ID, 'id_username').send_keys('usuario_inexistente')
        self.driver.find_element(By.ID, 'id_password').send_keys('incorrecta')
        self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        WebDriverWait(self.driver, 5).until(
            lambda driver: driver.find_elements(By.CSS_SELECTOR, '[role="alert"]'),
        )
        self.assertIn('incorrectos', self.driver.find_element(By.CSS_SELECTOR, '[role="alert"]').text)

    @tag('selenium', 'P-003')
    def test_P003_administrador_busca_paciente_ficticio(self):
        self._login(self.admin.username)
        self.driver.get(f'{self.live_server_url}{reverse("pacientes:lista")}?q=Selenium')
        self.assertIn('Paciente Selenium Ficticio', self.driver.page_source)
        self.assertIn('Ver ficha', self.driver.page_source)

    @tag('selenium', 'P-004')
    def test_P004_medico_asignado_consulta_ficha_clinica(self):
        self._login(self.medico.username)
        self.driver.get(f'{self.live_server_url}{reverse("pacientes:detalle", args=[self.paciente.pk])}')
        self.assertIn('Paciente Selenium Ficticio', self.driver.page_source)
        self.assertIn('Registrar atencion', self.driver.page_source)

    @tag('selenium', 'P-005')
    def test_P005_medico_no_asignado_recibe_denegacion(self):
        self._login(self.medico_ajeno.username)
        self.driver.get(f'{self.live_server_url}{reverse("pacientes:detalle", args=[self.paciente.pk])}')
        self.assertIn('Acceso no autorizado', self.driver.page_source)
        self.assertIn('No tienes acceso', self.driver.page_source)

    @tag('selenium', 'P-006')
    def test_P006_secretaria_no_ve_controles_clinicos(self):
        self._login(self.secretaria.username)
        self.driver.get(f'{self.live_server_url}{reverse("pacientes:detalle", args=[self.paciente.pk])}')
        self.assertIn('Datos del paciente', self.driver.page_source)
        self.assertNotIn('Registrar atencion', self.driver.page_source)
        self.assertNotIn('Antecedentes neurologicos', self.driver.page_source)

    @tag('selenium', 'P-007')
    def test_P007_tutor_ve_solo_paciente_vinculado(self):
        self._login(self.tutor.username)
        self.assertIn('Paciente Selenium Ficticio', self.driver.page_source)
        self.assertNotIn('Ficha NoAutorizada', self.driver.page_source)
        self.assertTrue(self.driver.find_elements(By.LINK_TEXT, 'Reservar una hora'))

    @tag('selenium', 'P-008')
    def test_P008_tutor_consulta_horarios_y_tarifa(self):
        self._login(self.tutor.username)
        query = urlencode({
            'paciente': self.paciente.pk, 'profesional': self.medico.pk,
            'fecha': self.fecha_reserva.isoformat(), 'tipo': Cita.Tipo.CONTROL,
        })
        self.driver.get(f'{self.live_server_url}{reverse("portal:reservar")}?{query}')
        self.assertIn('Horarios disponibles', self.driver.page_source)
        self.assertIn('$25000 CLP', self.driver.page_source)
        self.assertTrue(self.driver.find_elements(By.CSS_SELECTOR, 'button[name="hora"]'))

    @tag('selenium', 'P-009')
    def test_P009_tutor_reserva_hora_y_la_cita_se_registra(self):
        self._login(self.tutor.username)
        query = urlencode({
            'paciente': self.paciente.pk, 'profesional': self.medico.pk,
            'fecha': self.fecha_reserva.isoformat(), 'tipo': Cita.Tipo.CONTROL,
        })
        self.driver.get(f'{self.live_server_url}{reverse("portal:reservar")}?{query}')
        Select(self.driver.find_element(By.ID, 'id_forma_pago')).select_by_value('PRESENCIAL')
        self.driver.find_element(By.CSS_SELECTOR, 'button[name="hora"]').click()
        WebDriverWait(self.driver, 8).until(
            lambda driver: reverse('portal:inicio') in driver.current_url,
        )
        # Rango en vez de fecha_hora__date: ese filtro falla en MySQL sin tablas de zona horaria.
        inicio_dia = timezone.make_aware(datetime.combine(self.fecha_reserva, time.min))
        self.assertTrue(Cita.objects.filter(
            paciente=self.paciente, profesional=self.medico,
            fecha_hora__gte=inicio_dia, fecha_hora__lt=inicio_dia + timedelta(days=1),
        ).exists())

    @tag('selenium', 'P-010')
    def test_P010_tutor_no_accede_a_modulos_clinicos(self):
        self._login(self.tutor.username)
        self.driver.get(f'{self.live_server_url}{reverse("pacientes:lista")}')
        self.assertIn('Acceso no autorizado', self.driver.page_source)
        self.assertNotIn('Ficha clínica', self.driver.page_source)
