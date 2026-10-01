from django import forms
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    UserChangeForm,
)

from .models import Usuario


class CorreoRecuperacionMixin:
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
