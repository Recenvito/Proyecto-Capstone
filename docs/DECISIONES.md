# Decisiones tecnicas — Proyecto NeuroFicha

Sistema de agenda y ficha clinica para consulta de neurologia infantil.

---

## Stack acordado por el equipo

| Area | Herramienta |
|---|---|
| Gestion de proyecto | Jira |
| Editor / IDE | Visual Studio Code |
| Framework | Django (Python) |
| Base de datos | MySQL 8.4 LTS |
| Control de versiones | GitHub |
| Prototipado de interfaz | Canva |

---

## Historial — Por que se descarto Oracle SQL

El stack inicial contemplaba **Oracle SQL**. Se descarto el 2026-09-22 por un motivo
practico: **Oracle Database no se puede instalar en macOS** (Oracle no publica una
version para Mac desde 2010, ni para Intel ni para Apple Silicon).

Eso generaba una asimetria en el equipo: los integrantes con Windows podian instalar
Oracle XE de forma nativa, pero el integrante con macOS quedaba obligado a levantarlo
en un contenedor Docker o en la nube, es decir, trabajando distinto del resto.

Se evaluaron tres salidas (Oracle local por integrante, Oracle Cloud compartido, o un
servidor de la universidad) y finalmente el equipo opto por **cambiar de motor**. La
decision y sus fundamentos estan mas abajo, en "Base de datos: MySQL 8.4 LTS".

Todo rastro de Oracle se elimino del proyecto el 2026-10-08: el driver `oracledb` salio
de `requirements.txt` y la configuracion correspondiente salio de `settings.py`.

## Decision tomada — Version de Python y Django

**Python 3.13 + Django 5.2 LTS** (en vez de Python 3.9 + Django 4.2).

**Motivo tecnico:** Django 4.2 solo se conecta a Oracle mediante el driver `cx_Oracle`, que
exige compilar el *Oracle Instant Client* nativo — algo especialmente problematico en
Apple Silicon. El driver moderno `python-oracledb` funciona en **modo Thin** (Python puro,
sin librerias nativas, compatible con ARM), pero **solo esta soportado desde Django 5.0**.

**Motivo de mantenimiento:** Django 4.2 LTS termino su soporte en abril de 2026. Django 5.2
LTS lo tiene hasta abril de 2028, es decir, cubre toda la vida util del proyecto.

Todo el equipo debe usar la **misma version de Python (3.13)**, sin importar el sistema
operativo, para que `requirements.txt` funcione igual en todas las maquinas.

---

## Decision tomada — Repositorio publico

**Repositorio:** https://github.com/Recenvito/Proyecto-Capstone

Se mantiene **publico** de forma deliberada: los evaluadores de casa central deben poder
revisar el codigo sin que el equipo tenga que agregar a cada persona como colaborador del
repositorio (lo que ademas les daria permiso de escritura innecesario).

### Regla de trabajo que se deriva de esto

Al ser publico, hay una separacion que el equipo debe respetar durante todo el proyecto:

| Donde vive | Que contiene |
|---|---|
| Repositorio de GitHub (publico) | **Solo codigo.** Datos de pacientes siempre ficticios. |
| Base de datos Oracle | Los pacientes **reales**. Nunca pasa por Git. |
| Archivo `.env` (local, en `.gitignore`) | Credenciales reales de la base de datos. |

**Riesgo concreto:** el archivo `crear_datos_demo.py` esta versionado y contiene los
pacientes de prueba. **No se debe editar reemplazando los datos ficticios por pacientes
reales.** Los pacientes reales se ingresan por la aplicacion web, que es justamente el
sistema que se esta construyendo.

**Por que importa:** lo que se sube al historial de Git no se puede borrar del todo. Un
commit posterior que elimine un dato sensible no lo saca del historial: sigue siendo
recuperable, y si el repositorio es publico, cualquiera pudo haberlo clonado antes.
Se trata de datos de salud de menores de edad.

---

## Decision tomada — Base de datos: MySQL 8.4 LTS

**Fecha:** 2026-09-22. Reemplaza la decision previa de usar Oracle SQL.

### Motivo

Oracle Database no se puede instalar en macOS (Oracle no publica version para Mac desde
2010), lo que dejaba a un integrante del equipo obligado a trabajar con Docker o con una
base en la nube, distinto del resto. **MySQL corre nativo tanto en macOS (Apple Silicon)
como en Windows**, asi que todo el equipo trabaja igual.

Se evaluo tambien PostgreSQL, tecnicamente equivalente para este proyecto. Se elegio
MySQL porque el equipo ya lo maneja de otros ramos, lo que reduce la curva de aprendizaje
y el riesgo de bloqueos.

### Version

**MySQL 8.4 LTS**, no la serie "Innovation". La serie LTS recibe correcciones de
seguridad por varios anios y no introduce cambios incompatibles, que es lo que conviene
para un proyecto que se desarrolla durante meses y se defiende al final.

### Configuracion aplicada

- Codificacion `utf8mb4` en la base, las tablas y la conexion, para que los nombres con
  tilde y la letra "n" con virgulilla se guarden correctamente.
- `sql_mode = STRICT_TRANS_TABLES`: MySQL rechaza datos invalidos en vez de guardarlos
  truncados en silencio. Es importante en un sistema con informacion clinica, donde un
  dato cortado a la mitad puede cambiar el sentido de una indicacion medica.
- El servidor solo escucha en `127.0.0.1`, es decir, no acepta conexiones desde fuera
  del computador.
- La aplicacion se conecta con un usuario dedicado (`neuroficha`) que solo tiene
  permisos sobre su propia base, no con el usuario administrador.

### Instalacion en macOS

MySQL no ofrece un instalador para Mac que no exija permisos de administrador, por lo que
se uso el paquete portable (`.tar.gz`) descomprimido en `~/.local/mysql`. Funciona igual
y no requiere contrasenia de administrador. Hay scripts en `scripts/` para encenderlo,
apagarlo y abrir la consola.

En Windows se usa el instalador oficial de MySQL 8.4 LTS (o XAMPP, que trae MySQL).

### Lo que NO cambio

El codigo de la aplicacion es identico: modelos, vistas, formularios y consultas no se
tocaron. Django traduce las consultas al motor configurado. Lo unico que cambia es el
archivo `.env`.

---

## Tecnologias utilizadas y versiones

Estado al 2026-10-08.

### Lenguaje y framework

| Tecnologia | Version | Rol en el proyecto |
|---|---|---|
| Python | 3.13.15 | Lenguaje de programacion del backend |
| Django | 5.2.17 LTS | Framework web (soporte hasta abril de 2028) |
| HTML5 / CSS3 | — | Interfaz de usuario. Son estandares web, no llevan version |

### Base de datos

| Tecnologia | Version | Rol en el proyecto |
|---|---|---|
| MySQL Server | 8.4.11 LTS | Motor de base de datos |
| mysqlclient | 2.3.0 | Driver que conecta Python con MySQL |
| SQLite | Incluida en Python | Respaldo para desarrollar sin MySQL encendido |

### Librerias de Python

| Libreria | Version | Para que se usa |
|---|---|---|
| python-dotenv | 1.2.3 | Lee las credenciales desde el archivo `.env` |
| sqlparse | 0.6.0 | Procesamiento de SQL (requisito de Django) |
| asgiref | 3.12.1 | Soporte asincrono (requisito de Django) |
| cryptography | 50.0.1 | Cifrado de las conexiones |
| cffi, pycparser, typing_extensions | — | Dependencias internas de las anteriores |

### Herramientas de desarrollo

| Herramienta | Version | Rol en el proyecto |
|---|---|---|
| Visual Studio Code | 1.137.0 | Editor de codigo |
| MySQL Workbench | 26.7.0 | Cliente visual de base de datos y diagramas entidad-relacion |
| Git | 2.50.1 | Control de versiones |
| GitHub CLI (`gh`) | 2.98.0 | Interaccion con GitHub desde la terminal |
| uv | 0.12.6 | Instalacion y gestion de versiones de Python |
| Jira | — | Gestion del proyecto |
| Canva | — | Prototipado de la interfaz |

### Entorno de desarrollo

El equipo trabaja en dos sistemas operativos distintos. Todas las tecnologias de la
lista funcionan de forma nativa en ambos, por lo que el proyecto se ejecuta igual en
cualquiera de las maquinas del equipo.

| Integrante | Sistema operativo |
|---|---|
| Rodrigo Maira | macOS 26.6 sobre Apple Silicon (M4 Pro) |
| Resto del equipo | Windows |
