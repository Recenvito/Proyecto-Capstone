import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from agenda.models import PagoCita
from .models import VerificacionCorreo

logger = logging.getLogger(__name__)


def enviar_verificacion_correo(usuario, request):
    token, token_hash = VerificacionCorreo.generar_token()
    VerificacionCorreo.objects.update_or_create(
        usuario=usuario,
        defaults={
            'token_hash': token_hash,
            'expira_en': VerificacionCorreo.expiracion(),
            'consumida_en': None,
        },
    )
    enlace = request.build_absolute_uri(
        reverse('portal:verificar_correo', kwargs={'token': token})
    )
    send_mail(
        'Verifica tu correo de NeuroFicha',
        f'Para verificar el correo de tu cuenta, abre este enlace válido por 24 horas:\n\n{enlace}\n\n'
        'La clínica revisará tu identidad, teléfono y representación antes de habilitar la ficha solicitada.',
        settings.DEFAULT_FROM_EMAIL, [usuario.email], fail_silently=False,
    )


def _reservar_envio_comprobante(pago_id, campo):
    """Marca el comprobante antes del envío para evitar correos duplicados concurrentes."""
    with transaction.atomic():
        pago = PagoCita.objects.select_for_update().select_related(
            'cita__paciente', 'cita__profesional', 'tutor',
        ).filter(pk=pago_id).first()
        if pago is None or getattr(pago, campo) or not pago.tutor.email:
            return None
        enviado_en = timezone.now()
        setattr(pago, campo, enviado_en)
        pago.save(update_fields=(campo, 'actualizado_en'))
        return pago, enviado_en


def _enviar_comprobante(pago_id, campo, asunto, cuerpo):
    reservado = _reservar_envio_comprobante(pago_id, campo)
    if reservado is None:
        return False
    pago, enviado_en = reservado
    try:
        enviados = send_mail(asunto, cuerpo(pago), settings.DEFAULT_FROM_EMAIL, [pago.tutor.email])
        if enviados != 1:
            raise RuntimeError('El backend no confirmó el envío del correo.')
    except Exception:
        PagoCita.objects.filter(pk=pago.pk, **{campo: enviado_en}).update(**{campo: None})
        logger.exception('No se pudo enviar el comprobante de NeuroFicha (pago %s).', pago.pk)
        return False
    return True


def enviar_comprobante_reserva(pago):
    def cuerpo(registro):
        cita = registro.cita
        fecha = timezone.localtime(cita.fecha_hora).strftime('%d/%m/%Y a las %H:%M')
        monto = f'${registro.monto_clp:,}'.replace(',', '.')
        return (
            'Tu reserva fue registrada en NeuroFicha.\n\n'
            f'Paciente: {cita.paciente.nombre_completo}\n'
            f'Profesional: {cita.profesional.get_full_name() or cita.profesional.username}\n'
            f'Fecha y hora: {fecha}\n'
            f'Tipo de atención: {cita.get_tipo_display()}\n'
            f'Estado de la reserva: {cita.get_estado_display()}\n'
            f'Estado del pago: {registro.get_estado_display()}\n'
            f'Monto: {monto} CLP\n\n'
            'Este comprobante corresponde a la reserva; conserva este correo para consultarlo.'
        )

    return _enviar_comprobante(
        pago.pk, 'comprobante_reserva_enviado_en',
        'Comprobante de reserva · NeuroFicha', cuerpo,
    )


def enviar_comprobante_pago(pago):
    def cuerpo(registro):
        cita = registro.cita
        fecha = timezone.localtime(cita.fecha_hora).strftime('%d/%m/%Y a las %H:%M')
        monto = f'${registro.monto_clp:,}'.replace(',', '.')
        return (
            'Registramos el pago asociado a tu atención en NeuroFicha.\n\n'
            f'Paciente: {cita.paciente.nombre_completo}\n'
            f'Profesional: {cita.profesional.get_full_name() or cita.profesional.username}\n'
            f'Fecha y hora de la atención: {fecha}\n'
            f'Tipo de atención: {cita.get_tipo_display()}\n'
            f'Monto pagado: {monto} CLP\n'
            f'Método: {registro.get_metodo_display()}\n'
            f'Orden de compra: {registro.orden_compra}\n'
            f'Código de autorización: {registro.codigo_autorizacion or "Registrado en clínica"}\n\n'
            'Este correo es el comprobante del pago. No incluye datos de tarjeta.'
        )

    return _enviar_comprobante(
        pago.pk, 'comprobante_pago_enviado_en',
        'Comprobante de pago · NeuroFicha', cuerpo,
    )
