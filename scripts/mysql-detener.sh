#!/bin/bash
# Apaga el servidor MySQL local.
MYSQL_HOME="$HOME/.local/mysql"
DATA="$HOME/.local/mysql-data"
"$MYSQL_HOME/bin/mysqladmin" --socket="$DATA/mysql.sock" -u root shutdown 2>/dev/null \
  && echo "MySQL detenido." \
  || echo "MySQL no estaba corriendo."
