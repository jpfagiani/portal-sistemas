#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  Atualiza o portal já instalado com a versão desta pasta.
#
#  Uso:  git pull && sudo ./atualizar.sh
#
#  Copia apenas o código (app.py, templates, CSS/JS). NÃO toca no banco de
#  dados, nas imagens enviadas, no logo, na foto de fundo nem na configuração
#  de rede ou do serviço.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PORTAL_NOME=cdpni-portal
DEST=/opt/$PORTAL_NOME
SERVICO=$PORTAL_NOME.service
USUARIO=$PORTAL_NOME
SRC="$(cd "$(dirname "$0")" && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "Execute como root:  sudo ./atualizar.sh"; exit 1; }

# Instalação da época em que o serviço rodava em /opt/intranet: só o instalador
# sabe trazer banco e imagens para cá, e atualizar sem isso subiria um portal
# vazio por cima de nada.
# Instalação anterior à convenção de nomes: o instalador move e renomeia.
if [ ! -d "$DEST" ] && [ -d /opt/portal ]; then
    echo "O portal ainda está em /opt/portal e agora se chama $PORTAL_NOME."
    echo "Rode o instalador uma vez para migrar:  sudo bash instalar.sh"
    exit 1
fi

if [ ! -f "$DEST/dados.db" ] && [ -f /opt/intranet/dados.db ]; then
    echo "Seus dados ainda estão em /opt/intranet, e agora o portal roda em $DEST."
    echo "Rode o instalador uma vez para trazer tudo:  sudo bash instalar.sh"
    exit 1
fi
[ -f "$DEST/dados.db" ] || { echo "O portal ainda não foi instalado — use ./instalar.sh"; exit 1; }

if [ "$(realpath "$SRC")" = "$(realpath "$DEST")" ]; then
    echo "Nada a copiar: você já está em $DEST."
else
    echo "Atualizando o código em $DEST ..."
    cp -f  "$SRC/app.py"    "$DEST/"
    cp -rf "$SRC/templates" "$DEST/"
    # Todo o CSS/JS; as imagens enviadas pelo administrador não são tocadas.
    cp -f  "$SRC"/static/*.css "$SRC"/static/*.js "$DEST/static/"
    # Imagens que acompanham o código (brasão, marcas d'água): só copia as que
    # ainda não existem no destino, para não sobrescrever o que foi enviado.
    for arq in "$SRC"/static/brasao.* "$SRC"/static/marca-*; do
        [ -f "$arq" ] && [ ! -f "$DEST/static/$(basename "$arq")" ]             && cp -f "$arq" "$DEST/static/"
    done
    chown -R "$USUARIO:$USUARIO" "$DEST"
fi

systemctl restart "$SERVICO"
sleep 2

if systemctl is-active --quiet "$SERVICO"; then
    echo "Portal atualizado e no ar."
    echo "  Dados, imagens e configurações preservados."
    echo "  Recarregue a página com Ctrl+F5 para pegar o CSS novo."
else
    echo "O serviço não voltou. Veja o erro com:  journalctl -u $PORTAL_NOME -n 30"
    exit 1
fi
