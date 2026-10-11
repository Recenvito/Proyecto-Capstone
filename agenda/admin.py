from django.contrib import admin

from .models import Bloqueo, Cita, Disponibilidad, PagoCita, TarifaServicio


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'paciente', 'profesional', 'tipo', 'estado')
    list_filter = ('estado', 'tipo', 'profesional', 'fecha_hora')
    search_fields = ('paciente__rut', 'paciente__nombres', 'paciente__apellido_paterno')
    date_hierarchy = 'fecha_hora'
    autocomplete_fields = ('paciente',)
    list_editable = ('estado',)


@admin.register(Disponibilidad)
class DisponibilidadAdmin(admin.ModelAdmin):
    list_display = ('profesional', 'dia_semana', 'hora_inicio', 'hora_fin',
                    'duracion_cita_minutos', 'lugar', 'activo')
    list_filter = ('profesional', 'dia_semana', 'activo')


@admin.register(Bloqueo)
class BloqueoAdmin(admin.ModelAdmin):
    list_display = ('profesional', 'inicio', 'fin', 'motivo')
    list_filter = ('profesional',)


@admin.register(TarifaServicio)
class TarifaServicioAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'monto_clp', 'activa', 'actualizada_en')
    list_filter = ('activa',)


@admin.register(PagoCita)
class PagoCitaAdmin(admin.ModelAdmin):
    list_display = ('cita', 'tutor', 'metodo', 'estado', 'monto_clp', 'creado_en')
    list_filter = ('metodo', 'estado', 'creado_en')
    search_fields = ('orden_compra', 'cita__paciente__rut', 'tutor__email')
    readonly_fields = (
        'cita', 'tutor', 'metodo', 'estado', 'monto_clp', 'orden_compra', 'sesion_id',
        'token_transbank', 'codigo_autorizacion', 'expira_en', 'creado_en', 'actualizado_en',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    actions = ('registrar_pagos_presenciales',)

    @admin.action(description='Registrar como pagadas las citas cobradas en clínica')
    def registrar_pagos_presenciales(self, request, queryset):
        from django.db import transaction
        from usuarios.models import Auditoria

        confirmados = 0
        for seleccionado in queryset:
            with transaction.atomic():
                pago = PagoCita.objects.select_for_update().select_related('cita').get(pk=seleccionado.pk)
                if pago.metodo != PagoCita.Metodo.PRESENCIAL or pago.estado != PagoCita.Estado.POR_PAGAR:
                    continue
                pago.estado = PagoCita.Estado.PAGADA
                pago.save(update_fields=('estado', 'actualizado_en'))
                Cita.objects.filter(pk=pago.cita_id, estado=Cita.Estado.AGENDADA).update(
                    estado=Cita.Estado.CONFIRMADA,
                )
                Auditoria.objects.create(
                    usuario=request.user, accion=Auditoria.Accion.MODIFICAR,
                    modelo='Pago de cita', registro_id=pago.pk,
                    ip=request.META.get('REMOTE_ADDR'),
                    detalle={'evento': 'Pago presencial registrado', 'cita_id': pago.cita_id},
                )
                confirmados += 1
            from portal.emails import enviar_comprobante_pago
            enviar_comprobante_pago(pago)
        self.message_user(request, f'Se registraron {confirmados} pago(s) presencial(es).')
