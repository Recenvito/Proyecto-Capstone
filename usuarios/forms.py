from django import forms
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    UserChangeForm,
)
from config.validators import normalizar_rut, normalizar_telefono, validar_nombre_persona, validar_rut_chileno

from .models import Usuario


class CorreoRecuperacionMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ayudas = {
            'email': 'Ingresa una dirección válida y única; se usa para recuperar la cuenta.',
            'rut': 'RUT con dígito verificador o pasaporte si corresponde.',
            'telefono': 'Entre 8 y 15 dígitos; se aceptan +, espacios, paréntesis y guiones.',
            'profesion': 'Obligatoria para cuentas con rol Médico; por ejemplo psicología o medicina.',
            'especialidad': 'Área clínica específica, si corresponde.',
            'registro_superintendencia': 'Número de registro profesional, si corresponde.',
        }
        for nombre, campo in self.fields.items():
            if not campo.help_text and nombre in ayudas:
                campo.help_text = ayudas[nombre]
            if nombre == 'rut':
                campo.widget.attrs.setdefault('placeholder', '12.345.678-5')
            elif nombre == 'telefono':
                campo.widget.attrs.update({'type': 'tel', 'inputmode': 'tel', 'autocomplete': 'tel'})
                campo.widget.attrs.setdefault('placeholder', '+56 9 1234 5678')
            elif nombre == 'email':
                campo.widget.attrs.update({'type': 'email', 'autocomplete': 'email'})

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('rol') == Usuario.Rol.MEDICO and not cleaned_data.get('profesion', '').strip():
            self.add_error('profesion', 'Indica la profesion para las cuentas con rol Medico.')
        return cleaned_data

    def clean_rut(self):
        rut = normalizar_rut(self.cleaned_data.get('rut', ''))
        if self.instance.pk and rut == normalizar_rut(self.instance.rut):
            return rut
        validar_rut_chileno(rut)
        return rut

    def clean_telefono(self):
        return normalizar_telefono(self.cleaned_data.get('telefono', ''), requerido=False)

    def clean_first_name(self):
        valor = self.cleaned_data.get('first_name', '').strip()
        validar_nombre_persona(valor)
        return valor

    def clean_last_name(self):
        valor = self.cleaned_data.get('last_name', '').strip()
        validar_nombre_persona(valor)
        return valor

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        coincidencias = Usuario.objects.filter(email__iexact=email)
        if self.instance.pk:
            coincidencias = coincidencias.exclude(pk=self.instance.pk)
        if coincidencias.exists():
            raise forms.ValidationError(
                'Este correo ya está asociado a otra cuenta. Usa un correo único.'
            )
        return email


class UsuarioCreationForm(CorreoRecuperacionMixin, AdminUserCreationForm):
    """Exige un correo de recuperación al crear una cuenta desde el admin."""

    email = forms.EmailField(required=True, label='Correo electrónico')

    class Meta(AdminUserCreationForm.Meta):
        model = Usuario
        fields = ('username', 'email')


class UsuarioChangeForm(CorreoRecuperacionMixin, UserChangeForm):
    """Evita dejar cuentas sin un correo para recuperar su contraseña."""

    email = forms.EmailField(required=True, label='Correo electrónico')

    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = '__all__'


class PerfilUsuarioForm(CorreoRecuperacionMixin, forms.ModelForm):
    """Datos de perfil que el usuario puede mantener desde la aplicación."""

    class Meta:
        model = Usuario
        fields = (
            'first_name', 'last_name', 'email', 'rut', 'telefono',
            'profesion', 'especialidad', 'registro_superintendencia',
        )
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
            'rut': 'RUT',
            'telefono': 'Teléfono',
            'profesion': 'Profesión',
            'especialidad': 'Especialidad',
            'registro_superintendencia': 'Registro profesional',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        for campo in self.fields.values():
            campo.widget.attrs.setdefault('class', 'input')


class UsuarioEdicionAdminForm(PerfilUsuarioForm):
    """Edición administrativa del perfil, con username fuera del formulario."""

    class Meta(PerfilUsuarioForm.Meta):
        fields = PerfilUsuarioForm.Meta.fields + ('rol',)
        labels = {**PerfilUsuarioForm.Meta.labels, 'rol': 'Rol'}
