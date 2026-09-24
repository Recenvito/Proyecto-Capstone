"""Rutas principales del sistema."""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.shortcuts import render
from django.urls import include, path

from usuarios import views as usuarios_views


def acceso_denegado(request, exception=None):
  return render(
    request,
    '403.html',
    {'exception': exception},
    status=403,
  )


handler403 = 'config.urls.acceso_denegado'


urlpatterns = [
  # Panel de administracion de Django
  path('admin/', admin.site.urls),

  # Autenticacion
  path(
    'login/',
    usuarios_views.LoginAuditoriaView.as_view(),
    name='login',
  ),

  path('logout/', usuarios_views.LogoutAuditoriaView.as_view(), name='logout'),

  # Recuperacion de contraseña
  path(
    'password-reset/',
    auth_views.PasswordResetView.as_view(
      template_name='registration/password_reset_form.html'
    ),
    name='password_reset',
  ),

  path(
    'password-reset/done/',
    auth_views.PasswordResetDoneView.as_view(
      template_name='registration/password_reset_done.html'
    ),
    name='password_reset_done',
  ),

  path(
    'reset/<uidb64>/<token>/',
    auth_views.PasswordResetConfirmView.as_view(
      template_name='registration/password_reset_confirm.html'
    ),
    name='password_reset_confirm',
  ),

  path(
    'reset/done/',
    auth_views.PasswordResetCompleteView.as_view(
      template_name='registration/password_reset_complete.html'
    ),
    name='password_reset_complete',
  ),

  # Pantalla principal
  path('', usuarios_views.inicio, name='inicio'),

  # Modulos
  path('pacientes/', include('pacientes.urls')),
  path('agenda/', include('agenda.urls')),
]