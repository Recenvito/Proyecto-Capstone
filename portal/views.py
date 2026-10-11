import hashlib
import logging
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from agenda.models import Bloqueo, Cita, Disponibilidad, PagoCita, TarifaServicio
from pacientes.models import AsignacionProfesional, DocumentoPaciente, Paciente, SolicitudAccesoTutor, Tutor
from usuarios.models import Auditoria, Usuario

from .forms import RegistroTutorForm, ReservaCitaForm, SolicitudVinculoForm
from .emails import enviar_comprobante_pago, enviar_comprobante_reserva, enviar_verificacion_correo
from .models import VerificacionCorreo

logger = logging.getLogger(__name__)


def _es_tutor(usuario):
    return usuario.is_authenticated and usuario.rol == Usuario.Rol.TUTOR


def registro(request):
    if request.user.is_authenticated:
        return redirect('portal:inicio' if _es_tutor(request.user) else 'inicio')
    form = RegistroTutorForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        datos = form.cleaned_data
        usuario = Usuario.objects.create_user(
            username=f'tutor_{uuid.uuid4().hex[:16]}',
            first_name=datos['nombres'], last_name=datos['apellidos'],
            email=datos['email'], rut=datos['rut_tutor'], telefono=datos['telefono'],
            rol=Usuario.Rol.TUTOR, is_active=False, password=datos['password1'],
        )
        SolicitudAccesoTutor.objects.create(
            usuario=usuario, paciente_rut=datos['rut_paciente'], parentesco=datos['parentesco'],
        )
        enviar_verificacion_correo(usuario, request)
        return render(request, 'portal/registro_enviado.html')
    return render(request, 'portal/registro.html', {'form': form})


def verificar_correo(request, token):
    if request.method == 'GET':
        return render(request, 'portal/confirmar_correo.html', {'token': token})
    if request.method != 'POST':
        return HttpResponseBadRequest('Método no permitido.')
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    verificacion = VerificacionCorreo.objects.select_related('usuario').filter(
        token_hash=token_hash, consumida_en__isnull=True, expira_en__gt=timezone.now(),
    ).first()
    if verificacion is None:
        return render(request, 'portal/verificacion_invalida.html', status=400)
    with transaction.atomic():
        verificacion = VerificacionCorreo.objects.select_for_update().get(pk=verificacion.pk)
        if verificacion.consumida_en or verificacion.expira_en <= timezone.now():
            return render(request, 'portal/verificacion_invalida.html', status=400)
        usuario = verificacion.usuario
        usuario.correo_verificado = True
        usuario.is_active = True
        usuario.save(update_fields=('correo_verificado', 'is_active'))
        verificacion.consumida_en = timezone.now()
        verificacion.save(update_fields=('consumida_en',))
    messages.success(request, 'Correo verificado. La clínica revisará el vínculo solicitado antes de habilitar el acceso a la ficha.')
    return redirect('login')


def _liberar_reservas_vencidas():
    """Reconcilia Webpay antes de liberar cupos online vencidos."""
    ahora = timezone.now()
    pagos = PagoCita.objects.filter(
        metodo=PagoCita.Metodo.WEBPAY,
        estado=PagoCita.Estado.INICIADA,
        expira_en__lte=ahora,
    ).select_related('cita')
    for pendiente in pagos:
        pago = pendiente
        if pago.token_transbank:
            try:
                estado = _transbank_transaction().status(pago.token_transbank)
                estado_transbank = estado.get('status') if isinstance(estado, dict) else None
                if estado_transbank == 'AUTHORIZED':
                    if _pago_autorizado(estado, pago):
                        _confirmar_pago(pago, estado)
                    # Una respuesta autorizada que no coincide con la orden o
                    # monto requiere revisión; no liberar el cupo.
                    continue
                if estado_transbank not in ('INITIALIZED', 'FAILED', 'REVERSED'):
                    # Si Transbank no entrega un estado concluyente, conservar la reserva.
                    continue
            except Exception:
                logger.error('No fue posible reconciliar una reserva Webpay vencida.')
                continue
        with transaction.atomic():
            pago = PagoCita.objects.select_for_update().select_related('cita').get(pk=pago.pk)
            if pago.estado != PagoCita.Estado.INICIADA or not pago.expira_en or pago.expira_en > timezone.now():
                continue
            if pago.reintento_presencial:
                pago.metodo = PagoCita.Metodo.PRESENCIAL
                pago.estado = PagoCita.Estado.POR_PAGAR
                pago.reintento_presencial = False
                pago.token_transbank = None
                pago.expira_en = None
                pago.save(update_fields=(
                    'metodo', 'estado', 'reintento_presencial', 'token_transbank',
                    'expira_en', 'actualizado_en',
                ))
                continue
            pago.estado = PagoCita.Estado.EXPIRADA
            pago.save(update_fields=('estado', 'actualizado_en'))
            Cita.objects.filter(pk=pago.cita_id, estado=Cita.Estado.AGENDADA).update(
                estado=Cita.Estado.CANCELADA,
            )
            _revertir_asignacion_de_reserva(pago)


def _pago_autorizado(respuesta, pago):
    try:
        return (
            respuesta.get('status') == 'AUTHORIZED'
            and int(respuesta.get('response_code', -1)) == 0
            and int(respuesta.get('amount', -1)) == pago.monto_clp
            and respuesta.get('buy_order') == pago.orden_compra
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _confirmar_pago(pago, respuesta):
    confirmado = False
    with transaction.atomic():
        pago = PagoCita.objects.select_for_update().get(pk=pago.pk)
        if pago.estado != PagoCita.Estado.INICIADA:
            return
        pago.estado = PagoCita.Estado.PAGADA
        pago.reintento_presencial = False
        pago.codigo_autorizacion = str(respuesta.get('authorization_code', ''))[:20]
        pago.save(update_fields=('estado', 'reintento_presencial', 'codigo_autorizacion', 'actualizado_en'))
        Cita.objects.filter(pk=pago.cita_id, estado=Cita.Estado.AGENDADA).update(
            estado=Cita.Estado.CONFIRMADA,
        )
        confirmado = True
    if confirmado:
        enviar_comprobante_reserva(pago)
        enviar_comprobante_pago(pago)


def _restaurar_pago_presencial(pago):
    """Devuelve a pago en clínica los intentos Webpay de una reserva existente."""
    with transaction.atomic():
        actualizado = PagoCita.objects.select_for_update().filter(
            pk=pago.pk, estado=PagoCita.Estado.INICIADA, reintento_presencial=True,
        ).update(
            metodo=PagoCita.Metodo.PRESENCIAL,
            estado=PagoCita.Estado.POR_PAGAR,
            reintento_presencial=False,
            token_transbank=None,
            expira_en=None,
            actualizado_en=timezone.now(),
        )
    return bool(actualizado)


def _revertir_asignacion_de_reserva(pago):
    if not pago.asignacion_vinculo_creado:
        return
    tiene_otra_cita = Cita.objects.filter(
        paciente_id=pago.cita.paciente_id, profesional_id=pago.cita.profesional_id,
    ).exclude(pk=pago.cita_id).exists()
    if not tiene_otra_cita:
        AsignacionProfesional.objects.filter(
            paciente_id=pago.cita.paciente_id,
            profesional_id=pago.cita.profesional_id,
            activa=True,
        ).update(activa=False, fecha_termino=timezone.now())


@login_required
def inicio(request):
    if not _es_tutor(request.user):
        return redirect('inicio')
    _liberar_reservas_vencidas()
    contactos_verificados = request.user.correo_verificado and request.user.telefono_verificado
    vinculos = Tutor.objects.filter(usuario=request.user, paciente__activo=True) if contactos_verificados else Tutor.objects.none()
    vinculos = vinculos.select_related('paciente').order_by('paciente__apellido_paterno', 'paciente__nombres')
    for vinculo in vinculos:
        Auditoria.objects.create(
            usuario=request.user, accion=Auditoria.Accion.CONSULTAR,
            modelo='Ficha de paciente (portal tutor)', registro_id=vinculo.paciente_id,
            ip=request.META.get('REMOTE_ADDR'),
            detalle={'evento': 'Consulta de ficha administrativa vinculada desde portal'},
        )
    solicitudes = request.user.solicitudes_vinculo_tutor.all()
    citas = Cita.objects.filter(
        paciente__tutores__usuario=request.user,
    ).exclude(estado=Cita.Estado.CANCELADA).select_related(
        'paciente', 'profesional', 'pago'
    ).order_by('-fecha_hora')[:20] if contactos_verificados else Cita.objects.none()
    documentos = DocumentoPaciente.objects.filter(
        paciente__activo=True, paciente__tutores__usuario=request.user, publicado=True,
    ).select_related('paciente').order_by('-fecha_documento', '-creado_en') if contactos_verificados else DocumentoPaciente.objects.none()
    return render(request, 'portal/inicio.html', {
        'vinculos': vinculos, 'solicitudes': solicitudes, 'citas': citas,
        'documentos': documentos,
        'contactos_verificados': contactos_verificados,
        'proxima_fecha_max': (timezone.localdate() + timedelta(days=180)).isoformat(),
    })


@login_required
def descargar_documento(request, pk):
    if not _es_tutor(request.user):
        return redirect('inicio')
    if not (request.user.is_active and request.user.correo_verificado and request.user.telefono_verificado):
        return redirect('portal:inicio')
    documento = get_object_or_404(
        DocumentoPaciente.objects.select_related('paciente'),
        pk=pk, publicado=True, paciente__activo=True,
        paciente__tutores__usuario=request.user,
    )
    archivo = documento.archivo.open('rb')
    Auditoria.objects.create(
        usuario=request.user, accion=Auditoria.Accion.CONSULTAR,
        modelo='Documento clínico del portal', registro_id=documento.pk,
        ip=request.META.get('REMOTE_ADDR'),
        detalle={'evento': 'Descarga autorizada', 'paciente_id': documento.paciente_id},
    )
    respuesta = FileResponse(
        archivo, as_attachment=True, filename=documento.archivo.name.rsplit('/', 1)[-1],
        content_type='application/pdf',
    )
    respuesta['X-Content-Type-Options'] = 'nosniff'
    return respuesta


@login_required
def solicitar_vinculo(request):
    if not _es_tutor(request.user):
        return redirect('inicio')
    if not (request.user.correo_verificado and request.user.telefono_verificado):
        messages.info(request, 'La clínica debe verificar tu correo y teléfono antes de enviar solicitudes de vínculo.')
        return redirect('portal:inicio')
    form = SolicitudVinculoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        rut = form.cleaned_data['rut_paciente']
        solicitud, creada = SolicitudAccesoTutor.objects.get_or_create(
            usuario=request.user, paciente_rut=rut,
            defaults={'parentesco': form.cleaned_data['parentesco']},
        )
        if not creada and solicitud.estado == SolicitudAccesoTutor.Estado.RECHAZADA:
            solicitud.parentesco = form.cleaned_data['parentesco']
            solicitud.estado = SolicitudAccesoTutor.Estado.PENDIENTE
            solicitud.revisada_en = None
            solicitud.revisada_por = None
            solicitud.save(update_fields=('parentesco', 'estado', 'revisada_en', 'revisada_por'))
            creada = True
        if creada:
            Auditoria.objects.create(
                usuario=request.user, accion=Auditoria.Accion.CREAR,
                modelo='Solicitud de vínculo de tutor', registro_id=solicitud.pk,
                ip=request.META.get('REMOTE_ADDR'), detalle={'evento': 'Solicitud de vínculo enviada'},
            )
            messages.success(request, 'La clínica revisará la solicitud. No se mostrarán datos hasta aprobar el vínculo.')
        else:
            messages.info(request, 'Ya existe una solicitud o un vínculo para ese identificador.')
        return redirect('portal:inicio')
    return render(request, 'portal/solicitar_vinculo.html', {'form': form})


def _cupo_disponible(profesional, fecha_hora, duracion):
    if fecha_hora <= timezone.now():
        return False
    disponibilidad = Disponibilidad.objects.filter(
        profesional=profesional, activo=True, dia_semana=fecha_hora.weekday(),
    )
    valido = any(
        fecha_hora in disp.generar_cupos(fecha_hora.date())
        and disp.duracion_cita_minutos == duracion
        for disp in disponibilidad
    )
    if not valido:
        return False
    fin = fecha_hora + timedelta(minutes=duracion)
    if Bloqueo.objects.filter(profesional=profesional, inicio__lt=fin, fin__gt=fecha_hora).exists():
        return False
    citas = Cita.objects.filter(
        profesional=profesional,
        fecha_hora__lt=fin,
        estado__in=(Cita.Estado.AGENDADA, Cita.Estado.CONFIRMADA),
    ).select_related('pago')
    for cita in citas:
        if cita.fecha_hora_fin <= fecha_hora:
            continue
        pago = getattr(cita, 'pago', None)
        if pago and pago.estado == PagoCita.Estado.INICIADA and pago.expira_en and pago.expira_en <= timezone.now():
            continue
        return False
    return True


def _horas_disponibles(profesional, fecha):
    horas = []
    for disponibilidad in Disponibilidad.objects.filter(profesional=profesional, activo=True):
        for cupo in disponibilidad.generar_cupos(fecha):
            if _cupo_disponible(profesional, cupo, disponibilidad.duracion_cita_minutos):
                horas.append((cupo, disponibilidad.duracion_cita_minutos, disponibilidad.lugar))
    return sorted(horas, key=lambda item: item[0])


def _transbank_transaction():
    """Crea el cliente únicamente en modo integración, nunca producción."""
    from transbank.common.integration_api_keys import IntegrationApiKeys
    from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
    from transbank.common.integration_type import IntegrationType
    from transbank.common.options import WebpayOptions
    from transbank.webpay.webpay_plus.transaction import Transaction

    commerce_code = getattr(settings, 'TRANSBANK_INTEGRATION_COMMERCE_CODE', '') or IntegrationCommerceCodes.WEBPAY_PLUS
    api_key = getattr(settings, 'TRANSBANK_INTEGRATION_API_KEY', '') or IntegrationApiKeys.WEBPAY
    return Transaction(WebpayOptions(commerce_code, api_key, IntegrationType.TEST, timeout=10))


@login_required
def reservar(request):
    if not _es_tutor(request.user):
        return redirect('inicio')
    _liberar_reservas_vencidas()
    if not (request.user.correo_verificado and request.user.telefono_verificado):
        messages.info(request, 'La clínica debe verificar tu correo y teléfono antes de habilitar las fichas y reservas.')
        return redirect('portal:inicio')
    if not Tutor.objects.filter(usuario=request.user, paciente__activo=True).exists():
        messages.info(request, 'La clínica debe aprobar primero el vínculo con una ficha antes de reservar.')
        return redirect('portal:inicio')

    datos = request.POST if request.method == 'POST' else request.GET
    fecha_texto = datos.get('fecha', '')
    try:
        fecha = datetime.strptime(fecha_texto, '%Y-%m-%d').date() if fecha_texto else timezone.localdate() + timedelta(days=1)
    except ValueError:
        fecha = timezone.localdate() + timedelta(days=1)
    form = ReservaCitaForm(request.POST or None, usuario=request.user, initial={
        'fecha': fecha, 'paciente': datos.get('paciente'), 'profesional': datos.get('profesional'),
        'tipo': datos.get('tipo') or Cita.Tipo.PRIMERA_VEZ,
    })
    profesional = form.fields['profesional'].queryset.filter(pk=datos.get('profesional')).first()
    cupos = _horas_disponibles(profesional, fecha) if profesional else []
    tarifas = {tarifa.tipo: tarifa.monto_clp for tarifa in TarifaServicio.objects.filter(activa=True)}

    if request.method == 'POST' and form.is_valid():
        paciente = form.cleaned_data['paciente']
        profesional = form.cleaned_data['profesional']
        fecha_hora = form.cleaned_data['hora']
        duracion = None
        for hora, minutos, _lugar in _horas_disponibles(profesional, fecha_hora.date()):
            if hora == fecha_hora:
                duracion = minutos
                break
        tarifa = TarifaServicio.objects.filter(tipo=form.cleaned_data['tipo'], activa=True).first()
        if not tarifa:
            form.add_error(None, 'La clínica aún no ha configurado una tarifa activa para esta atención.')
        elif duracion is None:
            form.add_error('hora', 'Ese horario ya no está disponible. Selecciona otro cupo.')
        elif form.cleaned_data['forma_pago'] == 'WEBPAY' and not getattr(settings, 'PORTAL_WEBPAY_ACTIVO', True):
            form.add_error(None, 'El pago en línea está temporalmente deshabilitado. Puedes reservar para pagar en clínica.')
        else:
            try:
                with transaction.atomic():
                    profesional = Usuario.objects.select_for_update().get(pk=profesional.pk)
                    if not _cupo_disponible(profesional, fecha_hora, duracion):
                        raise ValueError('Ese horario ya no está disponible. Selecciona otro cupo.')
                    cita = Cita(
                        paciente=paciente, profesional=profesional, fecha_hora=fecha_hora,
                        duracion_minutos=duracion, tipo=form.cleaned_data['tipo'],
                        motivo=form.cleaned_data['motivo'], creada_por=request.user,
                    )
                    cita.save()
                    asignacion = AsignacionProfesional.objects.filter(
                        paciente=paciente, profesional=profesional,
                    ).first()
                    asignacion_vinculo_creado = False
                    if asignacion is None:
                        AsignacionProfesional.objects.create(
                            paciente=paciente, profesional=profesional,
                        )
                        asignacion_vinculo_creado = True
                    elif not asignacion.activa:
                        asignacion.activa = True
                        asignacion.fecha_termino = None
                        asignacion.save(update_fields=('activa', 'fecha_termino'))
                        asignacion_vinculo_creado = True
                    online = form.cleaned_data['forma_pago'] == 'WEBPAY'
                    pago = PagoCita.objects.create(
                        cita=cita, tutor=request.user,
                        metodo=PagoCita.Metodo.WEBPAY if online else PagoCita.Metodo.PRESENCIAL,
                        estado=PagoCita.Estado.INICIADA if online else PagoCita.Estado.POR_PAGAR,
                        monto_clp=tarifa.monto_clp,
                        expira_en=timezone.now() + timedelta(minutes=15) if online else None,
                        asignacion_vinculo_creado=asignacion_vinculo_creado,
                    )
                    Auditoria.objects.create(
                        usuario=request.user, accion=Auditoria.Accion.CREAR,
                        modelo='Cita (portal tutor)', registro_id=cita.pk,
                        ip=request.META.get('REMOTE_ADDR'),
                        detalle={
                            'paciente_id': paciente.pk,
                            'profesional_id': profesional.pk,
                            'tipo': cita.tipo,
                            'metodo_pago': pago.metodo,
                            'monto_clp': pago.monto_clp,
                        },
                    )
                if form.cleaned_data['forma_pago'] == 'WEBPAY':
                    retorno = request.build_absolute_uri(reverse('portal:webpay_retorno'))
                    respuesta = _transbank_transaction().create(
                        pago.orden_compra, pago.sesion_id, pago.monto_clp, retorno,
                    )
                    token = respuesta.get('token') if isinstance(respuesta, dict) else getattr(respuesta, 'token', None)
                    url_pago = respuesta.get('url') if isinstance(respuesta, dict) else getattr(respuesta, 'url', None)
                    if not token or not url_pago:
                        raise RuntimeError('Respuesta incompleta de Webpay')
                    pago.token_transbank = token
                    pago.save(update_fields=('token_transbank', 'actualizado_en'))
                    return render(request, 'portal/redirigir_webpay.html', {
                        'url_webpay': url_pago, 'token_webpay': token,
                    })
                enviar_comprobante_reserva(pago)
                messages.success(request, 'La hora quedó reservada. El pago se realizará en la clínica.')
                return redirect('portal:inicio')
            except ValueError as error:
                form.add_error('hora', str(error))
            except ValidationError as error:
                form.add_error('hora', '; '.join(error.messages))
            except Exception:
                logger.error('No fue posible iniciar el pago Webpay de la reserva.')
                if 'pago' in locals():
                    PagoCita.objects.filter(pk=pago.pk, estado=PagoCita.Estado.INICIADA).update(
                        estado=PagoCita.Estado.FALLIDA,
                    )
                    Cita.objects.filter(pk=cita.pk, estado=Cita.Estado.AGENDADA).update(
                        estado=Cita.Estado.CANCELADA,
                    )
                    _revertir_asignacion_de_reserva(pago)
                form.add_error(None, 'No pudimos conectar con Webpay. No se realizó ningún cobro; intenta nuevamente o reserva para pagar en clínica.')

    return render(request, 'portal/reservar.html', {
        'form': form, 'fecha': fecha, 'cupos': cupos, 'tarifas': tarifas,
        'hoy': timezone.localdate(),
        'max_fecha': (timezone.localdate() + timedelta(days=180)).isoformat(),
        'medico_seleccionado': profesional,
    })


@login_required
@require_POST
def pagar_cita_webpay(request, pk):
    if not _es_tutor(request.user):
        return redirect('inicio')
    if not (request.user.is_active and request.user.correo_verificado and request.user.telefono_verificado):
        messages.info(request, 'Verifica tus datos antes de iniciar un pago.')
        return redirect('portal:inicio')
    if not getattr(settings, 'PORTAL_WEBPAY_ACTIVO', True):
        messages.error(request, 'El pago en línea está temporalmente deshabilitado. Puedes pagar en la clínica.')
        return redirect('portal:inicio')
    pago = get_object_or_404(
        PagoCita.objects.select_related('cita'),
        cita_id=pk, tutor=request.user, metodo=PagoCita.Metodo.PRESENCIAL,
        estado=PagoCita.Estado.POR_PAGAR, cita__estado=Cita.Estado.AGENDADA,
    )
    if pago.monto_clp <= 0:
        messages.error(request, 'La tarifa de esta atención debe ser mayor que $0 para pagar en línea.')
        return redirect('portal:inicio')

    with transaction.atomic():
        pago = get_object_or_404(
            PagoCita.objects.select_for_update().select_related('cita'),
            pk=pago.pk, tutor=request.user, metodo=PagoCita.Metodo.PRESENCIAL,
            estado=PagoCita.Estado.POR_PAGAR, cita__estado=Cita.Estado.AGENDADA,
        )
        pago.metodo = PagoCita.Metodo.WEBPAY
        pago.estado = PagoCita.Estado.INICIADA
        pago.reintento_presencial = True
        pago.orden_compra = uuid.uuid4().hex[:26]
        pago.sesion_id = uuid.uuid4().hex
        pago.token_transbank = None
        pago.expira_en = timezone.now() + timedelta(minutes=15)
        pago.save(update_fields=(
            'metodo', 'estado', 'reintento_presencial', 'orden_compra', 'sesion_id',
            'token_transbank', 'expira_en', 'actualizado_en',
        ))

    try:
        retorno = request.build_absolute_uri(reverse('portal:webpay_retorno'))
        respuesta = _transbank_transaction().create(
            pago.orden_compra, pago.sesion_id, pago.monto_clp, retorno,
        )
        token = respuesta.get('token') if isinstance(respuesta, dict) else getattr(respuesta, 'token', None)
        url_pago = respuesta.get('url') if isinstance(respuesta, dict) else getattr(respuesta, 'url', None)
        if not token or not url_pago:
            raise RuntimeError('Respuesta incompleta de Webpay')
        pago.token_transbank = token
        pago.save(update_fields=('token_transbank', 'actualizado_en'))
        return render(request, 'portal/redirigir_webpay.html', {
            'url_webpay': url_pago, 'token_webpay': token,
        })
    except Exception:
        logger.exception('No fue posible iniciar el pago Webpay de una reserva existente.')
        _restaurar_pago_presencial(pago)
        messages.error(request, 'No pudimos conectar con Webpay. La hora sigue reservada y puedes pagar en la clínica o intentarlo nuevamente.')
        return redirect('portal:inicio')


@login_required
def webpay_retorno(request):
    if not _es_tutor(request.user):
        return redirect('inicio')
    token = request.GET.get('token_ws')
    if not token:
        token = request.GET.get('TBK_TOKEN') or request.POST.get('TBK_TOKEN')
        if token:
            pago = PagoCita.objects.filter(token_transbank=token, tutor=request.user).select_related('cita').first()
            if pago and pago.estado == PagoCita.Estado.INICIADA:
                if not _restaurar_pago_presencial(pago):
                    pago.estado = PagoCita.Estado.FALLIDA
                    pago.save(update_fields=('estado', 'actualizado_en'))
                    pago.cita.estado = Cita.Estado.CANCELADA
                    pago.cita.save(update_fields=('estado',))
                    _revertir_asignacion_de_reserva(pago)
            messages.warning(request, 'El pago no se completó. Revisa el estado de la reserva en el portal.')
            return redirect('portal:inicio')
        return HttpResponseBadRequest('Retorno Webpay no válido.')
    pago = get_object_or_404(
        PagoCita.objects.select_related('cita'), token_transbank=token, tutor=request.user,
    )
    if pago.estado == PagoCita.Estado.PAGADA:
        return redirect('portal:inicio')
    if pago.estado != PagoCita.Estado.INICIADA:
        messages.error(request, 'La reserva o el pago ya expiró. Selecciona un nuevo horario.')
        return redirect('portal:inicio')
    try:
        respuesta = _transbank_transaction().commit(token)
        autorizado = _pago_autorizado(respuesta, pago)
    except Exception:
        logger.error('No fue posible confirmar el resultado del pago Webpay.')
        messages.error(request, 'No fue posible confirmar el pago. Contacta a la clínica antes de volver a reservar.')
        return redirect('portal:inicio')
    if autorizado:
        _confirmar_pago(pago, respuesta)
        messages.success(request, 'Pago aprobado y hora confirmada.')
    else:
        if _restaurar_pago_presencial(pago):
            messages.error(request, 'El pago no fue aprobado. La reserva sigue vigente y puedes pagar en la clínica o intentarlo nuevamente.')
        else:
            pago.estado = PagoCita.Estado.FALLIDA
            pago.save(update_fields=('estado', 'actualizado_en'))
            pago.cita.estado = Cita.Estado.CANCELADA
            pago.cita.save(update_fields=('estado',))
            _revertir_asignacion_de_reserva(pago)
            messages.error(request, 'El pago no fue aprobado y la hora quedó liberada.')
    return redirect('portal:inicio')
