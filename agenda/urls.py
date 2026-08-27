from django.urls import path

from . import views

app_name = 'agenda'

urlpatterns = [
    path('', views.calendario, name='calendario'),
    path('agendar/', views.agendar, name='agendar'),
    path('cita/<int:pk>/estado/', views.cambiar_estado, name='cambiar_estado'),
]
