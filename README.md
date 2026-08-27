# NeuroFicha — Sistema de agenda y ficha clinica

Proyecto de tesis. Sistema web para digitalizar la consulta de una neurologa infantil:
toma de horas, ficha clinica del paciente, antecedentes del desarrollo y registro de
atenciones.

## Stack

| Area | Herramienta |
|---|---|
| Gestion | Jira |
| Editor | Visual Studio Code |
| Framework | Django 5.2 LTS (Python 3.13) |
| Base de datos | Oracle SQL (SQLite en desarrollo) |
| Versiones | GitHub |
| Prototipado | Canva |

> Sobre por que Python 3.13 / Django 5.2, y donde se aloja Oracle, ver
> [`docs/DECISIONES.md`](docs/DECISIONES.md).

---

## Instalacion

### 1. Instalar Python 3.13

**macOS** (Apple Silicon o Intel):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.13
```

**Windows** — descargar el instalador desde https://www.python.org/downloads/
(marcar la casilla *"Add Python to PATH"* durante la instalacion).

### 2. Crear el entorno virtual e instalar dependencias

**macOS / Linux:**
```bash
python3.13 -m venv venv
./venv/bin/pip install -r requirements.txt
```

**Windows:**
```
py -3.13 -m venv venv
venv\Scripts\pip install -r requirements.txt
```

### 3. Configurar las variables de entorno

```bash
cp .env.ejemplo .env
```

Editar `.env` con las credenciales reales. **El archivo `.env` nunca se sube a GitHub.**

### 4. Crear la base de datos y los datos de prueba

```bash
./venv/bin/python manage.py migrate
./venv/bin/python manage.py shell < crear_datos_demo.py
```

### 5. Levantar el servidor

```bash
./venv/bin/python manage.py runserver
```

Abrir http://localhost:8000

---

## Usuarios de prueba

Solo para desarrollo local. **Nunca usar estas contrasenias en el sistema real.**

| Usuario | Contrasenia | Rol | Acceso |
|---|---|---|---|
| `admin` | `admin123` | Administrador | Todo, incluido el panel `/admin/` |
| `dra.neuro` | `demo1234` | Medico | Agenda + ficha clinica completa |
| `secretaria` | `demo1234` | Secretaria | Agenda y datos de contacto, **sin** ficha clinica |

---

## Estructura del proyecto

```
config/          Configuracion de Django (settings, rutas principales)
usuarios/        Usuarios del sistema y control de acceso por rol
pacientes/       Pacientes, tutores, antecedentes, diagnosticos y atenciones
agenda/          Disponibilidad horaria, bloqueos y citas
templates/       Plantillas HTML
static/css/      Hojas de estilo
docs/            Documentacion y decisiones tecnicas
```

## Modelo de datos

- **Usuario** — con rol: administrador / medico / secretaria.
- **Paciente** — nino o nina atendido. Identificacion, prevision, colegio.
- **Tutor** — madre, padre o apoderado responsable.
- **AntecedentesNeurologicos** — embarazo, parto e hitos del desarrollo psicomotor.
- **Diagnostico** — con codigo CIE-10 y estado.
- **Atencion** — cada consulta atendida (la evolucion de la ficha clinica).
- **Disponibilidad** — horario semanal de atencion del profesional.
- **Bloqueo** — periodos sin atencion (vacaciones, congresos).
- **Cita** — hora agendada para un paciente.

## Pruebas

```bash
./venv/bin/python manage.py test
```

21 pruebas que cubren el control de acceso por rol, las reglas de la agenda
(no permitir horas superpuestas ni citas dentro de un bloqueo) y el calculo de edad
de los pacientes.

## Cambiar entre SQLite y Oracle

En el archivo `.env`:

```
DB_ENGINE=sqlite    # desarrollo local, sin Oracle levantado
DB_ENGINE=oracle    # base de datos Oracle real
```

El codigo de la aplicacion es identico en ambos casos: Django traduce las consultas
al motor correspondiente.
