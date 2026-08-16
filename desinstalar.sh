#!/bin/bash
# Remove o serviço do portal. O banco (dados.db) e as imagens enviadas
# são PRESERVADOS na pasta da aplicação — apague-a manualmente se quiser.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Execute como root:  sudo ./desinstalar.sh"; exit 1; }

PORTAL_NOME=cdpni-portal
DEST=/opt/$PORTAL_NOME

# Nome atual e todos os anteriores: 'portal' (antes da convenção
# <servidor>-portal) e 'intranet' (até a versão 1.1). Remover só o atual
# deixaria unidades órfãs disputando a porta na próxima instalação.
for nome in "$PORTAL_NOME" portal intranet; do
    systemctl disable --now "${nome}.service"      2>/dev/null || true
    systemctl disable --now "${nome}-nome.service" 2>/dev/null || true
    rm -f "/etc/systemd/system/${nome}.service" \
          "/etc/systemd/system/${nome}-nome.service"
    rm -f "/usr/local/bin/${nome}-anuncia-nome"
done

# Entradas de nome no /etc/hosts, na marca atual e nas antigas
sed -i "/# ${PORTAL_NOME}\$/d;/# portal-intranet\$/d" /etc/hosts 2>/dev/null || true

systemctl daemon-reload

echo "Serviço removido. Dados preservados em $DEST"
echo "Para apagar tudo:  rm -rf $DEST && userdel $PORTAL_NOME"

for antigo in /opt/portal /opt/intranet; do
    if [ -d "$antigo" ]; then
        echo
        echo "Sobrou também a pasta de uma instalação anterior: $antigo"
        echo "  rm -rf $antigo && userdel $(basename "$antigo")"
    fi
done
