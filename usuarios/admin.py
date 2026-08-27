from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


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
