from django.contrib import admin
from usuarios.models import Auditoria
from .forms import AtencionAdminForm, DiagnosticoAdminForm, PacienteAdminForm, TutorForm
from .models import AntecedentesNeurologicos, AsignacionProfesional, Atencion, Diagnostico, Paciente, Tutor


class TutorInline(admin.TabularInline):
    """Permite editar los tutores dentro de la ficha del paciente."""
    model = Tutor
    form = TutorForm
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
    form = PacienteAdminForm
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

    def change_view(self, request, object_id, form_url='', extra_context=None):
        response = super().change_view(request, object_id, form_url, extra_context)
        if request.method == 'GET' and response.status_code == 200:
            Auditoria.objects.create(
                usuario=request.user, accion=Auditoria.Accion.CONSULTAR,
                modelo='Paciente', registro_id=int(object_id),
                ip=request.META.get('REMOTE_ADDR'),
                detalle={'evento': 'Acceso a ficha de paciente desde administracion'},
            )
        return response


@admin.register(Atencion)
class AtencionAdmin(admin.ModelAdmin):
    form = AtencionAdminForm
    list_display = ('fecha', 'paciente', 'profesional', 'impresion_diagnostica')
    list_filter = ('profesional', 'fecha')
    search_fields = ('paciente__rut', 'paciente__nombres', 'paciente__apellido_paterno')
    date_hierarchy = 'fecha'
    autocomplete_fields = ('paciente',)

    fieldsets = (
        ('Datos de la atencion', {'fields': ('paciente', 'profesional', 'cita', 'fecha', 'tipo_atencion')}),
        ('Consulta', {'fields': ('motivo_consulta', 'anamnesis', 'examen_fisico')}),
        ('Medidas', {'fields': ('peso_kg', 'talla_cm', 'perimetro_cefalico_cm')}),
        ('Conducta', {'fields': ('impresion_diagnostica', 'indicaciones',
                                 'examenes_solicitados', 'derivaciones', 'proximo_control')}),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if getattr(request.user, 'rol', None) == 'MEDICO':
            queryset = queryset.filter(profesional=request.user)
        return queryset

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if getattr(request.user, 'rol', None) == 'MEDICO' and 'profesional' not in readonly:
            readonly.append('profesional')
        return readonly

    def has_view_permission(self, request, obj=None):
        permitido = super().has_view_permission(request, obj)
        if permitido and obj is not None and getattr(request.user, 'rol', None) == 'MEDICO':
            return obj.profesional_id == request.user.pk
        return permitido

    def has_change_permission(self, request, obj=None):
        permitido = super().has_change_permission(request, obj)
        if permitido and obj is not None and getattr(request.user, 'rol', None) == 'MEDICO':
            return obj.profesional_id == request.user.pk
        return permitido

    def change_view(self, request, object_id, form_url='', extra_context=None):
        response = super().change_view(request, object_id, form_url, extra_context)
        if request.method == 'GET' and response.status_code == 200:
            atencion = self.get_object(request, object_id)
            if atencion:
                Auditoria.objects.create(
                    usuario=request.user, accion=Auditoria.Accion.CONSULTAR,
                    modelo='Atencion', registro_id=atencion.pk,
                    ip=request.META.get('REMOTE_ADDR'),
                    detalle={
                        'evento': 'Acceso a atencion desde administracion',
                        'paciente_id': atencion.paciente_id,
                        'profesional_id': atencion.profesional_id,
                    },
                )
        return response


@admin.register(AsignacionProfesional)
class AsignacionProfesionalAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'profesional', 'fecha_asignacion', 'fecha_termino', 'activa')
    list_filter = ('activa', 'profesional', 'fecha_asignacion', 'fecha_termino')
    search_fields = ('paciente__rut', 'paciente__nombres', 'profesional__username')
    readonly_fields = ('fecha_asignacion', 'fecha_termino')


@admin.register(Diagnostico)
class DiagnosticoAdmin(admin.ModelAdmin):
    form = DiagnosticoAdminForm
    list_display = ('paciente', 'descripcion', 'codigo_cie10', 'fecha_diagnostico', 'estado')
    list_filter = ('estado', 'fecha_diagnostico')
    search_fields = ('descripcion', 'codigo_cie10', 'paciente__nombres')
    autocomplete_fields = ('paciente',)
