# Portal de pacientes y tutores — Fase 1

## Flujo entregado

1. El tutor crea una cuenta con RUT, correo, teléfono, contraseña y RUT del paciente solicitado.
2. El sistema envía un enlace de un solo uso para verificar el correo. La pantalla de confirmación requiere una acción explícita y el enlace vence en 24 horas.
3. La ficha no se busca ni se muestra durante el registro. El sistema conserva la solicitud para revisión clínica.
4. Un administrador verifica el teléfono por el proceso de la clínica y marca `Teléfono verificado` en la cuenta. Después aprueba la solicitud desde **Administración → Solicitudes de acceso de tutores**.
5. La aprobación vincula la cuenta con la ficha existente. Si la ficha o el RUT no coinciden, la solicitud no otorga acceso.
6. Una cuenta ya verificada puede solicitar acceso a más fichas desde el portal; cada solicitud se revisa de forma independiente.
7. El tutor busca fechas, profesionales y cupos de las disponibilidades actuales. Una reserva crea una cita en la misma agenda usada por recepción y profesionales, y activa la asignación clínica necesaria para que el profesional pueda acceder a esa ficha.
8. El pago puede quedar para la clínica o iniciarse en Webpay. Una reserva presencial pendiente también puede pagarse después desde **Pagar ahora con Webpay**. La confirmación en línea ocurre solo después de validar la respuesta del servidor (estado, código, monto y orden de compra). Si el intento de pago posterior falla o vence, la cita se mantiene y queda disponible el pago presencial.
9. Se envía al correo de la cuenta que reservó un comprobante de reserva y, al confirmarse el cobro en Webpay o en clínica, un comprobante de pago. Los correos no incluyen datos de tarjeta ni notas clínicas.
10. Administración puede cargar copias PDF en **Administración → Informes para portal de pacientes**; los médicos solo acceden a documentos de pacientes con asignación activa. Solo se muestran y descargan para cuentas con correo y teléfono verificados y con vínculo aprobado a una ficha activa. Cada descarga queda auditada.

## Configuración de precios y Webpay

- Crear una **Tarifa de servicio** por tipo de atención en el panel de administración. No hay precios predeterminados; sin una tarifa activa de ese tipo no se puede reservar.
- El SDK oficial `transbank-sdk` está configurado explícitamente en `TEST`. La aplicación no tiene ruta ni configuración de producción en esta fase.
- `PORTAL_WEBPAY_ACTIVO=1` habilita la opción; para deshabilitarla, usar `0`.
- Si se usan credenciales de integración propias, configurar `TRANSBANK_INTEGRATION_COMMERCE_CODE` y `TRANSBANK_INTEGRATION_API_KEY`. Si se dejan vacías, se usan las constantes públicas de integración del SDK.
- Para correo real se requiere configurar SMTP con `DJANGO_EMAIL_*`; en desarrollo Django usa la consola.
- Los informes publicados se almacenan bajo `MEDIA_ROOT` y se entregan mediante una vista autenticada; no se publica una URL directa al archivo. Se aceptan PDF de hasta 10 MB.

## Límites actuales

- La verificación del correo es automática. La verificación telefónica y de representación legal es una acción manual del personal clínico; no hay proveedor SMS configurado.
- Esta fase vincula tutores con fichas ya existentes. No registra una ficha clínica nueva desde el portal.
- Se exponen los datos administrativos mínimos, las citas vinculadas y las copias PDF que la clínica publique para representantes autorizados. El portal no expone las notas internas de atención.
- Webpay puede probarse en integración, pero no se han cargado credenciales comerciales ni se debe usar para cobros reales.
