from django.contrib import admin

from .models import AntecedentesNeurologicos, Atencion, Diagnostico, Paciente, Tutor


class TutorInline(admin.TabularInline):
    """Permite editar los tutores dentro de la ficha del paciente."""
    model = Tutor
    extra = 1


class AntecedentesInline(admin.StackedInline):
    model = AntecedentesNeurologicos
    extra = 0
    can_delete = False


class DiagnosticoInline(admin.TabularInline):
    model = Diagnostico
    extra = 0
    fields = ('descripcion', 'codigo_cie10', 'fecha_diagnostico', 'estado')


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ('rut', 'nombre_completo', 'edad_texto', 'prevision', 'activo')
    list_filter = ('activo', 'sexo', 'prevision', 'comuna')
    search_fields = ('rut', 'nombres', 'apellido_paterno', 'apellido_materno')
    date_hierarchy = 'fecha_nacimiento'
    inlines = [TutorInline, AntecedentesInline, DiagnosticoInline]

    fieldsets = (
        ('Identificacion', {
            'fields': ('rut', 'nombres', 'apellido_paterno', 'apellido_materno',
                       'fecha_nacimiento', 'sexo'),
        }),
        ('Contacto y prevision', {
            'fields': ('prevision', 'direccion', 'comuna'),
        }),
        ('Contexto escolar y derivacion', {
            'fields': ('colegio', 'curso', 'derivado_por'),
        }),
        ('Estado', {'fields': ('activo',)}),
    )


@admin.register(Atencion)
class AtencionAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'paciente', 'profesional', 'impresion_diagnostica')
    list_filter = ('profesional', 'fecha')
    search_fields = ('paciente__rut', 'paciente__nombres', 'paciente__apellido_paterno')
    date_hierarchy = 'fecha'
    autocomplete_fields = ('paciente',)

    fieldsets = (
        ('Datos de la atencion', {'fields': ('paciente', 'profesional', 'cita', 'fecha')}),
        ('Consulta', {'fields': ('motivo_consulta', 'anamnesis', 'examen_fisico')}),
        ('Medidas', {'fields': ('peso_kg', 'talla_cm', 'perimetro_cefalico_cm')}),
        ('Conducta', {'fields': ('impresion_diagnostica', 'indicaciones',
                                 'examenes_solicitados', 'derivaciones', 'proximo_control')}),
    )


@admin.register(Diagnostico)
class DiagnosticoAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'descripcion', 'codigo_cie10', 'fecha_diagnostico', 'estado')
    list_filter = ('estado', 'fecha_diagnostico')
    search_fields = ('descripcion', 'codigo_cie10', 'paciente__nombres')
    autocomplete_fields = ('paciente',)
