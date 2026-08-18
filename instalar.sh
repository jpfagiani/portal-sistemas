#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
#  Portal Interno — instalador para Debian 13 (trixie)
#
#  Uso:  sudo ./instalar.sh [porta]        (porta padrão: 80)
#
#  Convenção de portas do projeto, igual em todas as unidades:
#     80    portal-sistemas (este)  — atalhos, todos os usuários
#     8080  portal-gateway  (GWOS)  — administração
#     8443  portal-samba            — administração
#  Este é o único acessado sem porta na barra de endereços, por isso fica na 80.
#
#  Pergunta tudo o que muda de uma unidade para outra (nome da instituição,
#  rede, logo e foto), de modo que o mesmo código sirva a qualquer unidade
#  sem precisar editar arquivo nenhum.
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# Nome do portal. Convenção portal-<função>: nomeia o que o portal administra,
# sem citar a unidade — portal-sistemas aqui, portal-samba no servidor de
# arquivos, portal-gateway no GWOS. Diretório, serviço, usuário e o mDNS
# derivam daqui: para renomear, muda esta linha e roda o instalador, que migra
# a instalação existente.
PORTAL_NOME=portal-sistemas

DEST=/opt/$PORTAL_NOME
SERVICO=$PORTAL_NOME.service
SERVICO_MDNS=$PORTAL_NOME-nome.service
BIN_MDNS=/usr/local/bin/$PORTAL_NOME-anuncia-nome
USUARIO=$PORTAL_NOME
MARCA_HOSTS="# $PORTAL_NOME"
PORTA="${1:-80}"
SRC="$(cd "$(dirname "$0")" && pwd)"

# Instalação anterior à convenção portal-<função>. A máquina pode ter parado
# em qualquer etapa (portal → cdpni-portal → portal-sistemas), então procuramos
# qual existe em vez de assumir: chutar o nome de origem faria o instalador não
# encontrar nada e criar uma instalação vazia ao lado dos dados antigos.
DEST_ANTERIOR=""
USUARIO_ANTERIOR=""
for _n in cdpni-portal portal; do
    if [ -d "/opt/$_n" ] && [ "/opt/$_n" != "$DEST" ]; then
        DEST_ANTERIOR="/opt/$_n"
        USUARIO_ANTERIOR="$_n"
        break
    fi
done

vermelho(){ printf '\033[31m%s\033[0m\n' "$*"; }
verde()   { printf '\033[32m%s\033[0m\n' "$*"; }
amarelo() { printf '\033[33m%s\033[0m\n' "$*"; }
titulo()  { printf '\n\033[1;36m%s\033[0m\n' "$*"; }

# Pergunta com valor padrão:  perguntar VARIAVEL "Rótulo" "padrão"
perguntar(){
    local __var="$1" rotulo="$2" padrao="${3:-}" resposta
    if [ -n "$padrao" ]; then
        read -r -p "   $rotulo [$padrao]: " resposta
        resposta="${resposta:-$padrao}"
    else
        read -r -p "   $rotulo: " resposta
    fi
    printf -v "$__var" '%s' "$resposta"
}
confirmar(){ local r; read -r -p "   $1 [s/N] " r; [[ "${r,,}" == s* ]]; }
eh_ip(){ [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; }

[ "$(id -u)" -eq 0 ] || { vermelho "Execute como root:  sudo ./instalar.sh"; exit 1; }

# ── 1 · versão do Debian ──────────────────────────────────────────────────────
titulo "[1/8] Sistema operacional"
. /etc/os-release 2>/dev/null || { vermelho "Não foi possível ler /etc/os-release"; exit 1; }
VER="${VERSION_ID:-0}"
echo "   Detectado: ${PRETTY_NAME:-desconhecido}"

if [ "$ID" != "debian" ] && [[ "${ID_LIKE:-}" != *debian* ]]; then
    vermelho "   Este instalador é para Debian (ou derivados). Detectado: ${ID:-?}"
    exit 1
fi

# A escolha entre "usar o Flask do sistema" e "montar um ambiente virtual" não
# é feita aqui de propósito. Decidir pelo número da versão erra nas duas
# pontas: um Debian 11 com Flask novo instalado à mão seria empurrado para o
# venv sem precisar, e um derivado com número desconhecido seria condenado ao
# venv mesmo trazendo pacote bom. Em [5/8] o instalador tenta o caminho do
# sistema, mede o que o apt entregou e só então decide.
case "$VER" in
    13*) verde   "   Debian 13 (trixie) — versão alvo deste portal." ;;
    12*) verde   "   Debian 12 (bookworm) — compatível." ;;
    11*|10*) amarelo "   Debian $VER é antigo, mas dá conta: as dependências" \
                     "vêm por ambiente virtual se as do sistema não servirem." ;;
    *)   amarelo "   Versão '$VER' não é uma das testadas. Sigo assim mesmo:" \
                 "as dependências são conferidas antes de instalar o portal." ;;
esac

# Pacotes que passos posteriores podem pedir (o avahi, quando o nome escolhido
# termina em .local). Instalados junto com o resto em [5/8].
EXTRAS=""

# ── 1c · instalação anterior com outro nome ───────────────────────────────────
# O portal passou a se chamar portal-sistemas, seguindo a convenção portal-<função>.
# A instalação antiga é MOVIDA — não copiada: manter as duas
# faria dois gunicorn disputarem a mesma porta, e o systemd subiria o errado.
if [ -n "$DEST_ANTERIOR" ] && [ -d "$DEST_ANTERIOR" ] && [ ! -d "$DEST" ]; then
    titulo "[1c/8] Instalação anterior encontrada em $DEST_ANTERIOR"
    echo "   O portal passou a se chamar $PORTAL_NOME."
    echo "   Vou mover $DEST_ANTERIOR para $DEST e renomear serviço e usuário."
    echo "   Os dados (banco, imagens, backups) vão junto."
    confirmar "Continuar?" || { vermelho "   Instalação cancelada."; exit 1; }

    # Parar antes de mover: gunicorn com o diretório de trabalho puxado debaixo
    # dos pés fica em laço de reinício e segura a porta.
    systemctl disable --now "${USUARIO_ANTERIOR}.service"      2>/dev/null || true
    systemctl disable --now "${USUARIO_ANTERIOR}-nome.service" 2>/dev/null || true
    if pgrep -f "gunicorn.*$DEST_ANTERIOR" >/dev/null 2>&1; then
        pkill -f "gunicorn.*$DEST_ANTERIOR" 2>/dev/null || true
        sleep 2
        pkill -9 -f "gunicorn.*$DEST_ANTERIOR" 2>/dev/null || true
    fi

    mv "$DEST_ANTERIOR" "$DEST"
    verde "   $DEST_ANTERIOR → $DEST"

    # O portal roda da própria pasta do clone, então é normal este script
    # estar DENTRO do que acabou de ser movido. O bash segue lendo pelo
    # inode aberto, mas $SRC virou caminho inexistente — e a cópia de
    # arquivos em [6/8] falharia no meio da instalação.
    if [ "$SRC" = "$DEST_ANTERIOR" ] || case "$SRC" in "$DEST_ANTERIOR"/*) true;; *) false;; esac; then
        SRC="${DEST}${SRC#"$DEST_ANTERIOR"}"
        amarelo "   Este script foi movido junto; continuando de $SRC"
    fi

    # Usuário do sistema: renomeia se existir e o novo ainda não. O serviço
    # está parado, então não há processo dele em execução.
    if id -u "$USUARIO_ANTERIOR" >/dev/null 2>&1 && ! id -u "$USUARIO" >/dev/null 2>&1; then
        usermod -l "$USUARIO" -d "$DEST" "$USUARIO_ANTERIOR" 2>/dev/null             && groupmod -n "$USUARIO" "$USUARIO_ANTERIOR" 2>/dev/null             && verde "   Usuário $USUARIO_ANTERIOR → $USUARIO"             || amarelo "   Usuário não renomeado — o instalador cria $USUARIO adiante."
    fi
    chown -R "$USUARIO:$USUARIO" "$DEST" 2>/dev/null || true

    rm -f "/etc/systemd/system/${USUARIO_ANTERIOR}.service"           "/etc/systemd/system/${USUARIO_ANTERIOR}-nome.service"
    rm -f "/usr/local/bin/${USUARIO_ANTERIOR}-anuncia-nome"
    systemctl daemon-reload
    verde "   Unidades antigas removidas. O serviço novo sobe em [7/8]."
fi

# ── 1b · instalação anterior em /opt/intranet ─────────────────────────────────
# Até a versão 1.1 o clone do Git ficava numa pasta e o serviço rodava em
# outra (/opt/intranet). Separar as duas confundia mais do que ajudava — quem
# atualizava via `git pull` numa pasta via o site rodando pela outra. Agora é
# uma pasta só.
#
# Os dados são COPIADOS, não movidos: a pasta antiga fica intacta como rede de
# segurança até você conferir que está tudo no lugar.
ANTIGO=/opt/intranet
if [ -f "$ANTIGO/dados.db" ] && [ ! -f "$DEST/dados.db" ]; then
    titulo "[1b/8] Instalação anterior encontrada em $ANTIGO"
    echo "   O portal passou a rodar direto de $DEST, sem pasta separada."
    echo "   Vou copiar para lá: banco de dados, chave de sessão, backups,"
    echo "   imagens enviadas, logo e foto de fundo."
    echo "   A pasta antiga NÃO será apagada."
    confirmar "Continuar?" || { vermelho "   Instalação cancelada."; exit 1; }

    systemctl disable --now portal.service    2>/dev/null || true
    systemctl disable --now intranet.service  2>/dev/null || true
    systemctl disable --now intranet-nome.service 2>/dev/null || true

    # Gunicorn órfão da instalação antiga continua segurando a porta: quando a
    # unidade some antes de os processos morrerem, o systemd perde o rastro
    # deles e o serviço novo não consegue abrir o socket. Só mata o que aponta
    # para a pasta antiga — nada de varrer a porta às cegas, esta máquina tem
    # outros serviços.
    if pgrep -f "gunicorn.*$ANTIGO" >/dev/null 2>&1; then
        amarelo "   Encerrando processos remanescentes da instalação antiga..."
        pkill -f "gunicorn.*$ANTIGO" 2>/dev/null || true
        sleep 2
        pkill -9 -f "gunicorn.*$ANTIGO" 2>/dev/null || true
    fi

    mkdir -p "$DEST/static/uploads"
    for arq in dados.db secret.key ACESSO-POR-NOME.txt; do
        if [ -f "$ANTIGO/$arq" ]; then cp -a "$ANTIGO/$arq" "$DEST/"; fi
    done
    if [ -d "$ANTIGO/backups" ]; then cp -a "$ANTIGO/backups" "$DEST/"; fi
    if [ -d "$ANTIGO/static/uploads" ]; then
        cp -a "$ANTIGO/static/uploads/." "$DEST/static/uploads/"
    fi
    # Logo, fundo e marcas d'água: arquivos soltos, extensão variável.
    for arq in "$ANTIGO"/static/logo.* "$ANTIGO"/static/brasao.* \
               "$ANTIGO"/static/fundo.* "$ANTIGO"/static/marca-*; do
        if [ -f "$arq" ]; then cp -a "$arq" "$DEST/static/"; fi
    done

    rm -f /etc/systemd/system/intranet.service /etc/systemd/system/intranet-nome.service
    rm -f /usr/local/bin/intranet-anuncia-nome
    systemctl daemon-reload

    if [ -f "$DEST/dados.db" ]; then
        verde "   Dados copiados para $DEST."
        echo  "   A pasta antiga continua em $ANTIGO. Depois de conferir que o"
        echo  "   site está certo, apague com:  rm -rf $ANTIGO"
    else
        vermelho "   O banco não foi copiado. Instalação interrompida para não"
        vermelho "   criar um portal vazio por cima dos seus dados."
        exit 1
    fi
fi

# ── 2 · identidade da unidade ─────────────────────────────────────────────────
titulo "[2/8] Identidade da unidade (aparece no site)"
if [ -f "$DEST/dados.db" ]; then
    echo "   Já existe uma instalação: o nome atual será mantido."
    echo "   (para mudar depois: Administração → Aparência)"
    ORG_NOME=""; ORG_SIGLA=""; ORG_SUB=""
else
    perguntar ORG_NOME  "Nome da unidade" "Centro de Detenção Provisória de Nova Independência"
    perguntar ORG_SIGLA "Sigla" "CDPNI"
    perguntar ORG_SUB   "Subtítulo" "Portal de Sistemas"
    echo
    echo "   Ficará assim no cabeçalho:"
    echo "      $ORG_NOME"
    echo "      $ORG_SUB"
    confirmar "Confirma?" || { vermelho "   Instalação cancelada."; exit 1; }
fi

# ── 3 · senha do administrador ────────────────────────────────────────────────
titulo "[3/8] Acesso do administrador"
SENHA_ADMIN=""
if [ -f "$DEST/dados.db" ]; then
    echo "   Já existe uma instalação: os usuários e senhas atuais são mantidos."
else
    echo "   O portal começa com um único usuário, de login fixo 'admin'."
    echo "   Depois de entrar, dá para criar os demais em Administração → Usuários."
    echo
    # Mesma exigência do portal do Samba: 8 caracteres com maiúscula, minúscula
    # e número. Este é o portal mais exposto dos três — fica na porta 80 e a
    # tela de login é vista por toda a unidade —, então não faz sentido ser o
    # de critério mais frouxo.
    echo "   Requisitos: mínimo 8 caracteres, com maiúscula, minúscula e número."
    echo
    while true; do
        read -r -s -p "   Senha para o usuário 'admin': " S1; echo
        read -r -s -p "   Repita a senha: " S2; echo

        # Os testes ficam TODOS como condição de if/elif. Um validador chamado
        # solto seria interceptado pelo 'set -e' do topo e mataria o script em
        # vez de repetir a pergunta.
        if [[ "$S1" == *[[:cntrl:]]* ]]; then
            # read -s com setas/Tab injeta sequências de escape na variável.
            vermelho "   Senha com caracteres inválidos — não use setas, Tab"
            vermelho "   nem teclas especiais ao digitar."
        elif [ "${#S1}" -lt 8 ]; then
            vermelho "   A senha precisa ter ao menos 8 caracteres."
        elif ! [[ "$S1" =~ [A-Z] ]]; then
            vermelho "   Falta uma letra MAIÚSCULA."
        elif ! [[ "$S1" =~ [a-z] ]]; then
            vermelho "   Falta uma letra minúscula."
        elif ! [[ "$S1" =~ [0-9] ]]; then
            vermelho "   Falta um número."
        elif [ "$S1" != "$S2" ]; then
            vermelho "   As senhas não conferem."
        else
            SENHA_ADMIN="$S1"; unset S1 S2; break
        fi
    done
    verde "   Senha definida."
fi

# ── 4 · rede ──────────────────────────────────────────────────────────────────
titulo "[4/8] Rede"

listar_ifaces(){
    mapfile -t IFACES < <(ls /sys/class/net | grep -v '^lo$' | sort)
    local i=1
    for f in "${IFACES[@]}"; do
        local ip est mac
        ip=$(ip -4 -o addr show dev "$f" 2>/dev/null | awk '{print $4}' | paste -sd, -)
        est=$(cat "/sys/class/net/$f/operstate" 2>/dev/null || echo "?")
        mac=$(cat "/sys/class/net/$f/address" 2>/dev/null || echo "?")
        printf '     %d) %-12s %-20s estado: %-6s  mac: %s\n' \
               "$i" "$f" "${ip:-sem IP}" "$est" "$mac"
        i=$((i+1))
    done
}

escolher_iface(){
    # Sugere a interface que hoje carrega a rota padrão; se não houver, a primeira.
    local sugerida
    sugerida=$(ip route 2>/dev/null | awk '/^default/{print $5; exit}')
    [ -n "$sugerida" ] || sugerida="${IFACES[0]}"

    echo "   Interface detectada em uso: $sugerida"
    if confirmar "Usar esta interface?"; then
        IFACE="$sugerida"
    else
        local n
        while true; do
            perguntar n "Número da interface desejada" "1"
            IFACE="${IFACES[$((n-1))]:-}"
            [ -n "$IFACE" ] && break
            vermelho "   Número inválido."
        done
    fi
    verde "   Interface escolhida: $IFACE"
}

aplicar_ifupdown(){   # $1 = bloco de configuração
    mkdir -p /etc/network/interfaces.d
    printf '%s\n' "$1" > "/etc/network/interfaces.d/$IFACE"
    grep -q 'source /etc/network/interfaces.d/\*' /etc/network/interfaces 2>/dev/null \
        || echo 'source /etc/network/interfaces.d/*' >> /etc/network/interfaces
    ifdown "$IFACE" >/dev/null 2>&1 || true
    ifup "$IFACE" >/dev/null 2>&1
}

aplicar_nmcli(){      # $1 = "auto" | "manual"; usa IP/MASCARA/GW/DNS
    local con
    con=$(nmcli -g GENERAL.CONNECTION device show "$IFACE" 2>/dev/null | head -1)
    [ -n "$con" ] || con=$(nmcli -t -f NAME con show | head -1)
    [ -n "$con" ] || return 1
    if [ "$1" = "auto" ]; then
        nmcli con mod "$con" ipv4.method auto ipv4.addresses "" ipv4.gateway "" ipv4.dns ""
    else
        nmcli con mod "$con" ipv4.method manual \
              ipv4.addresses "$IP/$MASCARA" ipv4.gateway "$GW" ipv4.dns "${DNS// /,}"
    fi
    nmcli con up "$con" >/dev/null 2>&1
}

testar_rede(){
    sleep 2
    local gw
    gw=$(ip route | awk '/^default/{print $3; exit}')
    [ -n "$gw" ] || return 1
    ping -c1 -W2 "$gw" >/dev/null 2>&1 || return 1
    verde "   Gateway $gw responde."
    if ping -c1 -W2 8.8.8.8 >/dev/null 2>&1; then
        verde "   Internet OK."
    else
        amarelo "   Sem internet (normal se a rede for fechada)."
    fi
    return 0
}

configurar_rede(){
    # Quando o GWOS esta na maquina, ele e o dono do /etc/network/interfaces.
    # Este instalador escreve em /etc/network/interfaces.d/<iface> — arquivo
    # separado, mas incluido pelo 'source /etc/network/interfaces.d/*' que o
    # GWOS poe no topo do dele. O resultado sao DUAS stanzas para a mesma
    # placa: o ifup aborta a interface no boot e a maquina sobe sem rede.
    # O sintoma so aparece no reboot seguinte, o que torna a causa dificil
    # de associar a esta instalacao. Melhor nem oferecer a opcao.
    if [ -f /etc/gwos/gwos.conf ]; then
        amarelo "   Rede gerenciada pelo GWOS nesta maquina — nao vou mexer."
        echo    "   Para trocar o IP:  sudo gwos ip <novo-ip>"
        echo    "   Ele valida, faz backup e recarrega DNS, proxy e firewall juntos."
        echo
        return
    fi

    listar_ifaces
    if [ "${#IFACES[@]}" -eq 0 ]; then
        vermelho "   Nenhuma placa de rede encontrada."; return
    fi
    echo "   Gateway atual: $(ip route | awk '/^default/{print $3; exit}' || echo 'nenhum')"
    echo "   DNS atual:     $(awk '/^nameserver/{printf "%s ", $2}' /etc/resolv.conf 2>/dev/null || echo '-')"
    echo

    escolher_iface
    echo
    echo "   O que deseja fazer com a rede?"
    echo "     1) Manter a configuração atual (recomendado)"
    echo "     2) Definir IP fixo"
    echo "     3) Usar DHCP (IP automático)"
    local OPT; perguntar OPT "Opção" "1"
    [ "$OPT" = "1" ] && { echo "   Rede mantida como está."; return; }

    local MODO="auto" BLOCO=""
    if [ "$OPT" = "2" ]; then
        MODO="manual"
        local atual_ip
        atual_ip=$(ip -4 -o addr show dev "$IFACE" | awk '{print $4}' | head -1)
        while true; do
            perguntar IP       "Endereço IP" "${atual_ip%%/*}"
            perguntar MASCARA  "Máscara em bits" "${atual_ip##*/}"
            perguntar GW       "Gateway" "$(ip route | awk '/^default/{print $3; exit}')"
            perguntar DNS      "DNS (separados por espaço)" "$GW 8.8.8.8"
            if ! eh_ip "$IP";  then vermelho "   IP inválido.";      continue; fi
            if ! eh_ip "$GW";  then vermelho "   Gateway inválido."; continue; fi
            if ! [[ "$MASCARA" =~ ^[0-9]{1,2}$ ]] || [ "$MASCARA" -gt 32 ]; then
                vermelho "   Máscara inválida (use algo como 24)."; continue
            fi
            echo
            echo "   Confira:"
            echo "     Interface: $IFACE"
            echo "     IP:        $IP/$MASCARA"
            echo "     Gateway:   $GW"
            echo "     DNS:       $DNS"
            confirmar "Está correto?" && break
        done
        BLOCO="auto $IFACE
iface $IFACE inet static
    address $IP/$MASCARA
    gateway $GW
    dns-nameservers $DNS"
    else
        BLOCO="auto $IFACE
iface $IFACE inet dhcp"
    fi

    amarelo "   ATENÇÃO: se você estiver conectado por SSH, a conexão pode cair"
    amarelo "   ao aplicar. O ideal é fazer isso no console da máquina."
    confirmar "Aplicar agora?" || { echo "   Rede não alterada."; return; }

    # Backup antes de qualquer escrita — é o que permite desfazer.
    local STAMP BACKUP
    STAMP=$(date +%Y%m%d-%H%M%S)
    BACKUP="/root/rede-backup-$STAMP"
    mkdir -p "$BACKUP"
    cp -a /etc/network/interfaces      "$BACKUP/" 2>/dev/null || true
    cp -a /etc/network/interfaces.d    "$BACKUP/" 2>/dev/null || true
    cp -a /etc/resolv.conf             "$BACKUP/" 2>/dev/null || true
    cp -a /etc/NetworkManager/system-connections "$BACKUP/" 2>/dev/null || true
    echo "   Backup salvo em $BACKUP"

    local USOU_NM=0
    if systemctl is-active --quiet NetworkManager 2>/dev/null && command -v nmcli >/dev/null; then
        echo "   NetworkManager está no comando desta máquina — usando nmcli."
        USOU_NM=1
        aplicar_nmcli "$MODO" || vermelho "   Falha ao aplicar via nmcli."
    else
        aplicar_ifupdown "$BLOCO" || vermelho "   Falha ao subir $IFACE."
    fi

    if testar_rede; then
        verde "   Rede configurada com sucesso."
    else
        vermelho "   A rede não respondeu. Desfazendo a alteração..."
        if [ "$USOU_NM" = "1" ]; then
            cp -a "$BACKUP/system-connections/." /etc/NetworkManager/system-connections/ 2>/dev/null || true
            nmcli con reload >/dev/null 2>&1 || true
        else
            cp -a "$BACKUP/interfaces" /etc/network/ 2>/dev/null || true
            rm -f "/etc/network/interfaces.d/$IFACE"
            ifdown "$IFACE" >/dev/null 2>&1 || true
        fi
        ifup "$IFACE" >/dev/null 2>&1 || true
        systemctl restart NetworkManager 2>/dev/null || true
        amarelo "   Configuração anterior restaurada de $BACKUP"
    fi
}
configurar_rede

# Nome (URL) pelo qual o portal será acessado. O servidor responde a qualquer
# nome que chegue até ele — o que falta é a REDE saber traduzir esse nome para
# o IP, e isso se resolve no servidor DNS, não aqui.
NOME_PORTAL=""
USAR_MDNS=0

# O mDNS chega em UDP 5353. Firewalls com política de bloqueio descartam essa
# porta silenciosamente e o nome simplesmente "não resolve" nos clientes, sem
# nenhum erro visível — por isso o aviso explícito quando não dá para liberar.
liberar_mdns_no_firewall(){
    if systemctl is-active --quiet nftables 2>/dev/null && command -v nft >/dev/null 2>&1; then
        if nft list ruleset 2>/dev/null | grep -q '5353'; then
            verde "   Firewall (nftables) já libera a porta 5353."
        else
            amarelo "   ATENÇÃO: este servidor usa nftables e a porta 5353 (mDNS)"
            amarelo "   não está liberada — sem isso o nome NÃO resolve nos clientes."
            amarelo "   Para testar agora (vale até o próximo boot):"
            TABELA=$(nft list tables 2>/dev/null | awk '{print $2, $3}' | head -1)
            echo    "     sudo nft add rule ${TABELA:-inet filter} input udp dport 5353 accept"
            amarelo "   Para tornar permanente, acrescente a mesma regra ao arquivo"
            amarelo "   de configuração do firewall (ex.: /etc/nftables.conf)."
        fi
    elif command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -qi active; then
        ufw allow 5353/udp >/dev/null 2>&1 && verde "   Porta 5353 liberada no ufw."
    elif command -v firewall-cmd >/dev/null 2>&1; then
        firewall-cmd --permanent --add-service=mdns >/dev/null 2>&1 \
            && firewall-cmd --reload >/dev/null 2>&1 \
            && verde "   mDNS liberado no firewalld."
    else
        echo "   Nenhum firewall ativo detectado — nada a liberar."
    fi
}

configurar_nome(){
    local IP_ATUAL SUGESTAO
    IP_ATUAL=$(hostname -I 2>/dev/null | awk '{print $1}')
    SUGESTAO="$(echo "${ORG_SIGLA:-portal}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9').local"
    echo
    echo "   Endereço que as pessoas vão digitar no navegador, no lugar do IP."
    echo "   Terminando em .local, o próprio servidor anuncia o nome na rede"
    echo "   (mDNS) — não é preciso ter servidor DNS na unidade."
    perguntar NOME_PORTAL "Nome de acesso" "$SUGESTAO"
    [ -n "$NOME_PORTAL" ] || { echo "   O portal responderá por http://${IP_ATUAL:-<ip>}"; return; }

    if ! [[ "$NOME_PORTAL" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ ]]; then
        vermelho "   Nome inválido (use letras, números, ponto e hífen). Ignorado."
        NOME_PORTAL=""; return
    fi
    NOME_PORTAL="${NOME_PORTAL,,}"

    # Resolução no próprio servidor — útil para teste local e para o serviço.
    sed -i "/${MARCA_HOSTS}\$/d;/# portal-intranet\$/d" /etc/hosts
    echo "$IP_ATUAL  $NOME_PORTAL  ${MARCA_HOSTS}" >> /etc/hosts

    if [[ "$NOME_PORTAL" == *.local ]]; then
        # mDNS: o servidor responde por si mesmo, sem infraestrutura de DNS.
        # Windows 10/11, macOS e Linux resolvem .local nativamente.
        USAR_MDNS=1
        EXTRAS="$EXTRAS avahi-daemon avahi-utils"
        verde "   O nome $NOME_PORTAL será anunciado pelo próprio servidor (mDNS)."
        if [[ "${NOME_PORTAL%.local}" == *.* ]]; then
            amarelo "   Atenção: o mDNS só resolve nomes de um rótulo + .local"
            amarelo "   (ex.: cdpni.local). '$NOME_PORTAL' tem pontos a mais e"
            amarelo "   provavelmente não será resolvido pelos clientes."
        fi
    else
        amarelo "   Nomes fora de .local dependem de um servidor DNS na rede."
        amarelo "   Veja as opções em $DEST/ACESSO-POR-NOME.txt"
    fi
}
configurar_nome

# ── 5 · pacotes ───────────────────────────────────────────────────────────────
titulo "[5/8] Dependências"

# Piso de versão do Flask. Não é gosto: o download do backup chama
# send_file(download_name=...), que só existe do Flask 2.0 em diante. O Debian
# 11 traz o Flask 1.1, que instala sem reclamar, importa sem erro e só quebra
# meses depois, na primeira vez que alguém tenta baixar o backup. Por isso a
# checagem é pela versão entregue, e não pelo pacote estar presente.
FLASK_MIN="2.0"

# Imprime a versão do Flask visível para o python3 do sistema e devolve 0
# quando ela atende ao piso. Sem gunicorn, sem Flask ou com versão velha,
# devolve 1 — e o que foi impresso ainda serve para explicar a recusa.
flask_do_sistema() {
    command -v gunicorn >/dev/null 2>&1 || return 1
    python3 - "$FLASK_MIN" 2>/dev/null <<'EOP'
import sys
try:
    import flask, werkzeug            # os dois: o app importa de ambos
    try:
        from importlib.metadata import version
        bruto = version('flask')
    except Exception:                 # Python antigo ou pacote sem metadados
        bruto = flask.__version__
    print(bruto)
    minimo = tuple(int(p) for p in sys.argv[1].split('.'))
    atual  = tuple(int(p) for p in bruto.split('.')[:len(minimo)])
except Exception:
    sys.exit(1)
sys.exit(0 if atual >= minimo else 1)
EOP
}

apt-get update -qq || amarelo "   Aviso: não foi possível atualizar o cache do apt."

USAR_VENV=1
FLASK_VER=""
echo "   Procurando Flask $FLASK_MIN ou mais novo nos pacotes do sistema..."
if apt-get install -y -qq python3 python3-flask python3-werkzeug gunicorn 2>/dev/null \
   && FLASK_VER=$(flask_do_sistema); then
    USAR_VENV=0
    verde "   Flask $FLASK_VER do sistema serve. Sem ambiente virtual —"
    verde "   as atualizações de segurança vêm pelo apt, junto com o resto."
else
    if [ -n "$FLASK_VER" ]; then
        amarelo "   O sistema traz o Flask $FLASK_VER, anterior ao $FLASK_MIN."
    else
        amarelo "   O sistema não tem Flask e gunicorn utilizáveis."
    fi
    amarelo "   Vou montar um ambiente virtual com pip, sem mexer no Python do sistema."
    apt-get install -y -qq python3 python3-venv python3-pip
fi

if [ -n "$EXTRAS" ]; then
    echo "   Instalando também:$EXTRAS"
    # shellcheck disable=SC2086
    apt-get install -y -qq $EXTRAS
fi

# ── anúncio do nome na rede (mDNS), quando o nome termina em .local ───────────
if [ "$USAR_MDNS" = "1" ]; then
    echo "   Configurando o anúncio de $NOME_PORTAL na rede..."
    systemctl enable --now avahi-daemon >/dev/null 2>&1 || true

    # avahi-publish anuncia o nome sem mexer no hostname da máquina (o que
    # poderia quebrar outros serviços, como o Samba). O IP é lido a cada start,
    # então uma troca de IP se resolve reiniciando o serviço.
    cat > "$BIN_MDNS" <<'EOS'
#!/bin/sh
# Anuncia o nome recebido em $1 apontando para o IP principal desta máquina.
# Usado pelo serviço <portal>-nome.service.
set -eu
NOME="$1"
IP=$(hostname -I | awk '{print $1}')
if [ -z "$IP" ]; then
    echo "Sem endereço IP para anunciar." >&2
    exit 1
fi
echo "Anunciando $NOME em $IP via mDNS."
exec /usr/bin/avahi-publish -a -R "$NOME" "$IP"
EOS
    chmod +x "$BIN_MDNS"

    cat > "/etc/systemd/system/$SERVICO_MDNS" <<EOF
[Unit]
Description=Anuncia $NOME_PORTAL na rede local (mDNS)
After=network-online.target avahi-daemon.service
Wants=network-online.target
Requires=avahi-daemon.service

[Service]
Type=simple
ExecStart=$BIN_MDNS $NOME_PORTAL
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now "$SERVICO_MDNS" >/dev/null 2>&1 || true

    liberar_mdns_no_firewall

    sleep 2
    if avahi-resolve -n "$NOME_PORTAL" >/dev/null 2>&1; then
        verde "   $NOME_PORTAL já responde na rede."
    else
        amarelo "   O nome ainda não respondeu ao teste — confira depois com:"
        amarelo "   avahi-resolve -n $NOME_PORTAL"
    fi

    mkdir -p "$DEST"
    cat > "$DEST/ACESSO-POR-NOME.txt" <<EOF
Acesso ao portal por nome
=========================

Nome    : $NOME_PORTAL
IP      : $(hostname -I | awk '{print $1}')
Como    : mDNS — o próprio servidor anuncia o nome na rede local.
          Não é preciso ter servidor DNS na unidade.

Quem resolve sem instalar nada:
  - Windows 10 (versão 1703, de 2017, em diante) e Windows 11
  - macOS e a maioria das distribuições Linux
  - celulares Android e iOS na mesma rede Wi-Fi

Limites do mDNS (por desenho do protocolo):
  - vale dentro da MESMA rede/segmento. Não atravessa roteador: se houver
    outra sub-rede (VLAN), lá o nome não resolve — use o IP ou um DNS.
  - usa UDP na porta 5353; switches ou firewalls que bloqueiam multicast
    impedem a resolução.
  - Windows 7 e anteriores não resolvem .local sem instalar o Bonjour.

Comandos úteis (no servidor):
  systemctl status $SERVICO_MDNS   situação do anúncio
  avahi-resolve -n $NOME_PORTAL   testa a resolução
  systemctl restart $SERVICO_MDNS  reanuncia (use após trocar o IP)

Se um dia a unidade tiver servidor DNS, o nome pode ser publicado lá também;
os dois métodos convivem sem conflito.

Teste a partir de um computador Windows da rede:
  ping $NOME_PORTAL
  e depois abra http://$NOME_PORTAL no navegador
EOF
fi

# ── 5 · arquivos e personalização ─────────────────────────────────────────────
titulo "[6/8] Arquivos"
mkdir -p "$DEST"
if [ "$(realpath "$SRC")" != "$(realpath "$DEST")" ]; then
    cp -f  "$SRC/app.py" "$DEST/"
    cp -rf "$SRC/templates" "$DEST/"
    mkdir -p "$DEST/static"
    # Todo o CSS/JS (nunca listar arquivo por arquivo: um script novo passaria
    # despercebido). As imagens ficam de fora e são tratadas logo abaixo.
    cp -f "$SRC"/static/*.css "$SRC"/static/*.js "$DEST/static/"
    for base in logo brasao fundo; do
        for ext in png jpg jpeg webp svg; do
            [ -f "$SRC/static/$base.$ext" ] && [ ! -f "$DEST/static/$base.$ext" ] \
                && cp -f "$SRC/static/$base.$ext" "$DEST/static/"
        done
    done
fi
mkdir -p "$DEST/static/uploads"
echo "   Portal copiado para $DEST"

echo
echo "   Logo e foto de fundo são arquivos soltos em $DEST/static/ — podem ser"
echo "   trocados a qualquer momento sem mexer no código, aqui ou pelo painel."
if confirmar "Quer indicar os arquivos agora?"; then
    perguntar CAM_LOGO "Caminho do logo (Enter para manter o atual)" ""
    if [ -n "$CAM_LOGO" ] && [ -f "$CAM_LOGO" ]; then
        # brasao.png fica: é versionado e o serviço roda dentro do clone.
        # O logo.* enviado já tem precedência sobre ele na hora de exibir.
        rm -f "$DEST"/static/logo.*
        cp -f "$CAM_LOGO" "$DEST/static/logo.${CAM_LOGO##*.}"
        verde "   Logo instalado."
    elif [ -n "$CAM_LOGO" ]; then
        vermelho "   Arquivo não encontrado: $CAM_LOGO (logo mantido)"
    fi

    perguntar CAM_FUNDO "Caminho da foto de fundo (Enter para pular)" ""
    if [ -n "$CAM_FUNDO" ] && [ -f "$CAM_FUNDO" ]; then
        rm -f "$DEST"/static/fundo.*
        cp -f "$CAM_FUNDO" "$DEST/static/fundo.${CAM_FUNDO##*.}"
        verde "   Foto de fundo instalada."
    elif [ -n "$CAM_FUNDO" ]; then
        vermelho "   Arquivo não encontrado: $CAM_FUNDO (fundo mantido)"
    fi
fi

# PY_EXEC é o interpretador que enxerga o Flask. No Debian 11 e 10 o Flask só
# existe dentro do venv, então o python3 do sistema não serve para nada que
# importe o app — inclusive a criação do banco, logo abaixo.
if [ "$USAR_VENV" = "1" ]; then
    python3 -m venv "$DEST/venv"
    "$DEST/venv/bin/pip" install -q --upgrade pip
    # O piso é o mesmo cobrado do apt; o teto quem escolhe é o pip, que resolve
    # a última versão compatível com o Python desta máquina.
    "$DEST/venv/bin/pip" install -q "flask>=$FLASK_MIN" gunicorn
    PY_BIN="$DEST/venv/bin/gunicorn"
    PY_EXEC="$DEST/venv/bin/python"
else
    PY_BIN="$(command -v gunicorn)"
    PY_EXEC="/usr/bin/python3"
fi

# Prova de que o interpretador escolhido enxerga o que o app importa. Falhar
# aqui é bem mais barato do que falhar na criação do banco, logo abaixo, onde o
# sintoma ("não foi possível criar o banco") não diz nada sobre a causa.
if ! "$PY_EXEC" -c "import flask, werkzeug" >/dev/null 2>&1; then
    vermelho "   As dependências não ficaram utilizáveis em $PY_EXEC."
    vermelho "   Confira o erro com: $PY_EXEC -c \"import flask, werkzeug\""
    exit 1
fi

id -u "$USUARIO" >/dev/null 2>&1 || useradd --system --home "$DEST" --shell /usr/sbin/nologin "$USUARIO"
chown -R "$USUARIO:$USUARIO" "$DEST"

# O serviço roda dentro do próprio clone, então a pasta passa a pertencer ao
# usuário do serviço. Sem isto o `sudo git pull` seguinte pára com "detected
# dubious ownership": o git recusa repositório de outro dono.
if [ -d "$DEST/.git" ] && command -v git >/dev/null 2>&1; then
    git config --global --get-all safe.directory 2>/dev/null | grep -qx "$DEST" \
        || git config --global --add safe.directory "$DEST"
fi

# Banco criado agora, antes de o serviço subir, com a identidade e a senha
# informadas no começo — assim o primeiro acesso já funciona.
if [ -n "$SENHA_ADMIN" ]; then
    SEED="import sys; sys.path.insert(0,'$DEST'); import app"
    ERRO_SEED=""
    export INTRANET_ADMIN_SENHA="$SENHA_ADMIN"
    export INTRANET_ORG_NOME="$ORG_NOME" INTRANET_ORG_SIGLA="$ORG_SIGLA" INTRANET_ORG_SUB="$ORG_SUB"
    ERRO_SEED=$(runuser -u "$USUARIO" --preserve-environment -- "$PY_EXEC" -c "$SEED" 2>&1) || true
    if [ ! -f "$DEST/dados.db" ]; then
        ERRO_SEED=$("$PY_EXEC" -c "$SEED" 2>&1) || true   # plano B: como root
        chown -R "$USUARIO:$USUARIO" "$DEST"
    fi
    unset INTRANET_ADMIN_SENHA INTRANET_ORG_NOME INTRANET_ORG_SIGLA INTRANET_ORG_SUB
    if [ ! -f "$DEST/dados.db" ]; then
        vermelho "   Não foi possível criar o banco de dados."
        # O erro guardado poupa uma segunda rodada só para descobrir o motivo.
        [ -n "$ERRO_SEED" ] && printf '%s\n' "$ERRO_SEED" | sed 's/^/     /'
        vermelho "   Para repetir à mão: $PY_EXEC -c \"$SEED\""
        exit 1
    fi
fi
SENHA_ADMIN=""   # não guardar a senha em memória além do necessário

# ── 6 · serviço ───────────────────────────────────────────────────────────────
titulo "[7/8] Serviço systemd (porta $PORTA)"
cat > "/etc/systemd/system/$SERVICO" <<EOF
[Unit]
Description=Portal Interno
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$DEST
ExecStart=$PY_BIN --chdir $DEST --workers 3 --bind 0.0.0.0:$PORTA --access-logfile - app:app
Restart=always
RestartSec=3
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ProtectSystem=full
ReadWritePaths=$DEST

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload

# Porta ocupada por outro serviço só apareceria depois, como "Address already
# in use" repetido no journal enquanto o systemd reinicia em laço — e no
# navegador como erro genérico. Melhor dizer agora, com o nome do culpado.
if command -v ss >/dev/null 2>&1 && ss -lntH "sport = :$PORTA" 2>/dev/null | grep -q .; then
    _OCUPANTE_INFO="$(ss -lptnH "sport = :$PORTA" 2>/dev/null)"
    vermelho "   A porta $PORTA já está ocupada por outro processo:"
    echo "$_OCUPANTE_INFO" | sed 's/^/     /'
    echo
    echo
    echo "   O portal não vai conseguir subir enquanto isso não for resolvido."
    echo

    # Pela convenção do projeto a 80 é DESTE portal — o único acessado sem
    # porta na barra de endereços. Mover o portal resolve o sintoma e estraga
    # o motivo: o usuário passa a ter que digitar a porta. Por isso a orientação
    # é liberar a 80, não fugir dela.
    if [ "$PORTA" = "80" ]; then
        echo "   Pela convenção do projeto a porta 80 é deste portal:"
        echo "     80    portal-sistemas (este)  atalhos, todos os usuários"
        echo "     8080  portal-gateway  (GWOS)  administração"
        echo "     8443  portal-samba            administração"
        echo "   Liberá-la é melhor que mudar de porta: é o único endereço que"
        echo "   o usuário digita sem sufixo."
        echo
    fi

    if echo "$_OCUPANTE_INFO" | grep -q nginx; then
        echo "   Quem ocupa a porta é o nginx. Veja qual site a segura:"
        echo "     grep -rn listen /etc/nginx/sites-enabled/"
        echo
        echo "   Se for o site de fábrica (chamado default), pode remover — ele"
        echo "   só serve a página de boas-vindas do nginx:"
        echo "     sudo rm -f /etc/nginx/sites-enabled/default"
        echo "     sudo nginx -t && sudo systemctl reload nginx"
    elif echo "$_OCUPANTE_INFO" | grep -q gunicorn; then
        echo "   É um gunicorn de instalação anterior. Para encerrá-lo:"
        echo "     sudo pkill -f gunicorn"
    else
        echo "   Encerre o processo acima, ou instale numa porta livre:"
        # 8080 e 8443 estão reservadas aos outros dois portais — sugerir uma
        # delas trocaria este conflito por outro, mais difícil de perceber.
        echo "     sudo ./instalar.sh 8081"
    fi
    echo
    confirmar "Tentar subir mesmo assim?" || {
        amarelo "   Serviço criado mas não iniciado. Depois de liberar a porta:"
        echo   "     systemctl start $PORTAL_NOME"
        exit 1
    }
fi

systemctl enable --now "$SERVICO"

# ── 7 · firewall ──────────────────────────────────────────────────────────────
titulo "[8/8] Firewall"
if command -v ufw >/dev/null 2>&1; then
    ufw allow "$PORTA/tcp" >/dev/null 2>&1 && echo "   Porta $PORTA liberada no ufw."
else
    echo "   Nenhum ufw instalado — nada a fazer."
fi

sleep 2
IP_LOCAL=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
if systemctl is-active --quiet portal; then
    verde "════════════════════════════════════════════════════════════"
    verde " Portal instalado e ATIVO."
    SUFIXO_PORTA=$( [ "$PORTA" != 80 ] && echo ":$PORTA" )
    echo  "   Endereço:  http://${IP_LOCAL:-<ip-do-servidor>}${SUFIXO_PORTA}"
    if [ -n "$NOME_PORTAL" ]; then
        echo  "              http://${NOME_PORTAL}${SUFIXO_PORTA}  (após cadastrar no DNS —"
        echo  "              veja $DEST/ACESSO-POR-NOME.txt)"
    fi
    echo  "   Usuário:   admin  (senha definida por você nesta instalação)"
    echo  "   Logo:      $DEST/static/logo.*   (troque o arquivo quando quiser)"
    echo  "   Fundo:     $DEST/static/fundo.*  (idem)"
    echo  "   Status:    systemctl status ${SERVICO}"
    echo  "   Logs:      journalctl -u ${SERVICO} -f"
    verde "════════════════════════════════════════════════════════════"
else
    # A unit chama-se portal-sistemas.service. As mensagens diziam
    # 'journalctl -u portal', nome que nunca existiu depois da renomeação:
    # quem seguia a instrução via um journal vazio e ficava sem pista.
    vermelho "O serviço ${SERVICO} não subiu."
    echo ""
    echo "── últimas linhas do journal ──"
    journalctl -u "$SERVICO" -n 20 --no-pager 2>/dev/null || true
    echo ""

    # Causa mais comum: outro processo já ocupa a porta. O gunicorn morre no
    # bind e, sem esta checagem, o motivo fica só no journal.
    OCUPANTE=$(ss -lntp 2>/dev/null | awk -v p=":${PORTA}\$" '$4 ~ p {print $NF}' | head -1) || OCUPANTE=""
    if [ -n "$OCUPANTE" ]; then
        vermelho "A porta ${PORTA} já está ocupada por: ${OCUPANTE}"
        echo  "   Libere a porta, ou reinstale em outra: sudo ./instalar.sh <porta>"
        echo  "   Pela convenção do projeto a 80 é deste portal; o painel do"
        echo  "   GWOS fica na 8080 e o portal do Samba na 8443."
    fi
    echo ""
    echo  "   Detalhes: journalctl -u ${SERVICO} -n 40 --no-pager"
    exit 1
fi
