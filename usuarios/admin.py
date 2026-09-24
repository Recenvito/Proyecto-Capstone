from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, AuditoriaAcceso, Auditoria


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'rol', 'email', 'is_active')
    list_filter = ('rol', 'is_active', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'rut', 'email')

    # Agregamos nuestros campos a los formularios que ya trae Django
    fieldsets = UserAdmin.fieldsets + (
        ('Datos del sistema', {
            'fields': ('rol', 'rut', 'telefono', 'especialidad', 'registro_superintendencia'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Datos del sistema', {
            'fields': ('rol', 'first_name', 'last_name', 'email', 'rut', 'telefono'),
        }),
    )

@admin.register(AuditoriaAcceso)
class AuditoriaAccesoAdmin(admin.ModelAdmin):
  list_display = ('usuario', 'accion', 'fecha_hora', 'ip')
  list_filter = ('accion', 'fecha_hora')
  search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name', 'ip')
  ordering = ('-fecha_hora',)
  readonly_fields = ('usuario', 'accion', 'fecha_hora', 'ip')

@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
  list_display = (
    'usuario',
    'accion',
    'modelo',
    'registro_id',
    'fecha_hora',
    'ip',
  )
  list_filter = ('accion', 'modelo', 'fecha_hora')
  search_fields = (
    'usuario__username',
    'usuario__first_name',
    'usuario__last_name',
    'modelo',
    'registro_id',
    'ip',
  )
  ordering = ('-fecha_hora',)
  readonly_fields = (
    'usuario',
    'accion',
    'modelo',
    'registro_id',
    'fecha_hora',
    'ip',
    'detalle',
  )