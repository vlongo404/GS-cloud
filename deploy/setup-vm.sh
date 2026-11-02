#!/usr/bin/env bash
# Roda DENTRO da VM Ubuntu (via SSH), com o usuario azureuser.
# Uso: ./setup-vm.sh https://github.com/SEU_USUARIO/api-tarefas.git
set -euo pipefail

REPO_URL="${1:?Uso: ./setup-vm.sh <url-do-repositorio-git>}"
APP_DIR="/opt/api-tarefas"

sudo apt-get update -y
sudo apt-get install -y python3-venv git

sudo mkdir -p "$APP_DIR"
sudo chown "$USER":"$USER" "$APP_DIR"

if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull
else
    git clone "$REPO_URL" "$APP_DIR"
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

sudo cp "$APP_DIR/deploy/api-tarefas.service" /etc/systemd/system/api-tarefas.service
sudo systemctl daemon-reload
sudo systemctl enable --now api-tarefas

sleep 2
sudo systemctl --no-pager status api-tarefas | head -n 8
echo
curl -s http://localhost/health
echo
