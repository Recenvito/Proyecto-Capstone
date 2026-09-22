#!/bin/bash
# Apaga el servidor MySQL local.
# El arranque automatico solo reinicia MySQL si se cae por un error, asi que
# apagarlo con este script lo deja apagado hasta que lo vuelvas a encender.
MYSQL_HOME="$HOME/.local/mysql"
DATA="$HOME/.local/mysql-data"
"$MYSQL_HOME/bin/mysqladmin" --socket="$DATA/mysql.sock" -u root shutdown 2>/dev/null \
  && echo "MySQL detenido." \
  || echo "MySQL no estaba corriendo."
