from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """
    Usuario del sistema. Hereda de AbstractUser (que ya trae username,
    password, nombre, email, etc.) y le agregamos el rol y el RUT.

    Los roles definen que puede ver y hacer cada persona:
      - MEDICO:     ve y escribe fichas clinicas, ve su agenda.
      - SECRETARIA: agenda horas y administra pacientes, NO ve la ficha clinica.
      - ADMIN:      administra el sistema completo.
    """

    class Rol(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrador'
        MEDICO = 'MEDICO', 'Medico'
        SECRETARIA = 'SECRETARIA', 'Secretaria'

    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.SECRETARIA,
        verbose_name='Rol',
    )
    rut = models.CharField(
        max_length=12,
        blank=True,
        verbose_name='RUT',
        help_text='Formato 12345678-9',
    )
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Telefono')

    # Solo aplica a los medicos
    especialidad = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Especialidad',
        help_text='Ej: Neurologia infantil',
    )
    registro_superintendencia = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='N. registro Superintendencia de Salud',
    )

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['first_name', 'last_name']

    def __str__(self):
        nombre = self.get_full_name() or self.username
        return f'{nombre} ({self.get_rol_display()})'

    @property
    def es_medico(self):
        return self.rol == self.Rol.MEDICO

    @property
    def es_secretaria(self):
        return self.rol == self.Rol.SECRETARIA

    @property
    def puede_ver_ficha_clinica(self):
        """Solo el personal medico accede al contenido clinico."""
        return self.rol in (self.Rol.MEDICO, self.Rol.ADMIN)
