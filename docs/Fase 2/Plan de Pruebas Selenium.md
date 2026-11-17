# Plan de pruebas automatizadas de NeuroFicha

## Alcance

La planilla `Casos de Prueba.xls.xlsx` registra los escenarios, los resultados esperados y obtenidos, el estado y la evidencia. Los flujos críticos de usuario se ejecutan con Selenium en Chrome o Edge. Las reglas de negocio y validaciones se verifican además con la suite Django existente. Ambos niveles se ejecutan contra SQLite temporal y datos ficticios; el archivo `.env`, el MySQL de desarrollo, el correo real y los cobros reales no se usan.

Cada prueba de Selenium lleva un ID P-xxx y guarda una captura PNG al terminar, incluso cuando falla una aserción. La ruta predeterminada es `docs/Fase 2/Evidencias Selenium/Ciclo 1/`; los fallos quedan con sufijo `FALLO` o `ERROR`. El registro de defectos se completa solo con defectos reproducidos; no se asignan personas sin confirmación del equipo.

## Preparación en Windows

1. Abrir PowerShell en la carpeta del proyecto:

   ```powershell
   cd C:\Users\TEB\Documents\GitHub\Proyecto-Capstone
   ```

2. Activar el entorno virtual recomendado por el README. Si aún no existe:

   ```powershell
   py -3.13 -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   Selenium Manager localiza el navegador y gestiona el controlador compatible. Chrome y Edge están instalados en el equipo revisado; la primera ejecución puede requerir Internet para descargar el controlador.

3. Ejecutar las comprobaciones y pruebas de backend:

   ```powershell
   python manage.py check --settings=config.settings_selenium
   python manage.py test agenda.tests pacientes.tests portal.tests usuarios.tests --settings=config.settings_selenium
   ```

   La configuración `config.settings_selenium` fuerza una base SQLite de pruebas, correo en memoria y almacenamiento temporal. Las pruebas Django de Webpay sustituyen el cliente por un stub y no contactan la pasarela. No cambia `.env` ni escribe en MySQL.

4. Ejecutar los casos de navegador en Chrome:

   ```powershell
   $env:SELENIUM_BROWSER = 'chrome'
   $env:SELENIUM_HEADLESS = '1'
   python manage.py test tests_e2e --settings=config.settings_selenium_browser --verbosity=2
   ```

   Las capturas se guardan en la carpeta del ciclo. Para ver el navegador durante la ejecución, usar `$env:SELENIUM_HEADLESS = '0'`. La configuración E2E mantiene Webpay desactivado.

5. Repetir en Edge:

   ```powershell
   $env:SELENIUM_BROWSER = 'edge'
   $env:SELENIUM_HEADLESS = '1'
   python manage.py test tests_e2e --settings=config.settings_selenium_browser --verbosity=2
   ```

6. Revisar cada PNG con su mismo ID en la hoja `Casos de Prueba`. Actualizar resultado obtenido y estado según la ejecución. Si aparece un defecto, registrarlo en `Defectos por ciclo`, corregirlo en un ciclo posterior y repetir el caso original y su regresión. No declarar un pago Webpay exitoso desde esta suite: las pruebas de cobro usan simulaciones de Django y la integración del navegador tiene Webpay desactivado.

## Casos de navegador automatizados

| ID | Flujo comprobado |
|---|---|
| P-001 | Portada pública y acceso al inicio de sesión |
| P-002 | Rechazo de credenciales inválidas |
| P-003 | Búsqueda de paciente ficticio por administración |
| P-004 | Acceso clínico de médico asignado |
| P-005 | Bloqueo de ficha para médico no asignado |
| P-006 | Restricción de contenido clínico para secretaría |
| P-007 | Portal familiar y ficha vinculada |
| P-008 | Consulta de cupos y tarifa configurada |
| P-009 | Reserva de hora presencial y persistencia en agenda |
| P-010 | Bloqueo del portal a rutas clínicas |

## Criterios de ciclo

- **Aprobada:** resultado observado coincide con el esperado y existe evidencia.
- **Fallida:** la aplicación respondió, pero incumplió el resultado esperado; crear defecto.
- **Error de ejecución:** la prueba no pudo completar por un error técnico del entorno o del test; clasificar antes de atribuirlo al producto.
- **Pendiente:** caso preparado que aún no se ha ejecutado.
- **No aplica:** el caso no tiene interfaz; conservar el log de pruebas Django como evidencia de backend.

Criticidad del defecto: **Crítica** (exposición de datos clínicos, cobro incorrecto o pérdida grave de datos), **Alta** (bloquea una función principal o el acceso de un rol), **Media** (función con alternativa disponible o error acotado), **Baja** (presentación o detalle sin impacto funcional). El responsable se asigna con el equipo; hasta entonces indicar `Equipo de desarrollo (por asignar)`.
