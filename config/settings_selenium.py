"""Configuración aislada para pruebas de navegador con datos ficticios."""

from pathlib import Path

from .settings import *  # noqa: F403


_E2E_ROOT = BASE_DIR / 'tmp' / 'selenium'  # noqa: F405
_E2E_ROOT.mkdir(parents=True, exist_ok=True)

# Aunque el archivo .env local configure MySQL, Selenium nunca toca esa base.
DATABASES = {  # noqa: F405
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': _E2E_ROOT / 'neuroficha_selenium.sqlite3',
        'TEST': {'NAME': _E2E_ROOT / 'test_neuroficha_selenium.sqlite3'},
    }
}
MEDIA_ROOT = _E2E_ROOT / 'media'  # noqa: F405
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'  # noqa: F405
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']  # noqa: F405
# Las pruebas Django sustituyen siempre el cliente Webpay con un stub.
PORTAL_WEBPAY_ACTIVO = True  # noqa: F405
ALLOWED_HOSTS = [*ALLOWED_HOSTS, 'testserver', 'localhost', '127.0.0.1']  # noqa: F405

