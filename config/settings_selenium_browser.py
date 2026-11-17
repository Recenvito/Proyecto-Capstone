"""Configuración E2E de navegador: base aislada y Webpay desactivado."""

from .settings_selenium import *  # noqa: F403

PORTAL_WEBPAY_ACTIVO = False  # noqa: F405
