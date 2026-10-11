from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from agenda.models import Cita, Disponibilidad, PagoCita, TarifaServicio
from pacientes.models import DocumentoPaciente, Paciente, SolicitudAccesoTutor, Tutor
from usuarios.models import Auditoria
from .models import VerificacionCorreo

Usuario = get_user_model()


class PortalTutorTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tutor = Usuario.objects.create_user(
            username='tutor_demo_portal', password='Frase-Segura-987!',
            first_name='Tutor', last_name='Prueba', email='tutor@example.test',
            rut='11111111-1', telefono='+56912345678', rol=Usuario.Rol.TUTOR,
            correo_verificado=True, telefono_verificado=True,
        )
        cls.paciente = Paciente.objects.create(
            rut='22222222-2', nombres='Paciente', apellido_paterno='Ficticio',
            fecha_nacimiento=date(2018, 3, 12), sexo=Paciente.Sexo.FEMENINO,
        )
        Tutor.objects.create(
            paciente=cls.paciente, usuario=cls.tutor, rut=cls.tutor.rut,
            nombre_completo='Tutor Prueba', parentesco=Tutor.Parentesco.MADRE,
            telefono=cls.tutor.telefono, email=cls.tutor.email,
        )
        cls.medico = Usuario.objects.create_user(
            username='medico_demo_portal', password='Frase-Segura-987!',
            first_name='Profesional', last_name='Ficticio', rol=Usuario.Rol.MEDICO,
        )

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_registro_envia_verificacion_y_no_revela_si_ficha_existe(self):
        respuesta = self.client.post(reverse('portal:registro'), {
            'rut_tutor': '33.333.333-3', 'nombres': 'Ana', 'apellidos': 'Ejemplo',
            'email': 'ana@example.test', 'telefono': '+56 9 2222 3333',
            'rut_paciente': '22.222.222-2', 'parentesco': Tutor.Parentesco.MADRE,
            'password1': 'Clave-Muy-Segura-987!', 'password2': 'Clave-Muy-Segura-987!',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        solicitud = SolicitudAccesoTutor.objects.get(usuario__email='ana@example.test')
        self.assertEqual(solicitud.estado, SolicitudAccesoTutor.Estado.PENDIENTE)
        self.assertFalse(solicitud.usuario.is_active)
        self.assertNotContains(respuesta, self.paciente.nombre_completo)

    def test_token_de_correo_es_de_un_solo_uso_y_habilita_solo_portal(self):
        usuario = Usuario.objects.create_user(
            username='tutor_verificacion', email='verifica@example.test',
            password='Clave-Muy-Segura-987!', rol=Usuario.Rol.TUTOR, is_active=False,
        )
        token, digest = VerificacionCorreo.generar_token()
        VerificacionCorreo.objects.create(
            usuario=usuario, token_hash=digest, expira_en=timezone.now() + timedelta(hours=1),
        )
        respuesta = self.client.get(reverse('portal:verificar_correo', args=[token]))
        self.assertEqual(respuesta.status_code, 200)
        respuesta = self.client.post(reverse('portal:verificar_correo', args=[token]))
        self.assertRedirects(respuesta, reverse('login'))
        usuario.refresh_from_db()
        self.assertTrue(usuario.is_active)
        self.assertTrue(usuario.correo_verificado)
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse('portal:inicio')).status_code, 200)
        self.assertEqual(self.client.get(reverse('pacientes:lista')).status_code, 403)
        self.assertEqual(self.client.get(reverse('agenda:calendario')).status_code, 403)
        self.assertEqual(self.client.get(reverse('inicio')).status_code, 403)
        self.assertEqual(self.client.get('/admin/').status_code, 403)
        self.assertEqual(self.client.get('/media/informes/paciente_1/ejemplo.pdf').status_code, 403)

    def test_login_de_tutor_lo_envia_al_portal(self):
        respuesta = self.client.post(reverse('login'), {
            'username': self.tutor.username, 'password': 'Frase-Segura-987!',
        })
        self.assertRedirects(respuesta, reverse('portal:inicio'), fetch_redirect_response=False)

    def test_cambio_de_telefono_requiere_verificacion_antes_de_mostrar_fichas(self):
        self.client.force_login(self.tutor)
        respuesta = self.client.post(reverse('editar_perfil'), {
            'first_name': self.tutor.first_name, 'last_name': self.tutor.last_name,
            'email': self.tutor.email, 'rut': self.tutor.rut,
            'telefono': '+56 9 5555 6666', 'profesion': '', 'especialidad': '',
            'registro_superintendencia': '',
        })
        self.assertRedirects(respuesta, reverse('editar_perfil'))
        self.tutor.refresh_from_db()
        self.assertEqual(self.tutor.telefono, '+56955556666')
        mensajes = list(respuesta.wsgi_request._messages)
        self.assertFalse(self.tutor.telefono_verificado, f'mensajes={mensajes}')
        portal = self.client.get(reverse('portal:inicio'))
        self.assertNotContains(portal, self.paciente.nombre_completo)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_cambio_de_correo_desactiva_sesion_hasta_verificar_el_nuevo(self):
        self.client.force_login(self.tutor)
        respuesta = self.client.post(reverse('editar_perfil'), {
            'first_name': self.tutor.first_name, 'last_name': self.tutor.last_name,
            'email': 'tutor.nuevo@example.test', 'rut': self.tutor.rut,
            'telefono': self.tutor.telefono, 'profesion': '', 'especialidad': '',
            'registro_superintendencia': '',
        })
        self.assertRedirects(respuesta, reverse('editar_perfil'), fetch_redirect_response=False)
        self.tutor.refresh_from_db()
        self.assertFalse(self.tutor.is_active)
        self.assertFalse(self.tutor.correo_verificado)
        self.assertEqual(len(mail.outbox), 1)

    def test_tutor_verificado_puede_solicitar_vinculo_adicional_sin_consultar_el_rut(self):
        self.client.force_login(self.tutor)
        respuesta = self.client.post(reverse('portal:solicitar_vinculo'), {
            'rut_paciente': '44.444.444-4', 'parentesco': Tutor.Parentesco.PADRE,
        })
        self.assertRedirects(respuesta, reverse('portal:inicio'))
        solicitud = SolicitudAccesoTutor.objects.get(usuario=self.tutor, paciente_rut='44444444-4')
        self.assertEqual(solicitud.estado, SolicitudAccesoTutor.Estado.PENDIENTE)
        self.assertFalse(Tutor.objects.filter(usuario=self.tutor, paciente__rut='44444444-4').exists())

    def _preparar_horario(self, fecha, inicio=time(10, 0)):
        Disponibilidad.objects.create(
            profesional=self.medico, dia_semana=fecha.weekday(),
            hora_inicio=inicio, hora_fin=time(inicio.hour + 1, inicio.minute),
            duracion_cita_minutos=30, lugar='Consulta ficticia',
        )
        TarifaServicio.objects.create(tipo=Cita.Tipo.CONTROL, monto_clp=25000)
        return timezone.make_aware(datetime.combine(fecha, inicio), timezone.get_current_timezone())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reserva_presencial_crea_cita_en_agenda_clinica_y_envia_comprobante(self):
        fecha = timezone.localdate() + timedelta(days=14)
        fecha_hora = self._preparar_horario(fecha)
        self.client.force_login(self.tutor)
        respuesta = self.client.post(reverse('portal:reservar'), {
            'paciente': self.paciente.pk, 'profesional': self.medico.pk,
            'fecha': fecha.isoformat(), 'hora': fecha_hora.strftime('%Y-%m-%dT%H:%M'),
            'tipo': Cita.Tipo.CONTROL, 'forma_pago': 'PRESENCIAL', 'motivo': 'Control',
        })
        self.assertRedirects(respuesta, reverse('portal:inicio'))
        cita = Cita.objects.get(paciente=self.paciente, profesional=self.medico)
        self.assertEqual(cita.estado, Cita.Estado.AGENDADA)
        self.assertEqual(cita.pago.estado, PagoCita.Estado.POR_PAGAR)
        self.assertEqual(cita.pago.monto_clp, 25000)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.tutor.email])
        self.assertIn('Comprobante de reserva', mail.outbox[0].subject)
        self.assertIn('Paciente Ficticio', mail.outbox[0].body)
        self.assertTrue(self.paciente.asignaciones_profesionales.filter(profesional=self.medico, activa=True).exists())
        self.client.force_login(self.medico)
        agenda = self.client.get(reverse('agenda:calendario'), {'fecha': fecha.isoformat()})
        self.assertContains(agenda, self.paciente.nombre_completo)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reserva_webpay_solo_confirma_tras_commit_autorizado_y_envia_comprobantes(self):
        fecha = timezone.localdate() + timedelta(days=14)
        fecha_hora = self._preparar_horario(fecha)
        self.client.force_login(self.tutor)
        cliente = type('ClienteWebpayFalso', (), {
            'create': lambda _self, orden, sesion, monto, retorno: {
                'token': 'token-prueba-no-real', 'url': 'https://webpay.example.test',
            },
            'commit': lambda _self, token: {
                'status': 'AUTHORIZED', 'response_code': 0, 'amount': 25000,
                'buy_order': PagoCita.objects.get(token_transbank=token).orden_compra,
                'authorization_code': '123456',
            },
        })()
        with patch('portal.views._transbank_transaction', return_value=cliente):
            inicio = self.client.post(reverse('portal:reservar'), {
                'paciente': self.paciente.pk, 'profesional': self.medico.pk,
                'fecha': fecha.isoformat(), 'hora': fecha_hora.strftime('%Y-%m-%dT%H:%M'),
                'tipo': Cita.Tipo.CONTROL, 'forma_pago': 'WEBPAY', 'motivo': 'Consulta',
            })
            self.assertEqual(inicio.status_code, 200)
            pago = PagoCita.objects.get(token_transbank='token-prueba-no-real')
            self.assertEqual(pago.cita.estado, Cita.Estado.AGENDADA)
            retorno = self.client.get(reverse('portal:webpay_retorno'), {'token_ws': pago.token_transbank})
        self.assertRedirects(retorno, reverse('portal:inicio'))
        pago.refresh_from_db()
        pago.cita.refresh_from_db()
        self.assertEqual(pago.estado, PagoCita.Estado.PAGADA)
        self.assertEqual(pago.cita.estado, Cita.Estado.CONFIRMADA)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('Comprobante de reserva', mail.outbox[0].subject)
        self.assertIn('Comprobante de pago', mail.outbox[1].subject)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_tutor_puede_pagar_por_webpay_una_reserva_presencial_pendiente(self):
        fecha = timezone.localdate() + timedelta(days=14)
        fecha_hora = self._preparar_horario(fecha)
        cita = Cita.objects.create(
            paciente=self.paciente, profesional=self.medico, fecha_hora=fecha_hora,
            tipo=Cita.Tipo.CONTROL, creada_por=self.tutor,
        )
        pago = PagoCita.objects.create(
            cita=cita, tutor=self.tutor, metodo=PagoCita.Metodo.PRESENCIAL,
            estado=PagoCita.Estado.POR_PAGAR, monto_clp=25000,
        )
        cliente = type('ClienteWebpayFalso', (), {
            'create': lambda _self, orden, sesion, monto, retorno: {
                'token': 'token-reintento-prueba', 'url': 'https://webpay.example.test',
            },
            'commit': lambda _self, token: {
                'status': 'AUTHORIZED', 'response_code': 0, 'amount': 25000,
                'buy_order': PagoCita.objects.get(token_transbank=token).orden_compra,
                'authorization_code': '123456',
            },
        })()
        self.client.force_login(self.tutor)
        with patch('portal.views._transbank_transaction', return_value=cliente):
            inicio = self.client.post(reverse('portal:pagar_cita_webpay', args=[cita.pk]))
            self.assertEqual(inicio.status_code, 200)
            pago.refresh_from_db()
            self.assertEqual(pago.estado, PagoCita.Estado.INICIADA)
            self.assertTrue(pago.reintento_presencial)
            respuesta = self.client.get(
                reverse('portal:webpay_retorno'), {'token_ws': pago.token_transbank},
            )
        self.assertRedirects(respuesta, reverse('portal:inicio'))
        pago.refresh_from_db()
        cita.refresh_from_db()
        self.assertEqual(pago.estado, PagoCita.Estado.PAGADA)
        self.assertFalse(pago.reintento_presencial)
        self.assertEqual(cita.estado, Cita.Estado.CONFIRMADA)
        self.assertEqual(len(mail.outbox), 2)

    def test_pago_webpay_posterior_rechazado_conserva_la_reserva_para_pago_en_clinica(self):
        fecha = timezone.localdate() + timedelta(days=14)
        fecha_hora = self._preparar_horario(fecha)
        cita = Cita.objects.create(
            paciente=self.paciente, profesional=self.medico, fecha_hora=fecha_hora,
            tipo=Cita.Tipo.CONTROL, creada_por=self.tutor,
        )
        pago = PagoCita.objects.create(
            cita=cita, tutor=self.tutor, metodo=PagoCita.Metodo.PRESENCIAL,
            estado=PagoCita.Estado.POR_PAGAR, monto_clp=25000,
        )
        cliente = type('ClienteWebpayRechazado', (), {
            'create': lambda _self, orden, sesion, monto, retorno: {
                'token': 'token-rechazado-prueba', 'url': 'https://webpay.example.test',
            },
            'commit': lambda _self, token: {
                'status': 'FAILED', 'response_code': 1, 'amount': 25000,
                'buy_order': pago.orden_compra,
            },
        })()
        self.client.force_login(self.tutor)
        with patch('portal.views._transbank_transaction', return_value=cliente):
            self.client.post(reverse('portal:pagar_cita_webpay', args=[cita.pk]))
            pago.refresh_from_db()
            self.client.get(reverse('portal:webpay_retorno'), {'token_ws': pago.token_transbank})
        pago.refresh_from_db()
        cita.refresh_from_db()
        self.assertEqual(pago.metodo, PagoCita.Metodo.PRESENCIAL)
        self.assertEqual(pago.estado, PagoCita.Estado.POR_PAGAR)
        self.assertFalse(pago.reintento_presencial)
        self.assertEqual(cita.estado, Cita.Estado.AGENDADA)

    def test_cancelar_webpay_de_pago_posterior_conserva_la_reserva(self):
        fecha = timezone.localdate() + timedelta(days=14)
        fecha_hora = self._preparar_horario(fecha)
        cita = Cita.objects.create(
            paciente=self.paciente, profesional=self.medico, fecha_hora=fecha_hora,
            tipo=Cita.Tipo.CONTROL, creada_por=self.tutor,
        )
        pago = PagoCita.objects.create(
            cita=cita, tutor=self.tutor, metodo=PagoCita.Metodo.PRESENCIAL,
            estado=PagoCita.Estado.POR_PAGAR, monto_clp=25000,
        )
        cliente = type('ClienteWebpayCancelado', (), {
            'create': lambda _self, orden, sesion, monto, retorno: {
                'token': 'token-cancelado-prueba', 'url': 'https://webpay.example.test',
            },
        })()
        self.client.force_login(self.tutor)
        with patch('portal.views._transbank_transaction', return_value=cliente):
            self.client.post(reverse('portal:pagar_cita_webpay', args=[cita.pk]))
            respuesta = self.client.get(
                reverse('portal:webpay_retorno'), {'TBK_TOKEN': 'token-cancelado-prueba'},
            )
        self.assertRedirects(respuesta, reverse('portal:inicio'))
        pago.refresh_from_db()
        cita.refresh_from_db()
        self.assertEqual(pago.metodo, PagoCita.Metodo.PRESENCIAL)
        self.assertEqual(pago.estado, PagoCita.Estado.POR_PAGAR)
        self.assertEqual(cita.estado, Cita.Estado.AGENDADA)

    def test_intento_webpay_vencido_retorna_a_pago_presencial_sin_liberar_hora(self):
        fecha = timezone.localdate() + timedelta(days=14)
        fecha_hora = self._preparar_horario(fecha)
        cita = Cita.objects.create(
            paciente=self.paciente, profesional=self.medico, fecha_hora=fecha_hora,
            tipo=Cita.Tipo.CONTROL, creada_por=self.tutor,
        )
        pago = PagoCita.objects.create(
            cita=cita, tutor=self.tutor, metodo=PagoCita.Metodo.WEBPAY,
            estado=PagoCita.Estado.INICIADA, monto_clp=25000,
            token_transbank='token-vencido-reintento',
            expira_en=timezone.now() - timedelta(minutes=1), reintento_presencial=True,
        )
        cliente = type('EstadoWebpayInicializado', (), {
            'status': lambda _self, token: {'status': 'INITIALIZED'},
        })()
        with patch('portal.views._transbank_transaction', return_value=cliente):
            from portal.views import _liberar_reservas_vencidas
            _liberar_reservas_vencidas()
        pago.refresh_from_db()
        cita.refresh_from_db()
        self.assertEqual(pago.metodo, PagoCita.Metodo.PRESENCIAL)
        self.assertEqual(pago.estado, PagoCita.Estado.POR_PAGAR)
        self.assertEqual(cita.estado, Cita.Estado.AGENDADA)

    def test_informe_publicado_solo_se_descarga_por_tutor_autorizado_y_se_audita(self):
        informe = DocumentoPaciente.objects.create(
            paciente=self.paciente, titulo='Informe ficticio de prueba',
            descripcion='Documento de demostración, sin datos clínicos reales.',
            archivo=SimpleUploadedFile(
                'informe-prueba.pdf', b'%PDF-1.4\nDocumento ficticio de prueba\n%%EOF',
                content_type='application/pdf',
            ),
            publicado=True, subido_por=self.medico,
        )
        self.addCleanup(informe.archivo.delete, save=False)
        self.client.force_login(self.tutor)
        portal = self.client.get(reverse('portal:inicio'))
        self.assertContains(portal, informe.titulo)
        respuesta = self.client.get(reverse('portal:descargar_documento', args=[informe.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('attachment;', respuesta['Content-Disposition'])
        self.assertEqual(b''.join(respuesta.streaming_content), b'%PDF-1.4\nDocumento ficticio de prueba\n%%EOF')
        self.assertTrue(Auditoria.objects.filter(
            usuario=self.tutor, modelo='Documento clínico del portal', registro_id=informe.pk,
        ).exists())

    def test_documento_no_publicado_o_de_otra_ficha_no_se_entrega(self):
        informe = DocumentoPaciente.objects.create(
            paciente=self.paciente, titulo='Borrador ficticio',
            archivo=SimpleUploadedFile('borrador.pdf', b'%PDF-1.4\nBorrador\n%%EOF'),
            publicado=False,
        )
        self.addCleanup(informe.archivo.delete, save=False)
        otro_tutor = Usuario.objects.create_user(
            username='tutor_sin_acceso_informe', password='Frase-Segura-987!',
            email='otro@example.test', rol=Usuario.Rol.TUTOR,
            correo_verificado=True, telefono_verificado=True,
        )
        self.client.force_login(otro_tutor)
        self.assertEqual(
            self.client.get(reverse('portal:descargar_documento', args=[informe.pk])).status_code,
            404,
        )

    def test_reconcilia_pago_autorizado_antes_de_liberar_reserva_vencida(self):
        fecha = timezone.localdate() + timedelta(days=14)
        fecha_hora = self._preparar_horario(fecha)
        cita = Cita.objects.create(
            paciente=self.paciente, profesional=self.medico, fecha_hora=fecha_hora,
            tipo=Cita.Tipo.CONTROL, creada_por=self.tutor,
        )
        asignacion, _ = self.paciente.asignaciones_profesionales.get_or_create(
            profesional=self.medico, defaults={'activa': True},
        )
        pago = PagoCita.objects.create(
            cita=cita, tutor=self.tutor, metodo=PagoCita.Metodo.WEBPAY,
            estado=PagoCita.Estado.INICIADA, monto_clp=25000,
            token_transbank='token-expirado-prueba', expira_en=timezone.now() - timedelta(minutes=1),
            asignacion_vinculo_creado=True,
        )
        respuesta = {
            'status': 'AUTHORIZED', 'response_code': 0, 'amount': 25000,
            'buy_order': pago.orden_compra, 'authorization_code': '654321',
        }
        cliente = type('EstadoWebpayFalso', (), {'status': lambda _self, token: respuesta})()
        with patch('portal.views._transbank_transaction', return_value=cliente):
            self.client.force_login(self.tutor)
            self.client.get(reverse('portal:inicio'))
        pago.refresh_from_db()
        cita.refresh_from_db()
        self.assertEqual(pago.estado, PagoCita.Estado.PAGADA)
        self.assertEqual(cita.estado, Cita.Estado.CONFIRMADA)
        self.assertTrue(asignacion.activa)


    def test_visitante_recibe_portada_con_accesos_para_nuevos_y_recurrentes(self):
        respuesta = self.client.get(reverse('home'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'landing.html')
        self.assertContains(respuesta, reverse('portal:registro'))
        self.assertContains(respuesta, reverse('login'))
        self.assertContains(respuesta, '¿Es tu primera atención en la clínica?')

    def test_tutor_autenticado_en_portada_va_a_su_portal(self):
        tutor = Usuario.objects.create_user(
            username='landing_tutor', password='Frase-Segura-987!',
            rol=Usuario.Rol.TUTOR,
        )
        self.client.force_login(tutor)

        respuesta = self.client.get(reverse('home'))

        self.assertRedirects(respuesta, reverse('portal:inicio'))

    def test_personal_clinico_en_portada_va_al_panel_clinico(self):
        medico = Usuario.objects.create_user(
            username='landing_medico', password='Frase-Segura-987!',
            rol=Usuario.Rol.MEDICO,
        )
        self.client.force_login(medico)

        respuesta = self.client.get(reverse('home'))

        self.assertRedirects(respuesta, reverse('inicio'))

    def test_panel_clinico_conserva_proteccion_de_autenticacion(self):
        respuesta = self.client.get(reverse('inicio'))

        self.assertRedirects(
            respuesta,
            f"{reverse('login')}?next={reverse('inicio')}",
        )

    def test_inicio_de_sesion_del_personal_redirige_al_panel_movido(self):
        Usuario.objects.create_user(
            username='landing_login_medico', password='Frase-Segura-987!',
            rol=Usuario.Rol.MEDICO,
        )

        respuesta = self.client.post(reverse('login'), {
            'username': 'landing_login_medico',
            'password': 'Frase-Segura-987!',
        })

        self.assertRedirects(respuesta, reverse('inicio'))

    def test_no_se_puede_reservar_sin_vinculo_aprobado_o_sin_tarifa(self):
        usuario = Usuario.objects.create_user(
            username='tutor_sin_vinculo', password='Frase-Segura-987!',
            rol=Usuario.Rol.TUTOR,
        )
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse('portal:reservar'))
        self.assertRedirects(respuesta, reverse('portal:inicio'))
        self.assertFalse(Cita.objects.exists())

    def test_admin_solo_puede_aprobar_si_correo_y_telefono_estan_verificados(self):
        self.tutor.correo_verificado = False
        self.tutor.telefono_verificado = False
        self.tutor.save(update_fields=('correo_verificado', 'telefono_verificado'))
        paciente_solicitado = Paciente.objects.create(
            rut='44444444-4', nombres='Menor', apellido_paterno='Ficticio',
            fecha_nacimiento=date(2019, 4, 9), sexo=Paciente.Sexo.MASCULINO,
        )
        solicitud = SolicitudAccesoTutor.objects.create(
            usuario=self.tutor, paciente_rut=paciente_solicitado.rut,
            parentesco=Tutor.Parentesco.MADRE,
        )
        admin = Usuario.objects.create_superuser(
            username='admin_portal_ficticio', email='admin@example.test',
            password='Frase-Segura-987!',
        )
        self.client.force_login(admin)
        respuesta = self.client.post(
            reverse('admin:pacientes_solicitudaccesotutor_changelist'),
            {'action': 'aprobar_vinculos', '_selected_action': [solicitud.pk]},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAccesoTutor.Estado.PENDIENTE)
        self.assertFalse(Tutor.objects.filter(paciente=paciente_solicitado, usuario=self.tutor).exists())

    def test_clinica_aprueba_vinculo_tras_verificar_contactos(self):
        self.tutor.correo_verificado = True
        self.tutor.telefono_verificado = True
        self.tutor.save(update_fields=('correo_verificado', 'telefono_verificado'))
        solicitud = SolicitudAccesoTutor.objects.create(
            usuario=self.tutor, paciente_rut=self.paciente.rut,
            parentesco=Tutor.Parentesco.MADRE,
        )
        admin = Usuario.objects.create_superuser(
            username='admin_vinculo_portal', email='admin.vinculo@example.test',
            password='Frase-Segura-987!',
        )
        self.client.force_login(admin)
        respuesta = self.client.post(
            reverse('admin:pacientes_solicitudaccesotutor_changelist'),
            {'action': 'aprobar_vinculos', '_selected_action': [solicitud.pk]},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAccesoTutor.Estado.APROBADA)
        self.assertTrue(Tutor.objects.filter(paciente=self.paciente, usuario=self.tutor).exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_administracion_registra_pago_presencial_y_confirma_la_cita(self):
        fecha_hora = timezone.now() + timedelta(days=5)
        cita = Cita.objects.create(
            paciente=self.paciente, profesional=self.medico, fecha_hora=fecha_hora,
            tipo=Cita.Tipo.CONTROL,
        )
        pago = PagoCita.objects.create(
            cita=cita, tutor=self.tutor, metodo=PagoCita.Metodo.PRESENCIAL,
            estado=PagoCita.Estado.POR_PAGAR, monto_clp=25000,
        )
        admin = Usuario.objects.create_superuser(
            username='admin_pago_portal', email='admin.pago@example.test',
            password='Frase-Segura-987!',
        )
        self.client.force_login(admin)
        respuesta = self.client.post(
            reverse('admin:agenda_pagocita_changelist'),
            {'action': 'registrar_pagos_presenciales', '_selected_action': [pago.pk]},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        pago.refresh_from_db()
        cita.refresh_from_db()
        self.assertEqual(pago.estado, PagoCita.Estado.PAGADA)
        self.assertEqual(cita.estado, Cita.Estado.CONFIRMADA)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.tutor.email])
        self.assertIn('Comprobante de pago', mail.outbox[0].subject)
