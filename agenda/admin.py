from django.contrib import admin

from .models import Bloqueo, Cita, Disponibilidad


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'paciente', 'profesional', 'tipo', 'estado')
    list_filter = ('estado', 'tipo', 'profesional', 'fecha_hora')
    search_fields = ('paciente__rut', 'paciente__nombres', 'paciente__apellido_paterno')
    date_hierarchy = 'fecha_hora'
    autocomplete_fields = ('paciente',)
    list_editable = ('estado',)


@admin.register(Disponibilidad)
class DisponibilidadAdmin(admin.ModelAdmin):
    list_display = ('profesional', 'dia_semana', 'hora_inicio', 'hora_fin',
                    'duracion_cita_minutos', 'lugar', 'activo')
    list_filter = ('profesional', 'dia_semana', 'activo')


@admin.register(Bloqueo)
class BloqueoAdmin(admin.ModelAdmin):
    list_display = ('profesional', 'inicio', 'fin', 'motivo')
    list_filter = ('profesional',)
