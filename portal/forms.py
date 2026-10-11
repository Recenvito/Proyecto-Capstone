from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from datetime import timedelta
from django.utils import timezone

from config.validators import (
    normalizar_rut, normalizar_telefono, validar_nombre_persona, validar_rut_chileno,
)
from pacientes.models import Paciente, Tutor
from usuarios.models import Usuario


class RegistroTutorForm(forms.Form):
    rut_tutor = forms.CharField(label='RUT del adulto responsable', max_length=12)
    nombres = forms.CharField(label='Nombres', max_length=150)
    apellidos = forms.CharField(label='Apellidos', max_length=150)
    email = forms.EmailField(label='Correo electrónico')
    telefono = forms.CharField(label='Teléfono de contacto', max_length=20, widget=forms.TextInput(attrs={'type': 'tel'}))
    rut_paciente = forms.CharField(label='RUT del paciente que representas', max_length=12)
    parentesco = forms.ChoiceField(label='Relación con el paciente', choices=Tutor.Parentesco.choices)
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput, min_length=12)
    password2 = forms.CharField(label='Repite la contraseña', widget=forms.PasswordInput, min_length=12)

    def clean_rut_tutor(self):
        rut = normalizar_rut(self.cleaned_data['rut_tutor'])
        validar_rut_chileno(rut)
        if Usuario.objects.filter(rut__iexact=rut).exists():
            raise forms.ValidationError('Este RUT ya está asociado a una cuenta. Contacta a soporte si necesitas recuperarla.')
        return rut

    def clean_rut_paciente(self):
        rut = normalizar_rut(self.cleaned_data['rut_paciente'])
        validar_rut_chileno(rut)
        return rut

    def clean_nombres(self):
        nombre = self.cleaned_data['nombres'].strip()
        validar_nombre_persona(nombre)
        return nombre

    def clean_apellidos(self):
        apellidos = self.cleaned_data['apellidos'].strip()
        validar_nombre_persona(apellidos)
        return apellidos

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Este correo ya está asociado a una cuenta. Inicia sesión o recupera el acceso.')
        return email

    def clean_telefono(self):
        return normalizar_telefono(self.cleaned_data['telefono'])

    def clean(self):
        datos = super().clean()
        password1, password2 = datos.get('password1'), datos.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Las contraseñas no coinciden.')
        if password1:
            usuario = Usuario(
                username='tutor', first_name=datos.get('nombres', ''),
                last_name=datos.get('apellidos', ''), email=datos.get('email', ''),
            )
            try:
                validate_password(password1, usuario)
            except ValidationError as error:
                self.add_error('password1', error)
        return datos


class ReservaCitaForm(forms.Form):
    paciente = forms.ModelChoiceField(queryset=Paciente.objects.none(), label='Paciente')
    profesional = forms.ModelChoiceField(queryset=Usuario.objects.none(), label='Profesional')
    fecha = forms.DateField(label='Fecha', widget=forms.DateInput(attrs={'type': 'date'}))
    hora = forms.DateTimeField(label='Hora', input_formats=['%Y-%m-%dT%H:%M'], widget=forms.HiddenInput())
    tipo = forms.ChoiceField(label='Atención', choices=())
    forma_pago = forms.ChoiceField(
        label='Forma de pago', choices=(('PRESENCIAL', 'Pagar en la clínica'), ('WEBPAY', 'Pagar en línea con Webpay'))
    )
    motivo = forms.CharField(label='Motivo breve de la atención', required=False, max_length=500,
                             widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paciente'].queryset = Paciente.objects.filter(
            activo=True, tutores__usuario=usuario,
        ).distinct().order_by('apellido_paterno', 'nombres')
        self.fields['profesional'].queryset = Usuario.objects.filter(
            rol=Usuario.Rol.MEDICO, is_active=True, disponibilidades__activo=True,
        ).distinct().order_by('first_name', 'last_name')
        from agenda.models import Cita
        self.fields['tipo'].choices = Cita.Tipo.choices
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'input')

    def clean(self):
        datos = super().clean()
        fecha = datos.get('fecha')
        hora = datos.get('hora')
        hoy = timezone.localdate()
        if fecha and not hoy <= fecha <= hoy + timedelta(days=180):
            self.add_error('fecha', 'Elige una fecha dentro de los próximos 180 días.')
        if fecha and hora and fecha != hora.date():
            self.add_error('hora', 'El cupo elegido no corresponde a la fecha seleccionada.')
        return datos


class SolicitudVinculoForm(forms.Form):
    rut_paciente = forms.CharField(label='RUT del paciente', max_length=12)
    parentesco = forms.ChoiceField(label='Relación con el paciente', choices=Tutor.Parentesco.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'input')

    def clean_rut_paciente(self):
        rut = normalizar_rut(self.cleaned_data['rut_paciente'])
        validar_rut_chileno(rut)
        return rut
