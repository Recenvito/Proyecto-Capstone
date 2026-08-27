# Decisiones tecnicas — Proyecto NeuroFicha

Sistema de agenda y ficha clinica para consulta de neurologia infantil.

---

## Stack acordado por el equipo

| Area | Herramienta |
|---|---|
| Gestion de proyecto | Jira |
| Editor / IDE | Visual Studio Code |
| Framework | Django (Python) |
| Base de datos | Oracle SQL |
| Control de versiones | GitHub |
| Prototipado de interfaz | Canva |

---

## ⏳ DECISION PENDIENTE — Donde se aloja la base de datos Oracle

**Estado:** por confirmar con el equipo.
**Responsable:** Rodrigo consulta con sus companieros de tesis.

### El problema

**Oracle Database no se puede instalar en macOS.** Oracle no publica una version para Mac
desde 2010, ni para Intel ni para Apple Silicon. Esto no depende del equipo de Rodrigo:
es una decision del fabricante.

Esto genera una **asimetria en el equipo**:

| Integrante | Sistema | Puede instalar Oracle localmente |
|---|---|---|
| Rodrigo | macOS (Apple Silicon M4 Pro) | ❌ No — requiere contenedor o nube |
| Resto del equipo | Windows | ✅ Si — Oracle XE tiene instalador nativo |

### Las opciones

**A. Cada uno con su Oracle local**
- Windows: instalador nativo de Oracle XE / Free 23ai.
- macOS: contenedor Docker con la imagen ARM64 de Oracle Database Free 23ai.
- ✅ Gratis, sin cuentas, funciona sin internet (util para la defensa de la tesis).
- ❌ **Cada integrante trabaja sobre su propia base de datos.** Los datos de prueba no se
  comparten y hay riesgo de desincronizar los esquemas entre companieros.

**B. Una base Oracle compartida en la nube** *(Oracle Cloud — Autonomous Database "Always Free")*
- ✅ **Todo el equipo trabaja contra la misma base de datos**, sin importar el sistema
  operativo. Se elimina por completo el problema de Apple Silicon.
- ✅ Es la configuracion mas parecida a un sistema en produccion real.
- ❌ Requiere crear una cuenta en Oracle Cloud (pide tarjeta para verificar identidad; el
  plan Always Free no cobra).
- ❌ Depende de tener internet. **Riesgo:** si falla el wifi el dia de la defensa, no hay demo.

**C. Servidor Oracle provisto por la universidad**
- ✅ Compartido, sin costo, y suele estar bien visto en la evaluacion.
- ❌ Hay que averiguar si existe y pedir credenciales con tiempo.

### Recomendacion tecnica

**Opcion B o C (base compartida), con la opcion A como respaldo local.**

Al ser un trabajo en equipo, una base compartida evita el problema clasico de "en mi
maquina funciona". Y conviene, en cualquier caso, dejar preparado un respaldo local
(archivo `.sql` con el esquema y datos de prueba) para poder demostrar el sistema sin
internet el dia de la defensa.

### Mientras tanto: el desarrollo no esta bloqueado

El proyecto quedo configurado para **conmutar de base de datos con una sola linea**, en el
archivo `.env`:

```
DB_ENGINE=sqlite    # desarrollar sin Oracle levantado
DB_ENGINE=oracle    # apuntar a la base Oracle real
```

Django usa el mismo codigo para ambas: los modelos, las consultas y las migraciones no
cambian. Cuando el equipo confirme donde vive Oracle, solo se rellenan las credenciales.

---

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
