from django.urls import path

from . import views

app_name = 'pacientes'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nuevo/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/antecedentes/', views.editar_antecedentes, name='antecedentes'),
    path('<int:pk>/atencion/nueva/', views.crear_atencion, name='crear_atencion'),
    path('atencion/<int:pk>/', views.detalle_atencion, name='detalle_atencion'),
]
