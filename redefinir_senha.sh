#!/bin/bash
# =============================================================================
#  Redefine a senha de um usuário do portal de sistemas
# =============================================================================
#  Uso:  sudo ./redefinir_senha.sh [usuario]
#        sudo ./redefinir_senha.sh listar
#
#  Existe porque não há senha padrão e reinstalar NÃO recupera o acesso: o
#  instalador detecta o banco e preserva os usuários. Sem este script, alguém
#  que esquecesse a senha do 'admin' teria que mexer no SQLite à mão ou apagar
#  o banco — perdendo atalhos, ramais e usuários já cadastrados.
#
#  Nada de senha padrão aqui também: a nova senha é digitada por quem roda.
# =============================================================================

set -euo pipefail

PORTAL_NOME=portal-sistemas
DEST=/opt/$PORTAL_NOME
SERVICO=$PORTAL_NOME.service
USUARIO_SVC=$PORTAL_NOME

vermelho(){ printf '\033[31m%s\033[0m\n' "$*"; }
verde()   { printf '\033[32m%s\033[0m\n' "$*"; }
amarelo() { printf '\033[33m%s\033[0m\n' "$*"; }
titulo()  { printf '\n\033[1;36m%s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { vermelho "Execute como root: sudo $0"; exit 1; }

# Instalações anteriores usaram outros nomes de diretório.
if [ ! -f "$DEST/dados.db" ]; then
    for _alt in /opt/cdpni-portal /opt/portal /opt/intranet; do
        [ -f "$_alt/dados.db" ] && { DEST="$_alt"; break; }
    done
fi
DB="$DEST/dados.db"
[ -f "$DB" ] || { vermelho "Banco não encontrado em $DEST/dados.db — o portal está instalado?"; exit 1; }

command -v python3 >/dev/null 2>&1 || { vermelho "python3 não encontrado."; exit 1; }
python3 -c 'import werkzeug.security' 2>/dev/null \
    || { vermelho "python3-werkzeug não instalado (apt install python3-werkzeug)."; exit 1; }

# ---------------------------------------------------------------------------
# listar
# ---------------------------------------------------------------------------
listar() {
    titulo "Usuários cadastrados"
    python3 - "$DB" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
linhas = con.execute(
    'SELECT usuario, nome, admin, ativo, ultimo_acesso FROM usuarios ORDER BY usuario'
).fetchall()
print(f"  {'USUÁRIO':<20} {'NOME':<26} {'PERFIL':<8} {'STATUS':<9} ÚLTIMO ACESSO")
for u, n, adm, ativo, ult in linhas:
    print(f"  {u:<20} {(n or '')[:25]:<26} "
          f"{'admin' if adm else 'comum':<8} "
          f"{'ativo' if ativo else 'inativo':<9} {ult or '—'}")
print(f"\n  {len(linhas)} usuário(s).")
PY
}

if [ "${1:-}" = "listar" ]; then
    listar
    exit 0
fi

# ---------------------------------------------------------------------------
# qual usuário
# ---------------------------------------------------------------------------
titulo "Redefinir senha — portal de sistemas"
echo "   Banco: $DB"
listar

ALVO="${1:-}"
if [ -z "$ALVO" ]; then
    echo ""
    read -r -p "   Usuário [admin]: " ALVO
    ALVO="${ALVO:-admin}"
fi

EXISTE=$(python3 - "$DB" "$ALVO" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
r = con.execute('SELECT 1 FROM usuarios WHERE usuario = ?', (sys.argv[2],)).fetchone()
print('sim' if r else 'nao')
PY
)
[ "$EXISTE" = "sim" ] || { vermelho "   Usuário '$ALVO' não existe. Use: $0 listar"; exit 1; }

# ---------------------------------------------------------------------------
# nova senha — mesma exigência do instalador
# ---------------------------------------------------------------------------
echo ""
echo "   Requisitos: mínimo 8 caracteres, com maiúscula, minúscula e número."
echo ""
# Todos os testes ficam como condição de if/elif: um validador chamado solto
# seria interceptado pelo 'set -e' e mataria o script em vez de repetir a
# pergunta — foi assim que o bootstrap do Samba abortava com senha fraca.
while true; do
    read -r -s -p "   Nova senha para '$ALVO': " S1; echo
    read -r -s -p "   Repita a senha: " S2; echo
    if [[ "$S1" == *[[:cntrl:]]* ]]; then
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
        break
    fi
done

# ---------------------------------------------------------------------------
# grava
# ---------------------------------------------------------------------------
# A senha vai por variável de ambiente, não por argumento: argumento aparece
# no 'ps' de qualquer usuário da máquina enquanto o comando roda.
_PORTAL_NOVA="$S1" python3 - "$DB" "$ALVO" <<'PY'
import os, sqlite3, sys
from werkzeug.security import generate_password_hash

db, usuario = sys.argv[1], sys.argv[2]
con = sqlite3.connect(db)
with con:
    # Reativa de passagem: uma conta inativa aceita a senha nova e continua
    # sem conseguir entrar, o que parece que o reset não funcionou.
    con.execute('UPDATE usuarios SET senha_hash = ?, ativo = 1 WHERE usuario = ?',
                (generate_password_hash(os.environ['_PORTAL_NOVA']), usuario))
con.close()
PY
unset S1 S2

# O serviço roda como o usuário do portal. O sqlite pode criar -wal/-shm ao
# escrever, e criados pelo root eles impediriam a próxima escrita do serviço.
if id "$USUARIO_SVC" >/dev/null 2>&1; then
    chown "$USUARIO_SVC":"$USUARIO_SVC" "$DB" "$DB"-wal "$DB"-shm 2>/dev/null || true
fi

verde ""
verde "   Senha de '$ALVO' redefinida."
if [ "$(systemctl is-active "$SERVICO" 2>/dev/null || true)" = "active" ]; then
    echo "   O serviço não precisa reiniciar — a senha é lida do banco a cada login."
else
    amarelo "   O serviço $SERVICO não está ativo. Para subir:"
    echo    "     sudo systemctl start $SERVICO"
fi
_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "   Entre em: http://${_IP:-<ip-do-servidor>}"
echo ""
