from django.contrib import admin
from usuarios.models import Auditoria
from .forms import AtencionAdminForm, DiagnosticoAdminForm, PacienteAdminForm, TutorForm
from .models import (
    AntecedentesNeurologicos, AsignacionProfesional, Atencion, Diagnostico,
    DocumentoPaciente, Paciente, SolicitudAccesoTutor, Tutor,
)


class TutorInline(admin.TabularInline):
    """Permite editar los tutores dentro de la ficha del paciente."""
    model = Tutor
    form = TutorForm
    extra = 1
    exclude = ('usuario',)


@admin.register(DocumentoPaciente)
class DocumentoPacienteAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'paciente', 'fecha_documento', 'publicado', 'subido_por')
    list_filter = ('publicado', 'fecha_documento')
    search_fields = ('titulo', 'paciente__rut', 'paciente__nombres', 'paciente__apellido_paterno')
    autocomplete_fields = ('paciente',)
    readonly_fields = ('creado_en', 'subido_por')
    fields = ('paciente', 'titulo', 'descripcion', 'archivo', 'fecha_documento', 'publicado',
              'subido_por', 'creado_en')

    def save_model(self, request, obj, form, change):
        if not obj.subido_por_id:
            obj.subido_por = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        rol = getattr(request.user, 'rol', None)
        if rol == 'MEDICO':
            return queryset.filter(
                paciente__asignaciones_profesionales__profesional=request.user,
                paciente__asignaciones_profesionales__activa=True,
            ).distinct()
        if rol != 'ADMIN':
            return queryset.none()
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'paciente' and getattr(request.user, 'rol', None) == 'MEDICO':
            kwargs['queryset'] = Paciente.objects.filter(
                asignaciones_profesionales__profesional=request.user,
                asignaciones_profesionales__activa=True,
                activo=True,
            ).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_module_permission(self, request):
        return getattr(request.user, 'rol', None) in ('ADMIN', 'MEDICO') and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        if getattr(request.user, 'rol', None) not in ('ADMIN', 'MEDICO'):
            return False
        if obj is not None and getattr(request.user, 'rol', None) == 'MEDICO':
            return self.get_queryset(request).filter(pk=obj.pk).exists()
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if getattr(request.user, 'rol', None) not in ('ADMIN', 'MEDICO'):
            return False
        if obj is not None and getattr(request.user, 'rol', None) == 'MEDICO':
            return self.get_queryset(request).filter(pk=obj.pk).exists()
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        return getattr(request.user, 'rol', None) in ('ADMIN', 'MEDICO') and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SolicitudAccesoTutor)
class SolicitudAccesoTutorAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'paciente_rut', 'parentesco', 'estado', 'creada_en', 'revisada_por')
    list_filter = ('estado', 'parentesco', 'creada_en')
    search_fields = ('usuario__email', 'usuario__rut', 'paciente_rut')
    readonly_fields = ('usuario', 'paciente_rut', 'parentesco', 'creada_en', 'revisada_en', 'revisada_por')
    actions = ('aprobar_vinculos', 'rechazar_solicitudes')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.action(description='Aprobar vínculos después de verificar identidad y parentesco')
    def aprobar_vinculos(self, request, queryset):
        from django.db import transaction
        from django.utils import timezone
        from config.validators import normalizar_rut

        aprobadas = 0
        for solicitud in queryset.select_related('usuario'):
            if solicitud.estado != SolicitudAccesoTutor.Estado.PENDIENTE:
                continue
            usuario = solicitud.usuario
            if not (usuario.is_active and usuario.correo_verificado and usuario.telefono_verificado):
                self.message_user(
                    request,
                    f'No se aprobó la solicitud de {usuario.email}: falta verificar correo/teléfono.',
                    level='error',
                )
                continue
            paciente = Paciente.objects.filter(rut=normalizar_rut(solicitud.paciente_rut), activo=True).first()
            if paciente is None:
                self.message_user(
                    request,
                    f'No se encontró una ficha activa para una solicitud de {usuario.email}.',
                    level='error',
                )
                continue
            with transaction.atomic():
                tutor = Tutor.objects.filter(paciente=paciente, rut=normalizar_rut(usuario.rut)).first()
                if tutor and tutor.usuario_id not in (None, usuario.pk):
                    self.message_user(
                        request,
                        f'La ficha solicitada por {usuario.email} ya está vinculada a otra cuenta.',
                        level='error',
                    )
                    continue
                if tutor is None:
                    tutor = Tutor(paciente=paciente, rut=normalizar_rut(usuario.rut))
                tutor.usuario = usuario
                tutor.nombre_completo = usuario.get_full_name() or usuario.username
                tutor.parentesco = solicitud.parentesco
                tutor.telefono = usuario.telefono
                tutor.email = usuario.email
                tutor.save()
                solicitud.estado = SolicitudAccesoTutor.Estado.APROBADA
                solicitud.revisada_por = request.user
                solicitud.revisada_en = timezone.now()
                solicitud.save(update_fields=('estado', 'revisada_por', 'revisada_en'))
                aprobadas += 1
        if aprobadas:
            self.message_user(request, f'Se aprobaron {aprobadas} vínculo(s).')

    @admin.action(description='Rechazar solicitudes seleccionadas')
    def rechazar_solicitudes(self, request, queryset):
        from django.utils import timezone
        actualizadas = queryset.filter(estado=SolicitudAccesoTutor.Estado.PENDIENTE).update(
            estado=SolicitudAccesoTutor.Estado.RECHAZADA,
            revisada_por=request.user,
            revisada_en=timezone.now(),
        )
        self.message_user(request, f'Se rechazaron {actualizadas} solicitud(es).')


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
