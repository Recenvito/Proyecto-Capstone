from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from config.validators import normalizar_rut, normalizar_telefono, validar_nombre_persona, validar_rut_chileno
from .models import AntecedentesNeurologicos, Atencion, Diagnostico, Paciente, Tutor


class BaseForm(forms.ModelForm):
    """Le pone la clase CSS a todos los campos para que se vean bien."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ayudas = {
            'direccion': 'Calle, número y departamento si corresponde.',
            'comuna': 'Comuna de residencia actual.',
            'colegio': 'Establecimiento educacional actual, si corresponde.',
            'curso': 'Nivel o curso actual.',
            'derivado_por': 'Profesional o institución que derivó al paciente.',
            'semanas_gestacion': 'Semanas completas al nacimiento; rango de referencia 20 a 45.',
            'peso_nacimiento_gramos': 'Peso al nacer expresado en gramos.',
            'complicaciones_embarazo': 'Describe complicaciones conocidas; evita abreviaturas no estandarizadas.',
            'edad_sosten_cefalico': 'Edad en meses; rango 0 a 240.',
            'edad_sedestacion': 'Edad en meses; rango 0 a 240.',
            'edad_marcha': 'Edad en meses; rango 0 a 240.',
            'edad_primeras_palabras': 'Edad en meses; rango 0 a 240.',
            'observaciones_desarrollo': 'Describe el hito observado y la edad aproximada.',
            'antecedentes_familiares': 'Indica parentesco y diagnóstico familiar conocido.',
            'antecedentes_morbidos': 'Antecedentes médicos y quirúrgicos relevantes.',
            'alergias': 'Nombre de la sustancia y reacción, si se conoce.',
            'medicamentos_actuales': 'Nombre, dosis y frecuencia según la indicación vigente.',
        }
        for nombre, campo in self.fields.items():
            widget = campo.widget
            if not campo.help_text and nombre in ayudas:
                campo.help_text = ayudas[nombre]
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'check')
            else:
                widget.attrs.setdefault('class', 'input')
            if nombre == 'rut':
                widget.attrs.setdefault('placeholder', '12.345.678-5')
                widget.attrs.setdefault('autocomplete', 'off')
            elif nombre in {'nombre_completo', 'nombres', 'apellido_paterno', 'apellido_materno'}:
                widget.attrs.setdefault('autocomplete', 'name')
            elif nombre == 'telefono':
                widget.attrs.update({'type': 'tel', 'inputmode': 'tel', 'autocomplete': 'tel'})
                widget.attrs.setdefault('placeholder', '+56 9 1234 5678')
            elif nombre == 'email':
                widget.attrs.update({'type': 'email', 'autocomplete': 'email'})
            elif nombre in {'fecha_nacimiento', 'fecha_diagnostico'}:
                widget.attrs.setdefault('max', timezone.localdate().isoformat())


class PacienteForm(BaseForm):
    class Meta:
        model = Paciente
        fields = [
            'rut', 'nombres', 'apellido_paterno', 'apellido_materno',
            'fecha_nacimiento', 'sexo', 'prevision', 'direccion', 'comuna',
            'colegio', 'curso', 'derivado_por',
        ]
        help_texts = {
            'rut': 'RUT chileno con dígito verificador, por ejemplo 12.345.678-5. Si no tiene, ingresa su pasaporte.',
            'nombres': 'Ingresa los nombres tal como aparecen en el documento de identidad.',
            'apellido_paterno': 'Solo letras, espacios, apóstrofes, puntos o guiones.',
            'apellido_materno': 'Opcional. Solo letras, espacios, apóstrofes, puntos o guiones.',
            'fecha_nacimiento': 'No puede ser una fecha futura.',
            'direccion': 'Calle y número; agrega departamento si corresponde.',
            'comuna': 'Comuna de residencia actual.',
            'curso': 'Nivel o curso actual. Déjalo vacío si no corresponde.',
        }
        widgets = {
            'fecha_nacimiento': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def clean_rut(self):
        original = self.cleaned_data['rut']
        rut = normalizar_rut(original)
        rut = rut if '-' in rut or not rut.isdigit() else f'{rut[:-1]}-{rut[-1]}'
        if self.instance.pk and rut == normalizar_rut(self.instance.rut):
            return rut
        validar_rut_chileno(rut)
        return rut

    def clean_nombres(self):
        valor = self.cleaned_data['nombres'].strip()
        validar_nombre_persona(valor)
        return valor

    def clean_apellido_paterno(self):
        valor = self.cleaned_data['apellido_paterno'].strip()
        validar_nombre_persona(valor)
        return valor

    def clean_apellido_materno(self):
        valor = self.cleaned_data['apellido_materno'].strip()
        validar_nombre_persona(valor)
        return valor

    def clean_fecha_nacimiento(self):
        valor = self.cleaned_data['fecha_nacimiento']
        if valor > timezone.localdate():
            raise forms.ValidationError('La fecha de nacimiento no puede ser futura.')
        if (timezone.localdate() - valor).days > 120 * 366:
            raise forms.ValidationError('Revisa la fecha; la edad supera 120 años.')
        return valor


class PacienteAdminForm(PacienteForm):
    class Meta(PacienteForm.Meta):
        fields = '__all__'


class TutorForm(BaseForm):
    class Meta:
        model = Tutor
        fields = ['nombre_completo', 'rut', 'parentesco', 'telefono', 'email', 'es_principal']
        help_texts = {
            'nombre_completo': 'Nombre y apellidos del tutor, solo con caracteres propios de un nombre.',
            'rut': 'RUT con dígito verificador o pasaporte.',
            'telefono': 'Entre 8 y 15 dígitos; se aceptan +, espacios, paréntesis y guiones.',
            'email': 'Correo válido para contactar al tutor.',
        }

    def clean_nombre_completo(self):
        valor = self.cleaned_data['nombre_completo'].strip()
        validar_nombre_persona(valor)
        return valor

    def clean_rut(self):
        valor = normalizar_rut(self.cleaned_data['rut'])
        if self.instance.pk and valor == normalizar_rut(self.instance.rut):
            return valor
        validar_rut_chileno(valor)
        return valor

    def clean_telefono(self):
        return normalizar_telefono(self.cleaned_data['telefono'])


# Permite editar varios tutores en la misma pagina del paciente
TutorFormSet = inlineformset_factory(
    Paciente, Tutor,
    form=TutorForm,
    fields=['nombre_completo', 'rut', 'parentesco', 'telefono', 'email', 'es_principal'],
    extra=1, can_delete=True,
)


class AntecedentesForm(BaseForm):
    class Meta:
        model = AntecedentesNeurologicos
        exclude = ['paciente']
        help_texts = {
            'semanas_gestacion': 'Semanas completas al momento del nacimiento; normalmente entre 20 y 45.',
            'peso_nacimiento_gramos': 'Peso al nacer en gramos.',
            'edad_sosten_cefalico': 'Edad en meses; déjalo vacío si no hay información.',
            'edad_sedestacion': 'Edad en meses; déjalo vacío si no hay información.',
            'edad_marcha': 'Edad en meses; déjalo vacío si no hay información.',
            'edad_primeras_palabras': 'Edad en meses; déjalo vacío si no hay información.',
            'alergias': 'Indica alergias conocidas y la reacción, si se conoce.',
            'medicamentos_actuales': 'Nombre, dosis y frecuencia según el tratamiento vigente.',
        }

    def clean(self):
        datos = super().clean()
        rangos = {
            'semanas_gestacion': (20, 45),
            'peso_nacimiento_gramos': (500, 6500),
            'edad_sosten_cefalico': (0, 240),
            'edad_sedestacion': (0, 240),
            'edad_marcha': (0, 240),
            'edad_primeras_palabras': (0, 240),
        }
        for campo, (minimo, maximo) in rangos.items():
            valor = datos.get(campo)
            if valor is not None and not minimo <= valor <= maximo:
                self.add_error(campo, f'Ingresa un valor entre {minimo} y {maximo}.')
        return datos


class AtencionForm(BaseForm):
    tipo_atencion = forms.CharField(
        label='Disciplina o servicio',
        max_length=100,
        required=True,
        help_text='Indica la disciplina o servicio de esta atencion.',
    )

    class Meta:
        model = Atencion
        fields = [
            'fecha', 'tipo_atencion', 'motivo_consulta', 'anamnesis', 'examen_fisico',
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
        help_texts = {
            'fecha': 'Fecha y hora en que se realizó la atención; no puede ser futura.',
            'motivo_consulta': 'Motivo principal informado para esta atención.',
            'anamnesis': 'Relato clínico relevante de la atención.',
            'examen_fisico': 'Hallazgos observados durante el examen.',
            'peso_kg': 'Usa kilogramos, por ejemplo 18,50.',
            'talla_cm': 'Usa centímetros, por ejemplo 112,5.',
            'perimetro_cefalico_cm': 'Usa centímetros, si corresponde.',
            'impresion_diagnostica': 'Diagnóstico o hipótesis clínica de esta atención.',
            'indicaciones': 'Tratamiento o indicaciones acordadas.',
            'examenes_solicitados': 'Exámenes indicados y su prioridad, si corresponde.',
            'derivaciones': 'Profesional o servicio al que se deriva.',
            'proximo_control': 'Plazo sugerido para el siguiente control.',
        }

    def clean_fecha(self):
        valor = self.cleaned_data['fecha']
        if timezone.is_naive(valor):
            valor = timezone.make_aware(valor, timezone.get_current_timezone())
        if valor > timezone.now():
            raise forms.ValidationError('La fecha de una atención clínica no puede ser futura.')
        return valor

    def clean(self):
        datos = super().clean()
        limites = {
            'peso_kg': (0.2, 300),
            'talla_cm': (20, 250),
            'perimetro_cefalico_cm': (20, 80),
        }
        for campo, (minimo, maximo) in limites.items():
            valor = datos.get(campo)
            if valor is not None and not minimo <= valor <= maximo:
                self.add_error(campo, f'El valor debe estar entre {minimo} y {maximo}.')
        return datos


class AtencionAdminForm(AtencionForm):
    class Meta(AtencionForm.Meta):
        fields = [
            'paciente', 'profesional', 'cita', 'fecha', 'tipo_atencion',
            'motivo_consulta', 'anamnesis', 'examen_fisico', 'peso_kg',
            'talla_cm', 'perimetro_cefalico_cm', 'impresion_diagnostica',
            'indicaciones', 'examenes_solicitados', 'derivaciones', 'proximo_control',
        ]


class DiagnosticoForm(BaseForm):
    class Meta:
        model = Diagnostico
        fields = ['descripcion', 'codigo_cie10', 'fecha_diagnostico', 'estado', 'notas']
        widgets = {
            'fecha_diagnostico': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'notas': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {
            'descripcion': 'Diagnóstico o impresión clínica en lenguaje claro.',
            'codigo_cie10': 'Opcional. Formato, por ejemplo G40.9.',
            'fecha_diagnostico': 'No puede ser una fecha futura.',
            'estado': 'Selecciona el estado clínico actual del diagnóstico.',
            'notas': 'Antecedentes relevantes para este diagnóstico; evita repetir datos innecesarios.',
        }

    def clean_descripcion(self):
        return self.cleaned_data['descripcion'].strip()

    def clean_codigo_cie10(self):
        import re
        codigo = self.cleaned_data['codigo_cie10'].strip().upper()
        if codigo and not re.fullmatch(r'[A-Z][0-9]{2}(?:\.[0-9A-Z]{1,4})?', codigo):
            raise forms.ValidationError('Usa un código CIE-10 como G40.9 o F84.0.')
        return codigo

    def clean_fecha_diagnostico(self):
        fecha = self.cleaned_data['fecha_diagnostico']
        if fecha > timezone.localdate():
            raise forms.ValidationError('La fecha del diagnóstico no puede ser futura.')
        return fecha


class DiagnosticoAdminForm(DiagnosticoForm):
    class Meta(DiagnosticoForm.Meta):
        fields = '__all__'
