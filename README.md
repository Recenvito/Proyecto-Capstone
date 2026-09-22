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
| Base de datos | MySQL 8.4 LTS |
| Versiones | GitHub |
| Prototipado | Canva |

> Sobre por que Python 3.13 / Django 5.2 y por que MySQL, ver
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

### 4. Instalar y encender MySQL

**macOS (Apple Silicon)** — MySQL no tiene instalador oficial que no pida permisos de
administrador, asi que se usa el paquete portable en la carpeta personal:

```bash
curl -fL -o /tmp/mysql.tar.gz \
  https://cdn.mysql.com/Downloads/MySQL-8.4/mysql-8.4.11-macos15-arm64.tar.gz
tar -xzf /tmp/mysql.tar.gz -C /tmp
mv /tmp/mysql-8.4.11-macos15-arm64 ~/.local/mysql
```

Luego crear `~/.local/mysql/my.cnf`, inicializar con
`mysqld --initialize-insecure` y encenderlo con `./scripts/mysql-iniciar.sh`.

**Windows** — descargar el *MySQL Installer* desde
https://dev.mysql.com/downloads/installer/ y elegir la version **8.4 LTS**.
Tambien sirve XAMPP si ya lo tienen instalado.

### 5. Crear la base de datos del proyecto

Con MySQL encendido, en su consola:

```sql
CREATE DATABASE neuroficha CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'neuroficha'@'localhost' IDENTIFIED BY 'la-password-que-elijan';
GRANT ALL PRIVILEGES ON neuroficha.* TO 'neuroficha'@'localhost';
GRANT ALL PRIVILEGES ON test_neuroficha.* TO 'neuroficha'@'localhost';
FLUSH PRIVILEGES;
```

> El permiso sobre `test_neuroficha` es necesario para que `manage.py test` pueda
> crear y destruir su propia base de pruebas. **No crear esa base a mano:** Django
> la maneja sola y si ya existe, se queda esperando una confirmacion.

Poner esa misma password en el `MYSQL_PASSWORD` del archivo `.env`.

### 6. Crear las tablas y los datos de prueba

```bash
./venv/bin/python manage.py migrate
./venv/bin/python manage.py shell < crear_datos_demo.py
```

### 7. Levantar el servidor

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

## Comandos utiles de MySQL (solo macOS)

```bash
./scripts/mysql-iniciar.sh    # encender MySQL
./scripts/mysql-detener.sh    # apagarlo
./scripts/mysql-consola.sh    # abrir la consola SQL sobre la base del proyecto
```

MySQL hay que **encenderlo antes** de levantar el servidor de Django. No arranca solo
al prender el Mac.

## Cambiar de motor de base de datos

En el archivo `.env`:

```
DB_ENGINE=mysql     # lo que usa el proyecto
DB_ENGINE=sqlite    # respaldo, para trabajar sin MySQL encendido
```

El codigo de la aplicacion es identico en ambos casos: Django traduce las consultas
al motor correspondiente.
