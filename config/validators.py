import re
import unicodedata

from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password
from django.utils.translation import gettext_lazy as _


def normalizar_rut(valor):
    return re.sub(r'[.\s]', '', valor).upper()


def validar_rut_chileno(valor):
    limpio = normalizar_rut(valor)
    if not limpio:
        return
    if not re.fullmatch(r'\d{1,8}-[0-9K]', limpio):
        # Se admite pasaporte alfanumerico porque el formulario lo ofrece como
        # identificador alternativo cuando el paciente no tiene RUT chileno.
        if re.fullmatch(r'[A-Z][A-Z0-9-]{4,19}', limpio):
            return
        raise ValidationError(_('Ingresa un RUT válido (12.345.678-5) o un pasaporte.'), code='rut_invalido')

    cuerpo, digito = limpio.split('-')
    suma = 0
    factor = 2
    for numero in reversed(cuerpo):
        suma += int(numero) * factor
        factor = 2 if factor == 7 else factor + 1
    calculado = 11 - (suma % 11)
    esperado = '0' if calculado == 11 else 'K' if calculado == 10 else str(calculado)
    if digito != esperado:
        raise ValidationError(_('El dígito verificador del RUT no es válido.'), code='rut_invalido')


def validar_nombre_persona(valor):
    if not valor:
        return
    for caracter in valor:
        categoria = unicodedata.category(caracter)
        if categoria.startswith('L') or categoria.startswith('M'):
            continue
        if caracter in " '-’.":
            continue
        raise ValidationError(
            _('Usa solo letras, espacios, apóstrofes, puntos o guiones.'),
            code='nombre_invalido',
        )


def normalizar_telefono(valor, requerido=True):
    texto = (valor or '').strip()
    if not texto and not requerido:
        return ''
    if not texto or not re.fullmatch(r'\+?[0-9\s().-]+', texto):
        raise ValidationError(_('Ingresa un teléfono con números y, opcionalmente, +, espacios, paréntesis o guiones.'), code='telefono_invalido')
    prefijo = '+' if texto.startswith('+') else ''
    digitos = re.sub(r'\D', '', texto)
    if not 8 <= len(digitos) <= 15:
        raise ValidationError(_('El teléfono debe contener entre 8 y 15 dígitos.'), code='telefono_invalido')
    return prefijo + digitos


class ValidadorComplejidadContrasena:
    def validate(self, password, user=None):
        if not any(caracter.isupper() for caracter in password):
            raise ValidationError(_('La contraseña debe incluir al menos una letra mayúscula.'), code='sin_mayuscula')
        if not any(caracter.islower() for caracter in password):
            raise ValidationError(_('La contraseña debe incluir al menos una letra minúscula.'), code='sin_minuscula')
        if not any(caracter.isdigit() for caracter in password):
            raise ValidationError(_('La contraseña debe incluir al menos un número.'), code='sin_numero')
        if not any(not caracter.isalnum() and not caracter.isspace() for caracter in password):
            raise ValidationError(_('La contraseña debe incluir al menos un carácter especial.'), code='sin_especial')

    def get_help_text(self):
        return _('Usa al menos 12 caracteres, con mayúscula, minúscula, número y carácter especial.')


class ValidadorHistorialContrasenas:
    def validate(self, password, user=None):
        if user is None or not user.pk:
            return
        if user.has_usable_password() and user.check_password(password):
            raise ValidationError(_('No puedes reutilizar tu contraseña actual.'), code='contrasena_actual')
        Historial = user._meta.apps.get_model('usuarios', 'HistorialContrasena')
        recientes = Historial.objects.filter(usuario=user).order_by('-fecha_cambio', '-pk')[:4]
        if any(check_password(password, registro.password_hash) for registro in recientes):
            raise ValidationError(_('No puedes reutilizar ninguna de tus últimas 5 contraseñas.'), code='contrasena_reutilizada')

    def get_help_text(self):
        return _('No se puede repetir ninguna de las últimas 5 contraseñas.')
