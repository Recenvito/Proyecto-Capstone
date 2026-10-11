from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.utils.text import get_valid_filename


MAXIMO_INFORME_BYTES = 10 * 1024 * 1024


def validar_archivo_pdf(archivo):
    if Path(archivo.name).suffix.lower() != '.pdf':
        raise ValidationError('El informe debe estar en formato PDF.')
    posicion = archivo.tell() if hasattr(archivo, 'tell') else None
    cabecera = archivo.read(5)
    if posicion is not None:
        archivo.seek(posicion)
    if cabecera != b'%PDF-':
        raise ValidationError('El archivo no parece ser un PDF válido.')
    if archivo.size > MAXIMO_INFORME_BYTES:
        raise ValidationError('El informe no puede superar los 10 MB.')


def ruta_informe_paciente(instancia, nombre_archivo):
    nombre_seguro = get_valid_filename(Path(nombre_archivo).name)
    return f'informes/paciente_{instancia.paciente_id}/{timezone.now():%Y/%m}/{nombre_seguro}'


class Paciente(models.Model):
    """Ficha administrativa del paciente (nino/a). Datos de identificacion."""

    class Sexo(models.TextChoices):
        FEMENINO = 'F', 'Femenino'
        MASCULINO = 'M', 'Masculino'
        OTRO = 'O', 'Otro'

    class Prevision(models.TextChoices):
        FONASA = 'FONASA', 'Fonasa'
        ISAPRE = 'ISAPRE', 'Isapre'
        PARTICULAR = 'PARTICULAR', 'Particular'
        OTRA = 'OTRA', 'Otra'

    rut = models.CharField(
        max_length=12, unique=True, verbose_name='RUT',
        help_text='Formato 12345678-9. Si no tiene, usar el del pasaporte.',
    )
    nombres = models.CharField(max_length=100)
    apellido_paterno = models.CharField(max_length=50)
    apellido_materno = models.CharField(max_length=50, blank=True)
    fecha_nacimiento = models.DateField(verbose_name='Fecha de nacimiento')
    sexo = models.CharField(max_length=1, choices=Sexo.choices)

    prevision = models.CharField(
        max_length=20, choices=Prevision.choices,
        default=Prevision.FONASA, verbose_name='Prevision de salud',
    )
    direccion = models.CharField(max_length=200, blank=True)
    comuna = models.CharField(max_length=80, blank=True)

    # Contexto escolar: relevante en neurologia infantil (TDAH, TEA, epilepsia)
    colegio = models.CharField(max_length=150, blank=True, verbose_name='Establecimiento educacional')
    curso = models.CharField(max_length=50, blank=True)

    derivado_por = models.CharField(
        max_length=150, blank=True,
        verbose_name='Derivado por',
        help_text='Profesional o institucion que deriva al paciente.',
    )

    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'
        ordering = ['apellido_paterno', 'apellido_materno', 'nombres']

    def __str__(self):
        return f'{self.nombre_completo} ({self.rut})'

    def get_absolute_url(self):
        return reverse('pacientes:detalle', args=[self.pk])

    @property
    def nombre_completo(self):
        return f'{self.nombres} {self.apellido_paterno} {self.apellido_materno}'.strip()

    @property
    def edad(self):
        """Edad en anios cumplidos, calculada al dia de hoy."""
        hoy = date.today()
        return hoy.year - self.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )

    @property
    def edad_texto(self):
        """En lactantes el dato util son los meses, no los anios."""
        hoy = date.today()
        meses = (hoy.year - self.fecha_nacimiento.year) * 12 + hoy.month - self.fecha_nacimiento.month
        if hoy.day < self.fecha_nacimiento.day:
            meses -= 1
        if meses < 24:
            return f'{meses} meses'
        return f'{self.edad} anios'

    @property
    def tutor_principal(self):
        return self.tutores.filter(es_principal=True).first() or self.tutores.first()

class AsignacionProfesional(models.Model):
    """Relaciona un paciente con un profesional de su equipo tratante."""

    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name='asignaciones_profesionales',
    )
    profesional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='pacientes_asignados',
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_termino = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de termino')
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Asignacion profesional'
        verbose_name_plural = 'Asignaciones profesionales'
        constraints = [
            models.UniqueConstraint(
                fields=['paciente', 'profesional'],
                name='asignacion_paciente_profesional_unica',
            ),
        ]
        ordering = ['-fecha_asignacion']

    def __str__(self):
        return f'{self.profesional} - {self.paciente.nombre_completo}'

    def save(self, *args, **kwargs):
        if not self.activa and self.fecha_termino is None:
            self.fecha_termino = timezone.now()
        super().save(*args, **kwargs)


class Tutor(models.Model):
    """Madre, padre o apoderado responsable del paciente."""

    class Parentesco(models.TextChoices):
        MADRE = 'MADRE', 'Madre'
        PADRE = 'PADRE', 'Padre'
        ABUELO = 'ABUELO', 'Abuelo/a'
        TUTOR_LEGAL = 'TUTOR', 'Tutor legal'
        OTRO = 'OTRO', 'Otro'

    paciente = models.ForeignKey(
        Paciente, on_delete=models.CASCADE, related_name='tutores',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='vinculos_tutor', verbose_name='Cuenta del tutor',
    )
    rut = models.CharField(max_length=12, blank=True, verbose_name='RUT')
    nombre_completo = models.CharField(max_length=150)
    parentesco = models.CharField(max_length=20, choices=Parentesco.choices)
    telefono = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    es_principal = models.BooleanField(
        default=True,
        verbose_name='Contacto principal',
        help_text='A este contacto se le envian los recordatorios de hora.',
    )

    class Meta:
        verbose_name = 'Tutor / Apoderado'
        verbose_name_plural = 'Tutores / Apoderados'
        ordering = ['-es_principal', 'nombre_completo']

    def __str__(self):
        return f'{self.nombre_completo} ({self.get_parentesco_display()})'


class DocumentoPaciente(models.Model):
    """Copia documental publicada por la clínica para representantes autorizados."""

    paciente = models.ForeignKey(
        Paciente, on_delete=models.PROTECT, related_name='documentos_portal',
    )
    titulo = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=300, blank=True)
    archivo = models.FileField(
        upload_to=ruta_informe_paciente,
        validators=[FileExtensionValidator(['pdf']), validar_archivo_pdf],
    )
    fecha_documento = models.DateField(default=timezone.localdate)
    publicado = models.BooleanField(default=False)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='documentos_pacientes_subidos',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Informe para portal de pacientes'
        verbose_name_plural = 'Informes para portal de pacientes'
        ordering = ['-fecha_documento', '-creado_en']

    def __str__(self):
        return f'{self.titulo} · {self.paciente.nombre_completo}'

    def clean(self):
        super().clean()
        if self.archivo and self.archivo.size > MAXIMO_INFORME_BYTES:
            raise ValidationError({'archivo': 'El informe no puede superar los 10 MB.'})


class SolicitudAccesoTutor(models.Model):
    """Solicitud privada para vincular una cuenta verificada con una ficha."""

    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de revisión clínica'
        APROBADA = 'APROBADA', 'Aprobada'
        RECHAZADA = 'RECHAZADA', 'Rechazada'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='solicitudes_vinculo_tutor',
    )
    paciente_rut = models.CharField(max_length=12, verbose_name='RUT de paciente solicitado')
    parentesco = models.CharField(max_length=20, choices=Tutor.Parentesco.choices)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    creada_en = models.DateTimeField(auto_now_add=True)
    revisada_en = models.DateTimeField(null=True, blank=True)
    revisada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_vinculo_revisadas',
    )

    class Meta:
        verbose_name = 'Solicitud de acceso de tutor'
        verbose_name_plural = 'Solicitudes de acceso de tutores'
        ordering = ['estado', '-creada_en']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'paciente_rut'], name='solicitud_tutor_usuario_rut_unica',
            ),
        ]

    def __str__(self):
        return f'{self.usuario} solicita acceso a ficha {self.paciente_rut}'


class AntecedentesNeurologicos(models.Model):
    """
    Antecedentes perinatales y del desarrollo. En neurologia infantil esto se
    llena una vez (en la primera consulta) y se va actualizando.
    """

    class TipoParto(models.TextChoices):
        VAGINAL = 'VAGINAL', 'Parto vaginal'
        CESAREA = 'CESAREA', 'Cesarea'
        DESCONOCIDO = 'DESC', 'Desconocido'

    paciente = models.OneToOneField(
        Paciente, on_delete=models.CASCADE, related_name='antecedentes',
    )

    # --- Embarazo y parto ---
    semanas_gestacion = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Semanas de gestacion',
    )
    peso_nacimiento_gramos = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Peso al nacer (gramos)',
    )
    tipo_parto = models.CharField(
        max_length=10, choices=TipoParto.choices,
        default=TipoParto.DESCONOCIDO, verbose_name='Tipo de parto',
    )
    complicaciones_embarazo = models.TextField(
        blank=True, verbose_name='Complicaciones del embarazo o parto',
    )

    # --- Desarrollo psicomotor (hitos, en meses) ---
    edad_sosten_cefalico = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Sosten cefalico (meses)',
    )
    edad_sedestacion = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Se sento solo (meses)',
    )
    edad_marcha = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Camino solo (meses)',
    )
    edad_primeras_palabras = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Primeras palabras (meses)',
    )
    observaciones_desarrollo = models.TextField(
        blank=True, verbose_name='Observaciones del desarrollo',
    )

    # --- Otros antecedentes ---
    antecedentes_familiares = models.TextField(
        blank=True,
        verbose_name='Antecedentes familiares',
        help_text='Epilepsia, migrania, trastornos del aprendizaje, etc.',
    )
    antecedentes_morbidos = models.TextField(
        blank=True, verbose_name='Antecedentes morbidos y quirurgicos',
    )
    alergias = models.TextField(blank=True, verbose_name='Alergias')
    medicamentos_actuales = models.TextField(
        blank=True, verbose_name='Medicamentos en uso',
    )

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Antecedentes neurologicos'
        verbose_name_plural = 'Antecedentes neurologicos'

    def __str__(self):
        return f'Antecedentes de {self.paciente.nombre_completo}'


class Diagnostico(models.Model):
    """Diagnostico asociado al paciente. Un paciente puede tener varios."""

    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        RESUELTO = 'RESUELTO', 'Resuelto'
        DESCARTADO = 'DESCARTADO', 'Descartado'

    paciente = models.ForeignKey(
        Paciente, on_delete=models.CASCADE, related_name='diagnosticos',
    )
    codigo_cie10 = models.CharField(
        max_length=10, blank=True, verbose_name='Codigo CIE-10',
        help_text='Ej: G40.9 (epilepsia no especificada)',
    )
    descripcion = models.CharField(max_length=250)
    fecha_diagnostico = models.DateField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
    )
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Diagnostico'
        verbose_name_plural = 'Diagnosticos'
        ordering = ['-fecha_diagnostico']

    def __str__(self):
        return f'{self.descripcion} - {self.paciente.nombre_completo}'


class Atencion(models.Model):
    """
    Una consulta atendida. Es la 'evolucion' de la ficha clinica:
    cada vez que la doctora atiende al nino/a se crea un registro aqui.
    """

    paciente = models.ForeignKey(
        Paciente, on_delete=models.PROTECT, related_name='atenciones',
    )
    profesional = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='atenciones',
    )
    cita = models.OneToOneField(
        'agenda.Cita', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='atencion',
    )
    fecha = models.DateTimeField(verbose_name='Fecha de la atencion')
    tipo_atencion = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Disciplina o servicio',
        help_text='Ej: Neurologia, psicologia, fonoaudiologia.',
    )

    motivo_consulta = models.TextField(verbose_name='Motivo de consulta')
    anamnesis = models.TextField(
        blank=True, verbose_name='Anamnesis',
        help_text='Relato del tutor sobre lo que ocurre.',
    )
    examen_fisico = models.TextField(blank=True, verbose_name='Examen fisico y neurologico')

    peso_kg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Peso (kg)',
    )
    talla_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Talla (cm)',
    )
    perimetro_cefalico_cm = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        verbose_name='Perimetro cefalico (cm)',
    )

    impresion_diagnostica = models.TextField(blank=True, verbose_name='Impresion diagnostica')
    indicaciones = models.TextField(blank=True, verbose_name='Indicaciones y tratamiento')
    examenes_solicitados = models.TextField(
        blank=True, verbose_name='Examenes solicitados',
        help_text='Ej: EEG, resonancia, evaluacion fonoaudiologica.',
    )
    derivaciones = models.TextField(blank=True, verbose_name='Derivaciones')
    proximo_control = models.CharField(
        max_length=100, blank=True, verbose_name='Proximo control',
        help_text='Ej: en 3 meses',
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Atencion'
        verbose_name_plural = 'Atenciones'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.paciente.nombre_completo} - {self.fecha:%d/%m/%Y}'
