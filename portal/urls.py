from django.urls import path

from . import views

app_name = 'portal'

urlpatterns = [
    path('registro/', views.registro, name='registro'),
    path('verificar-correo/<str:token>/', views.verificar_correo, name='verificar_correo'),
    path('', views.inicio, name='inicio'),
    path('vinculos/solicitar/', views.solicitar_vinculo, name='solicitar_vinculo'),
    path('reservar/', views.reservar, name='reservar'),
    path('citas/<int:pk>/pagar/', views.pagar_cita_webpay, name='pagar_cita_webpay'),
    path('informes/<int:pk>/descargar/', views.descargar_documento, name='descargar_documento'),
    path('pago/webpay/retorno/', views.webpay_retorno, name='webpay_retorno'),
]
