"""Rutas principales del sistema."""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from usuarios import views as usuarios_views

urlpatterns = [
    # Panel de administracion de Django
    path('admin/', admin.site.urls),

    # Inicio de sesion
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Pantalla principal
    path('', usuarios_views.inicio, name='inicio'),

    # Modulos
    path('pacientes/', include('pacientes.urls')),
    path('agenda/', include('agenda.urls')),
]
