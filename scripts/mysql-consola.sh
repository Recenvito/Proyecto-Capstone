#!/bin/bash
# Abre la consola de MySQL sobre la base del proyecto, para escribir SQL a mano.
# Uso:  ./scripts/mysql-consola.sh
exec "$HOME/.local/mysql/bin/mysql" \
  --socket="$HOME/.local/mysql-data/mysql.sock" -u root neuroficha
