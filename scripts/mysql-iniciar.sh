#!/bin/bash
# Enciende el servidor MySQL local (solo macOS, instalacion en ~/.local/mysql).
# Si el arranque automatico esta configurado, se lo pide a macOS (launchd);
# si no, levanta el proceso directamente.
MYSQL_HOME="$HOME/.local/mysql"
DATA="$HOME/.local/mysql-data"
AGENTE="gui/$(id -u)/com.neuroficha.mysql"

if [ ! -x "$MYSQL_HOME/bin/mysqld" ]; then
  echo "MySQL no esta instalado en $MYSQL_HOME"; exit 1
fi

if "$MYSQL_HOME/bin/mysqladmin" --socket="$DATA/mysql.sock" -u root ping >/dev/null 2>&1; then
  echo "MySQL ya estaba corriendo."; exit 0
fi

if launchctl print "$AGENTE" >/dev/null 2>&1; then
  launchctl kickstart "$AGENTE"
else
  nohup "$MYSQL_HOME/bin/mysqld" --defaults-file="$MYSQL_HOME/my.cnf" >/dev/null 2>&1 &
fi

for i in $(seq 1 30); do
  if "$MYSQL_HOME/bin/mysqladmin" --socket="$DATA/mysql.sock" -u root ping >/dev/null 2>&1; then
    echo "MySQL encendido en el puerto 3306."; exit 0
  fi
  sleep 1
done
echo "MySQL no respondio. Revisa el log: $DATA/error.log"; exit 1
