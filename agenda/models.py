from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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
        if self.hora_inicio and self.hora_fin and self.hora_inicio >= self.hora_fin:
            raise ValidationError('La hora de inicio debe ser anterior a la hora de termino.')

    def generar_cupos(self, fecha):
        """Devuelve la lista de horas posibles (datetime) para una fecha dada."""
        if not self.activo or fecha.weekday() != self.dia_semana:
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
    duracion_minutos = models.PositiveSmallIntegerField(default=30)
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
        if not self.fecha_hora or not self.profesional_id:
            return

        # 1. No permitir dos citas encima para el mismo profesional.
        choque = Cita.objects.filter(
            profesional=self.profesional,
            fecha_hora__lt=self.fecha_hora_fin,
            estado__in=[self.Estado.AGENDADA, self.Estado.CONFIRMADA],
        ).exclude(pk=self.pk)

        for otra in choque:
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
