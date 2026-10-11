from datetime import datetime, timedelta
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def generar_orden_compra():
    return uuid.uuid4().hex[:26]


def generar_sesion_pago():
    return uuid.uuid4().hex


class Disponibilidad(models.Model):
    """
    Horario semanal en que el profesional atiende.
    Ej: "los martes de 15:00 a 19:00, en bloques de 30 minutos".
    De aqui el sistema calcula los cupos libres para agendar.
    """

    class DiaSemana(models.IntegerChoices):
        LUNES = 0, 'Lunes'
        MARTES = 1, 'Martes'
        MIERCOLES = 2, 'Miercoles'
        JUEVES = 3, 'Jueves'
        VIERNES = 4, 'Viernes'
        SABADO = 5, 'Sabado'
        DOMINGO = 6, 'Domingo'

    profesional = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='disponibilidades',
    )
    dia_semana = models.IntegerField(choices=DiaSemana.choices, verbose_name='Dia')
    hora_inicio = models.TimeField(verbose_name='Desde')
    hora_fin = models.TimeField(verbose_name='Hasta')
    duracion_cita_minutos = models.PositiveSmallIntegerField(
        default=30, verbose_name='Duracion de cada hora (minutos)',
        validators=[MinValueValidator(5), MaxValueValidator(240)],
    )
    lugar = models.CharField(
        max_length=150, blank=True, verbose_name='Lugar de atencion',
        help_text='Ej: Consulta particular, Clinica X.',
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Disponibilidad'
        verbose_name_plural = 'Disponibilidades'
        ordering = ['dia_semana', 'hora_inicio']

    def __str__(self):
        return f'{self.get_dia_semana_display()} {self.hora_inicio:%H:%M} a {self.hora_fin:%H:%M}'

    def clean(self):
        if self.duracion_cita_minutos and self.duracion_cita_minutos % 5:
            raise ValidationError({'duracion_cita_minutos': 'La duración debe avanzar en múltiplos de 5 minutos.'})
        if self.hora_inicio and self.hora_fin and self.hora_inicio >= self.hora_fin:
            raise ValidationError('La hora de inicio debe ser anterior a la hora de termino.')

    def generar_cupos(self, fecha):
        """Devuelve la lista de horas posibles (datetime) para una fecha dada."""
        if not self.activo or not self.duracion_cita_minutos or fecha.weekday() != self.dia_semana:
            return []

        tz = timezone.get_current_timezone()
        actual = timezone.make_aware(datetime.combine(fecha, self.hora_inicio), tz)
        termino = timezone.make_aware(datetime.combine(fecha, self.hora_fin), tz)
        paso = timedelta(minutes=self.duracion_cita_minutos)

        cupos = []
        while actual + paso <= termino:
            cupos.append(actual)
            actual += paso
        return cupos


class Bloqueo(models.Model):
    """Periodos en que el profesional NO atiende: vacaciones, congresos, etc."""

    profesional = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bloqueos',
    )
    inicio = models.DateTimeField()
    fin = models.DateTimeField()
    motivo = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'Bloqueo de agenda'
        verbose_name_plural = 'Bloqueos de agenda'
        ordering = ['-inicio']

    def __str__(self):
        return f'{self.motivo or "Bloqueo"}: {self.inicio:%d/%m/%Y} a {self.fin:%d/%m/%Y}'

    def clean(self):
        if self.inicio and self.fin and self.inicio >= self.fin:
            raise ValidationError('El inicio del bloqueo debe ser anterior al termino.')


class Cita(models.Model):
    """Una hora agendada para un paciente."""

    class Estado(models.TextChoices):
        AGENDADA = 'AGENDADA', 'Agendada'
        CONFIRMADA = 'CONFIRMADA', 'Confirmada'
        ATENDIDA = 'ATENDIDA', 'Atendida'
        CANCELADA = 'CANCELADA', 'Cancelada'
        NO_ASISTE = 'NO_ASISTE', 'No asistio'

    class Tipo(models.TextChoices):
        PRIMERA_VEZ = 'PRIMERA', 'Primera consulta'
        CONTROL = 'CONTROL', 'Control'
        INFORME = 'INFORME', 'Entrega de informe / examenes'

    paciente = models.ForeignKey(
        'pacientes.Paciente', on_delete=models.PROTECT, related_name='citas',
    )
    profesional = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='citas',
    )
    fecha_hora = models.DateTimeField(verbose_name='Fecha y hora')
    duracion_minutos = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(240)],
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.CONTROL)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.AGENDADA)
    motivo = models.TextField(blank=True, verbose_name='Motivo de la consulta')
    notas_internas = models.TextField(
        blank=True, verbose_name='Notas internas',
        help_text='Visible solo para el equipo, no para el paciente.',
    )

    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='citas_creadas',
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    recordatorio_enviado = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Cita'
        verbose_name_plural = 'Citas'
        ordering = ['fecha_hora']
        indexes = [models.Index(fields=['fecha_hora', 'profesional'])]

    def __str__(self):
        return f'{self.fecha_hora:%d/%m/%Y %H:%M} - {self.paciente.nombre_completo}'

    @property
    def fecha_hora_fin(self):
        return self.fecha_hora + timedelta(minutes=self.duracion_minutos)

    @property
    def es_futura(self):
        return self.fecha_hora > timezone.now()

    def clean(self):
        """Reglas de negocio: se validan antes de guardar."""
        if self.duracion_minutos and self.duracion_minutos % 5:
            raise ValidationError({'duracion_minutos': 'La duración debe avanzar en múltiplos de 5 minutos.'})
        if not self.fecha_hora or not self.profesional_id:
            return

        # 1. No permitir dos citas encima para el mismo profesional.
        choque = Cita.objects.filter(
            profesional=self.profesional,
            fecha_hora__lt=self.fecha_hora_fin,
            estado__in=[self.Estado.AGENDADA, self.Estado.CONFIRMADA],
        ).exclude(pk=self.pk)

        for otra in choque:
            pago = getattr(otra, 'pago', None)
            if (pago and pago.estado == PagoCita.Estado.INICIADA and pago.expira_en
                    and pago.expira_en <= timezone.now()):
                continue
            if otra.fecha_hora_fin > self.fecha_hora:
                raise ValidationError(
                    f'El profesional ya tiene una hora agendada a las '
                    f'{otra.fecha_hora:%H:%M} con {otra.paciente.nombre_completo}.'
                )

        # 2. No agendar dentro de un bloqueo (vacaciones, etc.).
        if Bloqueo.objects.filter(
            profesional=self.profesional,
            inicio__lt=self.fecha_hora_fin,
            fin__gt=self.fecha_hora,
        ).exists():
            raise ValidationError('El profesional no atiende en esa fecha (agenda bloqueada).')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class TarifaServicio(models.Model):
    """Tarifa vigente configurada por la clínica; el sistema no inventa precios."""

    tipo = models.CharField(max_length=20, choices=Cita.Tipo.choices, unique=True)
    monto_clp = models.PositiveIntegerField(verbose_name='Monto en pesos chilenos')
    activa = models.BooleanField(default=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tarifa de servicio'
        verbose_name_plural = 'Tarifas de servicios'
        ordering = ['tipo']

    def __str__(self):
        return f'{self.get_tipo_display()}: ${self.monto_clp:,} CLP'


class PagoCita(models.Model):
    """Registro de pago Webpay Plus o pago presencial asociado a una cita."""

    class Metodo(models.TextChoices):
        WEBPAY = 'WEBPAY', 'Webpay'
        PRESENCIAL = 'PRESENCIAL', 'Pago en clínica'

    class Estado(models.TextChoices):
        POR_PAGAR = 'POR_PAGAR', 'Por pagar en clínica'
        INICIADA = 'INICIADA', 'Pago Webpay iniciado'
        PAGADA = 'PAGADA', 'Pagada'
        FALLIDA = 'FALLIDA', 'Pago rechazado'
        EXPIRADA = 'EXPIRADA', 'Reserva expirada'

    cita = models.OneToOneField(Cita, on_delete=models.PROTECT, related_name='pago')
    tutor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='pagos_citas')
    metodo = models.CharField(max_length=12, choices=Metodo.choices)
    estado = models.CharField(max_length=12, choices=Estado.choices)
    monto_clp = models.PositiveIntegerField()
    orden_compra = models.CharField(max_length=26, unique=True, default=generar_orden_compra)
    sesion_id = models.CharField(max_length=32, default=generar_sesion_pago)
    token_transbank = models.CharField(max_length=64, unique=True, null=True, blank=True)
    codigo_autorizacion = models.CharField(max_length=20, blank=True)
    asignacion_vinculo_creado = models.BooleanField(default=False)
    reintento_presencial = models.BooleanField(default=False)
    comprobante_reserva_enviado_en = models.DateTimeField(null=True, blank=True)
    comprobante_pago_enviado_en = models.DateTimeField(null=True, blank=True)
    expira_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pago de cita'
        verbose_name_plural = 'Pagos de citas'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.cita_id} - {self.get_estado_display()} - ${self.monto_clp} CLP'
