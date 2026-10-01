from django import forms
from django.utils import timezone
from datetime import timedelta

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
        help_texts = {
            'paciente': 'Busca un paciente activo. Los médicos solo pueden elegir pacientes asignados a ellos.',
            'profesional': 'Profesional responsable de esta hora.',
            'fecha_hora': 'Selecciona una fecha futura y la hora local de atención.',
            'duracion_minutos': 'Duración en minutos, por ejemplo 30 o 60.',
            'tipo': 'Selecciona el tipo de cita.',
            'motivo': 'Motivo breve de la consulta; evita incluir notas clínicas extensas.',
            'notas_internas': 'Información operativa visible solo para el equipo.',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Solo pacientes activos y usuarios que sean medicos
        self.fields['paciente'].queryset = Paciente.objects.filter(activo=True)
        self.fields['profesional'].queryset = Usuario.objects.filter(
            rol=Usuario.Rol.MEDICO, is_active=True)
        if user and user.es_medico:
            self.fields['paciente'].queryset = self.fields['paciente'].queryset.filter(
                asignaciones_profesionales__profesional=user,
                asignaciones_profesionales__activa=True,
            ).distinct()
            self.fields['profesional'].queryset = Usuario.objects.filter(pk=user.pk)
            self.fields['profesional'].initial = user.pk
            self.fields['profesional'].disabled = True
        for campo in self.fields.values():
            campo.widget.attrs.setdefault('class', 'input')
        self.fields['fecha_hora'].widget.attrs.update({'type': 'datetime-local'})
        self.fields['motivo'].widget.attrs.setdefault('placeholder', 'Ej.: control de seguimiento')
        self.fields['notas_internas'].widget.attrs.setdefault('placeholder', 'Información operativa para el equipo')

    def clean_fecha_hora(self):
        fecha_hora = self.cleaned_data['fecha_hora']
        if fecha_hora <= timezone.now():
            raise forms.ValidationError('La hora de la cita debe estar en el futuro.')
        if fecha_hora > timezone.now() + timedelta(days=365 * 2):
            raise forms.ValidationError('No se pueden agendar citas con más de dos años de anticipación.')
        return fecha_hora
