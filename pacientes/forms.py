from django import forms
from django.forms import inlineformset_factory

from .models import AntecedentesNeurologicos, Atencion, Paciente, Tutor


class BaseForm(forms.ModelForm):
    """Le pone la clase CSS a todos los campos para que se vean bien."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'check')
            else:
                widget.attrs.setdefault('class', 'input')


class PacienteForm(BaseForm):
    class Meta:
        model = Paciente
        fields = [
            'rut', 'nombres', 'apellido_paterno', 'apellido_materno',
            'fecha_nacimiento', 'sexo', 'prevision', 'direccion', 'comuna',
            'colegio', 'curso', 'derivado_por', 'activo',
        ]
        widgets = {
            'fecha_nacimiento': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def clean_rut(self):
        # Normaliza el RUT: sin puntos, en minuscula la K
        rut = self.cleaned_data['rut'].replace('.', '').replace(' ', '').lower()
        if '-' not in rut and len(rut) > 1:
            rut = f'{rut[:-1]}-{rut[-1]}'
        return rut


# Permite editar varios tutores en la misma pagina del paciente
TutorFormSet = inlineformset_factory(
    Paciente, Tutor,
    fields=['nombre_completo', 'rut', 'parentesco', 'telefono', 'email', 'es_principal'],
    extra=1, can_delete=True,
)


class AntecedentesForm(BaseForm):
    class Meta:
        model = AntecedentesNeurologicos
        exclude = ['paciente']


class AtencionForm(BaseForm):
    class Meta:
        model = Atencion
        fields = [
            'fecha', 'motivo_consulta', 'anamnesis', 'examen_fisico',
            'peso_kg', 'talla_cm', 'perimetro_cefalico_cm',
            'impresion_diagnostica', 'indicaciones', 'examenes_solicitados',
            'derivaciones', 'proximo_control',
        ]
        widgets = {
            'fecha': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'motivo_consulta': forms.Textarea(attrs={'rows': 3}),
            'anamnesis': forms.Textarea(attrs={'rows': 5}),
            'examen_fisico': forms.Textarea(attrs={'rows': 5}),
            'impresion_diagnostica': forms.Textarea(attrs={'rows': 3}),
            'indicaciones': forms.Textarea(attrs={'rows': 4}),
            'examenes_solicitados': forms.Textarea(attrs={'rows': 2}),
            'derivaciones': forms.Textarea(attrs={'rows': 2}),
        }
