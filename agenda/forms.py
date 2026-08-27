from django import forms

from pacientes.models import Paciente
from usuarios.models import Usuario

from .models import Cita


class CitaForm(forms.ModelForm):
    class Meta:
        model = Cita
        fields = ['paciente', 'profesional', 'fecha_hora', 'duracion_minutos',
                  'tipo', 'motivo', 'notas_internas']
        widgets = {
            'fecha_hora': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'motivo': forms.Textarea(attrs={'rows': 3}),
            'notas_internas': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo pacientes activos y usuarios que sean medicos
        self.fields['paciente'].queryset = Paciente.objects.filter(activo=True)
        self.fields['profesional'].queryset = Usuario.objects.filter(
            rol=Usuario.Rol.MEDICO, is_active=True)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault('class', 'input')
