"""
Portal Interno — Centro de Detenção Provisória de Nova Independência/SP

Página inicial com os sistemas usados pela unidade, banner rotativo e barra
lateral de avisos. Tudo (links, banners, avisos, usuários, cores e a imagem
de fundo) é gerenciado pelo administrador na própria interface.

Requisitos: python3, flask, werkzeug. Banco: SQLite (arquivo dados.db).
"""

import io
import json
import os
import re
import secrets
import sqlite3
import sys
import time
import zipfile
from datetime import datetime
from html.parser import HTMLParser
from functools import wraps

from flask import (Flask, abort, flash, g, get_flashed_messages, jsonify, redirect,
                   render_template, request, send_file, session, url_for)
from markupsafe import Markup, escape
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_PATH    = os.environ.get('INTRANET_DB', os.path.join(BASE_DIR, 'dados.db'))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
UPLOAD_DIR = os.path.join(STATIC_DIR, 'uploads')
KEY_FILE   = os.path.join(BASE_DIR, 'secret.key')
TRAVA_FILE = KEY_FILE + '.lock'
EXT_OK     = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}

# Logo e foto de fundo são arquivos fixos em static/. Basta substituir o
# arquivo (pelo painel ou copiando por cima no servidor) que o site muda — não
# há nome aleatório nem caminho guardado no banco, e nada a alterar no código.
FUNDO_NOMES = ('fundo.jpg', 'fundo.jpeg', 'fundo.png', 'fundo.webp')
LOGO_NOMES  = ('logo.png', 'logo.jpg', 'logo.jpeg', 'logo.webp', 'logo.svg',
               'brasao.png')
# O que o envio de logo pode apagar. `brasao.png` fica de fora: é o brasão que
# acompanha o repositório e o serviço roda dentro do próprio clone — apagar
# arquivo versionado sujaria a árvore e travaria o `git pull` seguinte. Como
# logo_atual() já prefere logo.* a brasao.png, manter o arquivo não muda nada
# na tela e ainda serve de reserva se o logo enviado for removido.
LOGO_ENVIADO = tuple(n for n in LOGO_NOMES if n != 'brasao.png')

# Marca d'água opcional de cada cartão do painel: static/marca-<bloco>.<ext>.
# Trocar o arquivo troca a imagem, como no logo e no fundo.
MARCA_EXTS = ('.png', '.svg', '.webp', '.jpg', '.jpeg')


def marca_atual(bloco):
    return _arquivo_versionado(tuple(f'marca-{bloco}{e}' for e in MARCA_EXTS))


def _arquivo_versionado(nomes, padrao=None):
    """(nome, versão) do primeiro arquivo existente; a versão é a data de
    modificação, para o navegador não mostrar a imagem antiga do cache."""
    for nome in nomes:
        caminho = os.path.join(STATIC_DIR, nome)
        if os.path.isfile(caminho):
            return nome, int(os.path.getmtime(caminho))
    return padrao, 0


def fundo_atual():
    return _arquivo_versionado(FUNDO_NOMES)


def logo_atual():
    return _arquivo_versionado(LOGO_NOMES, padrao='brasao.png')


# ── ícones ─────────────────────────────────────────────────────────────────────

# Desenhos em traçado, sem arquivo externo nem fonte de ícones: o mesmo símbolo
# serve no ladrilho escuro, no menu e no cartão claro porque a cor vem do texto
# (currentColor). Emoji foi o que se usou na primeira versão — cada sistema
# operacional desenha de um jeito e o painel ficava desalinhado.
ICONES = {
    'inicio':     '<path d="M3 10.8 12 3.5l9 7.3"/><path d="M5.3 9.6V20.5h13.4V9.6"/>'
                  '<path d="M9.6 20.5v-6.2h4.8v6.2"/>',
    'telefone':   '<path d="M7.6 3.5H4.8A1.8 1.8 0 0 0 3 5.3c0 8.4 7.3 15.7 15.7 15.7a1.8 '
                  '1.8 0 0 0 1.8-1.8v-2.8l-4.3-1.4-2 2a14.6 14.6 0 0 1-6.2-6.2l2-2z"/>',
    'usuarios':   '<circle cx="9" cy="8" r="3.3"/><path d="M3.2 20.3c0-3.2 2.6-5.4 5.8-5.4'
                  's5.8 2.2 5.8 5.4"/><path d="M16.4 5.1a3.3 3.3 0 0 1 0 6.2"/>'
                  '<path d="M17.6 15.2c2.1.5 3.6 2.2 3.6 5.1"/>',
    'pessoa':     '<circle cx="12" cy="8.2" r="3.8"/><path d="M4.8 20.6c0-3.9 3.2-6.4 '
                  '7.2-6.4s7.2 2.5 7.2 6.4"/>',
    'documento':  '<path d="M13.4 3.2H6.6v17.6h10.8V7.2z"/><path d="M13.4 3.2v4h4"/>'
                  '<path d="M9.4 12.4h5.2M9.4 16h5.2"/>',
    'calendario': '<rect x="3.4" y="5.2" width="17.2" height="15.4" rx="2"/>'
                  '<path d="M3.4 10h17.2M8.2 3.4v3.6M15.8 3.4v3.6"/>',
    'fone':       '<path d="M4 15.5v-3a8 8 0 0 1 16 0v3"/>'
                  '<rect x="2.6" y="14.4" width="4.6" height="6.2" rx="2"/>'
                  '<rect x="16.8" y="14.4" width="4.6" height="6.2" rx="2"/>',
    'arquivo':    '<rect x="2.8" y="4.2" width="18.4" height="4.2" rx="1.2"/>'
                  '<path d="M4.6 8.4v10.2a1.8 1.8 0 0 0 1.8 1.8h11.2a1.8 1.8 0 0 0 '
                  '1.8-1.8V8.4"/><path d="M9.8 12.4h4.4"/>',
    'grafico':    '<path d="M3.4 20.6h17.2"/><path d="M6.6 20.6v-6.4M11.4 20.6V6.8'
                  'M16.2 20.6v-9.6"/>',
    'engrenagem': '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.6v2.6M12 18.8v2.6'
                  'M21.4 12h-2.6M5.2 12H2.6M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8'
                  'M18.4 18.4l-1.8-1.8M7.4 7.4 5.6 5.6"/>',
    'megafone':   '<path d="M3.4 9.6v4.8h3.4l7.4 4.4V5.2L6.8 9.6z"/>'
                  '<path d="M17.4 9a4.2 4.2 0 0 1 0 6"/><path d="M6.8 14.4v4.2h2.8"/>',
    'sino':       '<path d="M18 9.4a6 6 0 1 0-12 0c0 5.2-2 6.8-2 6.8h16s-2-1.6-2-6.8z"/>'
                  '<path d="M13.7 20a2 2 0 0 1-3.4 0"/>',
    'envelope':   '<rect x="2.8" y="5" width="18.4" height="14" rx="2"/>'
                  '<path d="m3.6 6.4 8.4 6.2 8.4-6.2"/>',
    'lupa':       '<circle cx="10.8" cy="10.8" r="6.4"/><path d="m15.6 15.6 5 5"/>',
    'barras':     '<path d="M3.6 6.6h16.8M3.6 12h16.8M3.6 17.4h16.8"/>',
    'sair':       '<path d="M9.4 20.6H5.6a1.8 1.8 0 0 1-1.8-1.8V5.2a1.8 1.8 0 0 1 '
                  '1.8-1.8h3.8"/><path d="m15.4 16.6 4.8-4.6-4.8-4.6"/><path d="M20.2 12H9"/>',
    'marcador':   '<path d="M6.4 3.6h11.2v17l-5.6-4-5.6 4z"/>',
    'grade':      '<rect x="3.4" y="3.4" width="7" height="7" rx="1.4"/>'
                  '<rect x="13.6" y="3.4" width="7" height="7" rx="1.4"/>'
                  '<rect x="3.4" y="13.6" width="7" height="7" rx="1.4"/>'
                  '<rect x="13.6" y="13.6" width="7" height="7" rx="1.4"/>',
    'escudo':     '<path d="M12 3 4.6 6v6c0 4.5 3.1 8.1 7.4 9.4 4.3-1.3 7.4-4.9 7.4-9.4V6z"/>',
    'bolo':       '<path d="M4.4 13.6c0-1.5 1.2-2.6 2.6-2.6h10c1.4 0 2.6 1.1 2.6 2.6v7H4.4z"/>'
                  '<path d="M12 11V7.8M8.2 11V8.6M15.8 11V8.6"/>'
                  '<path d="M4.4 16.4c1.6 0 1.6 1.4 3.1 1.4s1.6-1.4 3.1-1.4 1.6 1.4 3.1 1.4'
                  ' 1.6-1.4 3.1-1.4 1.6 1.4 3.1 1.4"/>',
    'relogio':    '<circle cx="12" cy="12" r="8.6"/><path d="M12 7v5.3l3.4 2"/>',
    'cifrao':     '<path d="M12 3.4v17.2"/><path d="M16.2 7.2H9.9a2.9 2.9 0 0 0 0 5.8h4.2a2.9'
                  ' 2.9 0 0 1 0 5.8H7.4"/>',
    'raio':       '<path d="M13.4 2.6 4.6 13.6h6.2l-.6 7.8 8.8-11h-6.2z"/>',
    'monitor':    '<rect x="2.8" y="4" width="18.4" height="12.4" rx="2"/>'
                  '<path d="M8.6 20.4h6.8M12 16.4v4"/>',
    'chave':      '<circle cx="7.6" cy="16.4" r="3.6"/>'
                  '<path d="m10.2 13.8 8.4-8.4M16.2 7.8l2 2M13.8 10.2l2 2"/>',
    'cadeado':    '<rect x="4.6" y="10.4" width="14.8" height="10" rx="2"/>'
                  '<path d="M8.2 10.4V7.8a3.8 3.8 0 0 1 7.6 0v2.6"/>',
    'globo':      '<circle cx="12" cy="12" r="8.8"/><path d="M3.2 12h17.6"/>'
                  '<path d="M12 3.2a13.6 13.6 0 0 1 0 17.6 13.6 13.6 0 0 1 0-17.6z"/>',
    'mapa':       '<path d="M12 21.4s6.8-6 6.8-11a6.8 6.8 0 1 0-13.6 0c0 5 6.8 11 6.8 11z"/>'
                  '<circle cx="12" cy="10.2" r="2.6"/>',
    'veiculo':    '<path d="M2.8 16.2V9.4h10.4v6.8"/><path d="M13.2 11.4h3.6l3.4 3.2v1.6h-7z"/>'
                  '<circle cx="7" cy="17.6" r="2"/><circle cx="17" cy="17.6" r="2"/>',
    'camera':     '<path d="M3.4 8.6h3.8l1.4-2.2h6.8l1.4 2.2h3.8v10.2H3.4z"/>'
                  '<circle cx="12" cy="13.4" r="3.4"/>',
    'livro':      '<path d="M4.2 4.4h5.2c1.4 0 2.6 1.1 2.6 2.5v13c0-1.1-1-2-2.2-2H4.2z"/>'
                  '<path d="M19.8 4.4h-5.2c-1.4 0-2.6 1.1-2.6 2.5v13c0-1.1 1-2 2.2-2h5.6z"/>',
    'prancheta':  '<rect x="5.4" y="4.6" width="13.2" height="16" rx="1.8"/>'
                  '<rect x="9" y="2.8" width="6" height="3.6" rx="1.2"/>'
                  '<path d="M9 11.4h6M9 15h6"/>',
    'pasta':      '<path d="M3.4 6.6a1.8 1.8 0 0 1 1.8-1.8h3.8l2 2.6h8.4a1.8 1.8 0 0 1 1.8 '
                  '1.8v9.6a1.8 1.8 0 0 1-1.8 1.8H5.2a1.8 1.8 0 0 1-1.8-1.8z"/>',
    'estrela':    '<path d="m12 3.4 2.7 5.5 6.1.9-4.4 4.3 1 6-5.4-2.9-5.4 2.9 1-6-4.4-4.3'
                  ' 6.1-.9z"/>',
    'balanca':    '<path d="M12 3.6v16.8M6.6 20.4h10.8"/><path d="M12 6.4 4.4 8.2M12 6.4l7.6 '
                  '1.8"/><path d="M4.4 8.2 1.9 14.2h5z"/><path d="M19.6 8.2l-2.5 6h5z"/>',
    'predio':     '<rect x="4.6" y="3.4" width="14.8" height="17.2" rx="1.4"/>'
                  '<path d="M8.4 7.6h2M13.6 7.6h2M8.4 11.6h2M13.6 11.6h2'
                  'M10.4 20.6v-4.4h3.2v4.4"/>',
    'saude':      '<path d="M3 12.4h4l2-4.4 3 9 2.4-6 1.6 3h5"/>',
    'ferramenta': '<path d="M20.2 6.6a5.2 5.2 0 0 1-6.9 6.9l-6.7 6.7a2 2 0 0 1-2.8-2.8l6.7-6.7'
                  'a5.2 5.2 0 0 1 6.9-6.9l-3.1 3.1.9 2.9 2.9.9z"/>',
    'alerta':     '<path d="M12 3.8 2.8 20.2h18.4z"/><path d="M12 9.8v4.6M12 17.4h.01"/>',
    'externo':    '<path d="M14.4 4.6h5v5"/><path d="m19.4 4.6-8 8"/><path d="M18.2 13.6v5.2a'
                  '1.8 1.8 0 0 1-1.8 1.8H5.2a1.8 1.8 0 0 1-1.8-1.8V7.6a1.8 1.8 0 0 1 '
                  '1.8-1.8h5.2"/>',
    'aplicativo': '<rect x="3.4" y="3.4" width="17.2" height="17.2" rx="4"/>'
                  '<circle cx="12" cy="12" r="3.2"/>',
    'confere':    '<circle cx="12" cy="12" r="8.8"/><path d="m8 12.2 2.8 2.8 5.2-5.6"/>',
    'lua':        '<path d="M20.6 14.4A8.8 8.8 0 0 1 9.6 3.4a8.8 8.8 0 1 0 11 11z"/>',
    'sol':        '<circle cx="12" cy="12" r="4.2"/><path d="M12 2.4v2.4M12 19.2v2.4'
                  'M21.6 12h-2.4M4.8 12H2.4M18.8 5.2l-1.7 1.7M6.9 17.1l-1.7 1.7'
                  'M18.8 18.8l-1.7-1.7M6.9 6.9 5.2 5.2"/>',
}

# Escolha explícita de "sem símbolo" — diferente de campo vazio, que significa
# apenas que ninguém escolheu e vale o ícone genérico.
SEM_ICONE = 'nenhum'

# Ícones enviados pelo administrador, em static/icones/. Guardados no banco
# como "arquivo:<nome>" para não colidirem com os nomes do catálogo interno.
ICONES_DIR  = os.path.join(STATIC_DIR, 'icones')
ICONE_ARQ   = 'arquivo:'
ICONE_EXTS  = {'.svg', '.png', '.webp', '.jpg', '.jpeg'}


def icones_enviados():
    """Nomes dos ícones em static/icones/, em ordem alfabética."""
    try:
        return sorted(n for n in os.listdir(ICONES_DIR)
                      if os.path.splitext(n)[1].lower() in ICONE_EXTS)
    except OSError:
        return []


# Zoom por ícone, em porcentagem, guardado em config como
# "icone_zoom:<arquivo>". Ícone baixado da internet costuma vir com margem
# transparente embutida: mesmo na caixa do tamanho certo, o desenho ocupa
# menos da metade dela e parece menor que os do catálogo, que são desenhados
# de ponta a ponta. O zoom amplia o desenho sem mudar o espaço que o ícone
# ocupa no layout — por isso é `transform`, e não largura.
ICONE_ZOOM = 'icone_zoom:'
# O teto vem do selo mais apertado: o ladrilho desenha um ícone de 16px dentro
# de um quadrado colorido de 30px, razão 1,875. Em 175% o desenho fica com 28px
# e sobra 1px de cada lado — passando disso ele começa a vazar para fora do
# quadrado, que é pior do que o ícone pequeno que se queria corrigir.
ZOOM_MIN, ZOOM_MAX, ZOOM_PADRAO = 100, 175, 100


def zooms_icones():
    """Zoom de cada ícone enviado, lido uma vez por requisição.

    O ic() é chamado dezenas de vezes para montar uma página, e cfg() varre a
    tabela config inteira a cada chamada — guardar em `g` troca isso por uma
    consulta só."""
    if 'zoom_icones' not in g:
        g.zoom_icones = {
            r['chave'][len(ICONE_ZOOM):]: _int(r['valor'], ZOOM_PADRAO)
            for r in db().execute('SELECT chave, valor FROM config'
                                  ' WHERE chave LIKE ?', (ICONE_ZOOM + '%',))}
    return g.zoom_icones


def icone_de_arquivo(valor):
    """Nome do arquivo se `valor` aponta para um ícone enviado que existe.

    Confere a existência para um ícone apagado não deixar imagem quebrada no
    painel — nesse caso o item volta para o símbolo genérico."""
    if not (valor or '').startswith(ICONE_ARQ):
        return None
    nome = secure_filename(valor[len(ICONE_ARQ):])
    if nome and os.path.isfile(os.path.join(ICONES_DIR, nome)):
        return nome
    return None

# A primeira versão guardava emoji nessas colunas. Traduzir aqui evita mexer no
# banco de quem já cadastrou itens — e o menu antigo continua desenhado igual.
EMOJI_ICONE = {
    '⌂': 'inicio', '☎': 'telefone', '👥': 'usuarios', '🗎': 'documento',
    '🗓': 'calendario', '🎧': 'fone', '🗄': 'arquivo', '📊': 'grafico',
    '⚙': 'engrenagem', '📢': 'megafone', '🔖': 'marcador', '🧭': 'grade',
    '🎂': 'bolo', '🛡': 'escudo', '▦': 'grade', '🔑': 'chave', '▸': 'aplicativo',
}


def nome_icone(valor):
    """Nome de ícone válido a partir do que está gravado (nome novo ou emoji).

    'nenhum' é escolha explícita de não mostrar símbolo. Vazio continua sendo
    "não escolheram nada" e cai no genérico — senão todo item já cadastrado
    perderia o ícone de uma vez."""
    valor = (valor or '').strip()
    if valor == SEM_ICONE or valor in ICONES:
        return valor
    if icone_de_arquivo(valor):
        return valor
    return EMOJI_ICONE.get(valor, 'aplicativo')


BACKUP_DIR = os.path.join(BASE_DIR, 'backups')

app = Flask(__name__)
# 64 MB: um backup carrega o banco mais a foto de fundo, o logo e as imagens
# do banner. As imagens avulsas continuam limitadas pela extensão aceita.
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024
# Cookie de sessão: inacessível ao JavaScript e não enviado em requisições de
# outros sites. `Secure` só liga com PORTAL_COOKIE_SEGURO=1, que é para quando o
# portal é servido por HTTPS — numa intranet em HTTP, o cookie seguro nunca
# chegaria de volta e ninguém conseguiria entrar.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('PORTAL_COOKIE_SEGURO') == '1',
)


def _secret_key():
    """Chave de sessão persistente — sem ela, todo restart desloga os usuários.

    O gunicorn sobe três workers que importam este módulo ao mesmo tempo. Gerar
    a chave sem combinar dava a cada um a sua: quem escrevesse por último ficava
    com o arquivo, mas os outros dois seguiam usando a que geraram na memória.
    O cookie assinado por um worker era ilegível para os demais, e o login
    morria em "Sessão expirada" toda vez que o POST caía num worker diferente
    do que desenhou o formulário.

    Um marcador criado com O_EXCL elege um único processo para gravar: ele
    escreve e devolve a chave que gravou, e os demais esperam o marcador sumir
    para reler o arquivo dele. Vale também para a chave vazia, que é como o
    arquivo fica quando o disco enche — o modo 'w' trunca antes de escrever, e
    é a escrita que falha.
    """
    limite = time.monotonic() + 5
    while time.monotonic() < limite:
        try:
            with open(KEY_FILE, 'r') as f:
                k = f.read().strip()
            if k:
                return k
        except FileNotFoundError:
            pass

        # Chave ausente ou vazia. Só um processo pode reparar: os demais
        # esperariam para sempre por uma chave que cada um sobrescreveria. O
        # marcador criado com O_EXCL elege esse processo — os outros dormem e
        # releem o que ele gravou.
        try:
            marca = os.open(TRAVA_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            time.sleep(0.05)
            continue
        try:
            nova = secrets.token_hex(32)
            fd = os.open(KEY_FILE, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(nova)
            return nova
        finally:
            # Solta o marcador mesmo se a escrita falhar (disco cheio), senão a
            # primeira falha travaria todo boot seguinte.
            os.close(marca)
            os.unlink(TRAVA_FILE)

    raise RuntimeError(f'Não foi possível estabelecer a chave de sessão em {KEY_FILE}')


app.secret_key = _secret_key()


@app.template_global()
def ic(nome, classe='ic-svg'):
    """Desenha um ícone do catálogo. Nome desconhecido cai no genérico, para um
    item mal cadastrado não deixar um buraco no lugar do símbolo; 'nenhum' não
    desenha nada, que é escolha de quem cadastrou."""
    escolhido = nome_icone(nome)
    if escolhido == SEM_ICONE:
        return Markup('')
    enviado = icone_de_arquivo(escolhido)
    if enviado:
        # Imagem própria: não herda a cor do texto como os desenhos do
        # catálogo, e é isso que se espera de um logo enviado.
        caminho = url_for('static', filename=f'icones/{enviado}')
        zoom = zooms_icones().get(enviado, ZOOM_PADRAO)
        # Só sai atributo quando há o que dizer: no tamanho natural o ícone
        # segue sendo uma tag limpa, como era antes de existir o ajuste.
        estilo = (f' style="--ic-zoom:{zoom / 100:.2f}"'
                  if zoom != ZOOM_PADRAO else '')
        return Markup(f'<img class="{escape(classe)} ic-arquivo"{estilo} '
                      f'src="{escape(caminho)}" alt="" aria-hidden="true">')
    return Markup(
        f'<svg class="{escape(classe)}" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{ICONES[escolhido]}</svg>')


# ── banco ──────────────────────────────────────────────────────────────────────

# A identidade da unidade vem do instalador (variáveis de ambiente) na primeira
# execução; depois disso é editável em Administração → Aparência. Outra unidade
# usa o mesmo código, só respondendo as perguntas da instalação.
PADROES = {
    'site_nome':    os.environ.get('INTRANET_ORG_NOME',
                                   'Centro de Detenção Provisória de Nova Independência'),
    'site_sigla':   os.environ.get('INTRANET_ORG_SIGLA', 'CDPNI'),
    'site_sub':     os.environ.get('INTRANET_ORG_SUB', 'Portal de Sistemas'),
    'cor_primaria': '#1c3d5a',     # azul institucional escuro (coberturas)
    'cor_destaque': '#2f7fb8',     # azul médio — botões e links
    'banner_seg':   '6',           # segundos por slide
    # Textos da capa (as linhas sobre a foto). Título em branco monta
    # "Portal <sigla>" sozinho, então trocar a sigla já arruma a capa.
    # A descrição é dividida em duas linhas para a quebra ser escolhida à mão:
    # deixada ao acaso, ela cai em lugar feio conforme a largura da tela.
    'capa_abertura': 'Bem-vindo ao',
    'capa_titulo':   '',
    'capa_texto':    'Acesse sistemas, informações',
    'capa_texto2':   'e serviços da unidade.',
    # Tipografia do que é digitado à mão. Tamanhos em rem, cores em hexa —
    # ambos validados na gravação, porque vão parar dentro de um <style>.
    'capa_titulo_tam': '1.75', 'capa_titulo_cor': '#ffffff',
    'capa_texto_tam':  '0.83', 'capa_texto_cor':  '#dde6f4',
    'botao_sigla_tam': '0.80', 'botao_sigla_cor': '#1e293b',
    'botao_nome_tam':  '0.67', 'botao_nome_cor':  '#7c8ba1',
    # Cores de fundo. A barra lateral aceita duas: iguais dão cor sólida,
    # diferentes dão degradê de cima para baixo.
    'capa_cor':     '#16294f',
    'lateral_cor1': '#101d3a',
    'lateral_cor2': '#16294f',
    # Fundo da página inteira: a foto aérea da unidade, uma cor à escolha ou
    # nada (o cinza claro do tema). O véu é o quanto a foto é clareada por
    # trás dos cartões — foto crua atrás de texto cansa a leitura.
    # Tipografia dos comunicados. A família sai de uma lista fechada: o servidor
    # é de rede interna, sem fonte de internet, então só valem pilhas que já
    # existem na máquina de quem lê.
    'com_fonte':      'padrao',    # padrao | classica | serifa | mono
    'com_titulo_tam': '0.83', 'com_titulo_cor': '#1e293b',
    'com_texto_tam':  '0.74', 'com_texto_cor':  '#7c8ba1',
    'fundo_modo': 'imagem',    # imagem | cor | nenhum
    'fundo_cor':  '#f6f8fc',
    'fundo_veu':  '82',        # 0 a 100
}
FUNDO_MODOS = ('imagem', 'cor', 'nenhum')

# Paleta oferecida nos seletores de cor. Escolher de uma lista curta evita o
# arco-íris que sai de um seletor livre — e todas aqui têm contraste suficiente
# para texto em cartão claro. O seletor livre continua ao lado, para quem
# precisar de uma cor específica da unidade.
PALETA = [
    ('#1e293b', 'Grafite'),   ('#7c8ba1', 'Cinza'),     ('#2563eb', 'Azul'),
    ('#1d4ed8', 'Azul forte'),('#16a34a', 'Verde'),     ('#0f766e', 'Verde-água'),
    ('#e08a2a', 'Âmbar'),     ('#c2410c', 'Laranja'),   ('#e0503c', 'Vermelho'),
    ('#b91c1c', 'Vermelho forte'), ('#6d5ae0', 'Roxo'), ('#a21caf', 'Magenta'),
    ('#dc2626', 'Vermelho vivo'), ('#9f1239', 'Vinho'), ('#0e7490', 'Petróleo'),
    ('#334155', 'Ardósia'), ('#000000', 'Preto'),
]
# Fundos: mesmas famílias, em tom claro — texto escuro por cima continua legível.
PALETA_FUNDO = [
    ('#e5edfd', 'Azul claro'),  ('#e3f6ec', 'Verde claro'), ('#fdf0e2', 'Âmbar claro'),
    ('#fdeae7', 'Vermelho claro'), ('#ece9fc', 'Roxo claro'), ('#f0f3f9', 'Cinza claro'),
    ('#fff8d6', 'Amarelo'),     ('#e6fbff', 'Ciano claro'),
]

# Como o comunicado chama atenção, além do selo de urgência.
DESTAQUES_COMUNICADO = {
    'nenhum': 'Sem destaque',
    'fundo':  'Fundo colorido',
    'pulso':  'Título pulsando',
}

FONTES_TEXTO = {
    'padrao':   ("Padrão do portal", "'Inter','Segoe UI Variable','Segoe UI',"
                                     "system-ui,sans-serif"),
    'classica': ("Sem serifa clássica", "Arial,Helvetica,'Liberation Sans',sans-serif"),
    'serifa':   ("Com serifa", "Georgia,'Times New Roman','Liberation Serif',serif"),
    'mono':     ("Monoespaçada", "'Consolas','DejaVu Sans Mono',monospace"),
}

# Títulos dos cartões do painel. Ficam em config para a unidade chamar cada
# bloco do jeito que fala no dia a dia — "Ramais mais utilizados" pode ser
# "Telefones úteis" sem ninguém mexer em template.
# Cartões cujo nome é uma configuração. Os cinco cartões do painel saíram
# daqui: o nome deles é do próprio cartão, guardado em `cartoes_painel.nome`.
TITULOS_CARTAO = [
    ('sistemas', 'Acesso rápido aos sistemas'),
    ('atalhos',  'Atalhos úteis'),
    ('ramais',   'Ramais mais utilizados'),
]
PADROES.update({f'titulo_{chave}': texto for chave, texto in TITULOS_CARTAO})

# Aparência de cada cartão: fonte, tamanho e cor do título e do texto. Editada
# na tela do próprio cartão; Aparência fica com o que vale para o portal todo.
#
# O prefixo nomeia as variáveis CSS emitidas em base.html. Os padrões são
# exatamente o que a folha já desenhava antes de existir o controle — ligar o
# ajuste não muda nada de lugar; só passa a ser possível mexer.
#
# 'com' é o prefixo dos comunicados desde antes; mantido para não perder o que
# já está gravado nas instalações em uso.
# Os cinco cartões do painel, na posição que os blocos antigos ocupavam. O
# nome é genérico de propósito: o cartão não é mais "de escala" nem "de
# aniversário", serve para o que a unidade quiser pôr dentro.
CARTOES_FIXOS = [
    # chave        nome                          icone       regiao coluna ordem
    ('sistemas',  'Acesso rápido aos sistemas', 'grade',     'topo',  3, -3),
    ('atalhos',   'Atalhos úteis',              'marcador',  'meio',  3, -2),
    ('ramais',    'Ramais mais utilizados',     'telefone',  'baixo', 1, -1),
    ('noticias',  'Últimas notícias',           'megafone',  'meio',  3, -1),
]

CARTOES_SEMENTE = [
    # A ordem é global, não por região: ela ordena as abas da administração e,
    # dentro de cada região, a posição no painel. Numerar por região faria os
    # valores colidirem e as abas sairiam fora de sequência.
    ('cartao1', 'Cartão 1', 'megafone',   'topo',  0),
    ('cartao2', 'Cartão 2', 'bolo',       'topo',  1),
    ('cartao3', 'Cartão 3', 'calendario', 'baixo', 2),
    ('cartao4', 'Cartão 4', 'fone',       'baixo', 3),
    ('cartao5', 'Cartão 5', 'arquivo',    'baixo', 4),
]

CARTAO_APARENCIA = {
    #                prefixo       título          texto
    # Os cinco cartões do painel nascem iguais — nada mais os distingue.
    **{c: (c, '0.83', '#1e293b', '0.74', '#7c8ba1')
       for c, *_ in CARTOES_SEMENTE},
    'sistemas':      ('sistemas', '0.80', '#1e293b', '0.67', '#7c8ba1'),
    'atalhos':       ('atalhos',  '0.80', '#1e293b', '0.67', '#7c8ba1'),
    # Medidas do cartão do painel, que é do que a tela de Ramais fala. A página
    # "ver todos" é outra coisa — três colunas de lista — e tem medida própria.
    'ramais':        ('ramais',   '0.74', '#1e293b', '0.78', '#1e293b'),
    # Últimas notícias: título de cada notícia em azul e um pouco maior que
    # os demais cartões (era .80–.85rem e cor do texto); o texto é a data.
    'noticias':      ('noticias', '0.95', '#2563eb', '0.68', '#7c8ba1'),
}
# Nome do cartão (o cabeçalho "ÚLTIMAS NOTÍCIAS", "ATALHOS ÚTEIS"...): tamanho e
# cor próprios, iguais em todos os cartões. Os padrões são o que a folha já
# desenhava (.82rem, cor do texto), então nada muda de lugar até alguém mexer.
CAB_TAM_PADRAO, CAB_COR_PADRAO = '0.82', '#1e293b'
PADROES.update({
    chave: valor
    for pref, t_tam, t_cor, x_tam, x_cor in CARTAO_APARENCIA.values()
    for chave, valor in ((f'{pref}_fonte', 'padrao'),
                         (f'{pref}_cab_tam', CAB_TAM_PADRAO), (f'{pref}_cab_cor', CAB_COR_PADRAO),
                         (f'{pref}_titulo_tam', t_tam), (f'{pref}_titulo_cor', t_cor),
                         (f'{pref}_texto_tam', x_tam),  (f'{pref}_texto_cor', x_cor))
    if chave not in PADROES})

# Faixa escura de links de informação no topo de todas as páginas, e o cartão
# "Em destaque" que fica abaixo do menu de páginas na tela inicial. Os dois são
# editados em Administração → Navegação.
PADROES.update({
    # Um link por linha, no formato "Nome | endereço".
    'faixa_links':     '',
    'lista_paginas_ativa': '0',
    'destaque_ativo':  '0',
    'destaque_rotulo': 'Em destaque',
    'destaque_titulo': '',
    'destaque_texto':  '',
    'destaque_url':    '',
    'destaque_cta':    'Saiba mais',
})


# "Título" e "texto" apontam para coisas diferentes em cada cartão. Dito na
# tela, ninguém precisa mexer para descobrir o que vai mudar.
CARTAO_PARTES = {
    **{c: ('o título de cada item', 'o texto embaixo dele')
       for c, *_ in CARTOES_SEMENTE},
    'sistemas': ('a sigla do botão', 'o nome embaixo dela'),
    'atalhos':  ('o nome do atalho', 'a descrição embaixo dele'),
    'ramais':   ('o nome do setor',  'o número do ramal'),
    'noticias': ('o título de cada notícia', 'a data e a categoria acima dele'),
}


def campos_aparencia(chave):
    """(campo, faixa) de cada ajuste do cartão. Faixa só para tamanho."""
    pref = prefixo_aparencia(chave)
    return ((f'{pref}_fonte', None),
            (f'{pref}_cab_tam', (0.6, 1.8)), (f'{pref}_cab_cor', None),
            (f'{pref}_titulo_tam', (0.6, 2.0)), (f'{pref}_titulo_cor', None),
            (f'{pref}_texto_tam', (0.5, 2.0)),  (f'{pref}_texto_cor', None))


# Cartões genéricos criados depois (cartao6, cartao7...) não estão em
# CARTAO_APARENCIA, mas têm a mesma aparência de fábrica e as mesmas telas.
APARENCIA_PADRAO = {'fonte': 'padrao', 'cab_tam': CAB_TAM_PADRAO, 'cab_cor': CAB_COR_PADRAO,
                    'titulo_tam': '0.83', 'titulo_cor': '#1e293b',
                    'texto_tam': '0.74', 'texto_cor': '#7c8ba1'}
PARTES_PADRAO = ('o título de cada item', 'o texto embaixo dele')


def prefixo_aparencia(chave):
    """Prefixo dos campos de aparência do cartão, ou None se ele não tem."""
    if chave in CARTAO_APARENCIA:
        return CARTAO_APARENCIA[chave][0]
    c = cartao_por_chave(chave)
    return chave if c and c['tipo'] == 'itens' else None


def padrao_aparencia(pref, campo):
    """Valor de fábrica de um campo de aparência (`campo` já com o prefixo)."""
    return PADROES.get(campo) or APARENCIA_PADRAO[campo[len(pref) + 1:]]


def prefixos_aparencia():
    """Todos os cartões com aparência: os de fábrica e os genéricos criados depois."""
    prefs = [p for p, *_ in CARTAO_APARENCIA.values()]
    for r in db().execute("SELECT chave FROM cartoes_painel WHERE tipo='itens' ORDER BY ordem, id"):
        if r['chave'] not in prefs:
            prefs.append(r['chave'])
    return prefs


def dados_aparencia_cartao(chave):
    """(chave, prefixo, o que é título, o que é texto) para a tela desenhar o
    formulário. Cartão sem aparência — o menu lateral — devolve None."""
    pref = prefixo_aparencia(chave)
    if not pref:
        return None
    return (chave, pref) + CARTAO_PARTES.get(chave, PARTES_PADRAO)

# Cartões livres: a unidade cria os seus, com título, foto e texto próprios.
# A posição é por encaixe na grade que já existe, não solta em pixels — o
# portal é aberto para telas de tamanhos muito diferentes, e posição livre
# viraria texto por cima de foto no primeiro notebook de tela menor.
CARTAO_REGIOES = {
    'topo':  'Fileira de cima (ao lado de sistemas e comunicados)',
    'meio':  'Faixa do meio (entre os atalhos e a fileira de baixo)',
    'baixo': 'Fileira de baixo (ao lado de ramais e escalas)',
}
# Onde a foto entra no cartão.
CARTAO_IMG_POS = {
    'topo':  'Acima do texto, largura inteira',
    'lado':  'À esquerda, com o texto ao lado',
    'fundo': 'Ao fundo, esmaecida atrás do texto',
}
# Quantas colunas o cartão ocupa. Mais que 3 não faz sentido: a fileira de
# cima tem três colunas, e a de baixo encolhe sozinha conforme a tela.
CARTAO_LARGURAS = {1: '1 coluna', 2: '2 colunas', 3: '3 colunas',
                   4: '4 colunas'}
# Em qual coluna o cartão começa. "Automática" é o que sempre houve: ele
# entra na primeira vaga livre da fileira. Escolher fixa a posição — útil
# para deixar um cartão sempre à direita, por exemplo.
CARTAO_COLUNAS = {0: 'Automática (próxima vaga livre)', 1: '1ª coluna',
                  2: '2ª coluna', 3: '3ª coluna', 4: '4ª coluna'}
# Quantas colunas cada região tem de verdade. A de baixo é mais estreita por
# cartão e cabe mais uma — era assim antes de existir configuração, e o mapa da
# administração precisa desenhar o mesmo número, senão promete uma posição que
# o painel não tem.
COLUNAS_POR_REGIAO = {'topo': 3, 'meio': 3, 'baixo': 4}
# Altura do cartão, em LINHAS da grade do painel (static/style.css, `data-alt`).
# Todas as colunas dividem as mesmas linhas, então os cartões ficam alinhados;
# um cartão de 2 linhas deixa uma célula livre ao lado, onde entra outro cartão.
CARTAO_ALTURAS = {0: '1 linha', 1: '2 linhas', 2: '3 linhas'}


def distribuir_em_colunas(cartoes, colunas):
    """Em qual coluna cada cartão realmente cai.

    Coluna 0 quer dizer "a próxima vaga livre", que é como a grade do navegador
    se comporta. Aqui o mesmo caminhar é refeito para o mapa poder mostrar a
    posição de fato — antes ele empilhava todos os automáticos na primeira, e
    quem olhava via um layout que não existia.
    """
    proxima = 1
    for c in cartoes:
        largura = min(c['largura'] or 1, colunas)
        if c['coluna']:
            inicio = min(c['coluna'], colunas)
        else:
            # Não cabendo no que resta da fileira, desce para a seguinte.
            if proxima + largura - 1 > colunas:
                proxima = 1
            inicio = proxima
        c['coluna_efetiva'] = inicio
        proxima = inicio + largura
        if proxima > colunas:
            proxima = 1

# Valores que entram numa folha de estilo não podem vir crus do formulário:
# um ponto-e-vírgula no meio já emenda outra regra.
_HEX = re.compile(r'^#[0-9a-fA-F]{6}$')


def medida(valor, padrao, minimo=0.5, maximo=4.0):
    """Tamanho em rem, preso a uma faixa razoável."""
    try:
        n = float(str(valor).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return padrao
    return f'{max(minimo, min(maximo, n)):.2f}'


POSICAO_PADRAO = '50% 50%'
_POSICAO = re.compile(r'^(\d{1,3}(?:\.\d)?)% (\d{1,3}(?:\.\d)?)%$')


def posicao_capa(valor):
    """Enquadramento do banner, como `background-position`.

    Vai cru para dentro de um atributo `style`, então não pode vir do
    formulário sem conferência: só o par de porcentagens é aceito, e qualquer
    outra coisa cai no centro."""
    achado = _POSICAO.match((valor or '').strip())
    if not achado:
        return POSICAO_PADRAO
    x, y = (min(100.0, max(0.0, float(n))) for n in achado.groups())
    return f'{x:g}% {y:g}%'


def cor_hexa(valor, padrao):
    valor = (valor or '').strip()
    return valor if _HEX.match(valor) else padrao


# A paleta de amostras fica disponível a qualquer template, inclusive os macros
# importados sem contexto (campos.html), que desenham a aparência dos cartões.
app.jinja_env.globals['PALETA'] = PALETA


@app.template_global()
def rgba(hexa, alfa):
    """Mesma cor com transparência — usada no véu que escurece a foto atrás do
    texto da capa. Sem ele o texto some sobre as partes claras da imagem."""
    hexa = cor_hexa(hexa, '#16294f').lstrip('#')
    r, g, b = (int(hexa[i:i + 2], 16) for i in (0, 2, 4))
    return f'rgba({r},{g},{b},{alfa})'

SEED_LINKS = [
    ('Plataforma SP',   'https://minhaarea.sp.gov.br/plataformasp',
     'Área do servidor — Governo do Estado de São Paulo', 'PSP', '#2f7fb8'),
    ('SisDRHu',         'http://10.200.45.21:81/SisDrhu/webroot/ui/Login.php',
     'Sistema de Recursos Humanos', 'RH', '#2a8f8a'),
    ('GPU',             'https://gpu.policiapenal.sp.gov.br/',
     'Gestão Prisional Unificada — Polícia Penal', 'GPU', '#c9a227'),
    ('Cartórios SP',    'http://new.cartoriosap.sp.gov.br/',
     'Sistema de cartórios', 'CAR', '#4a5b68'),
    ('GEPEN',           'http://10.200.45.5:8080/gepen/index.do',
     'Gestão Penitenciária', 'GEP', '#6455a8'),
]

# Atalhos que toda unidade acaba pedindo. Entram sem endereço de propósito:
# metade é sistema interno, com IP diferente em cada unidade, e chutar um link
# é pior que nenhum — quem clica num atalho errado só descobre no erro do
# navegador. Sem URL a pastilha aparece na faixa e não leva a lugar nenhum, até
# alguém preencher em Administração → Links → Atalhos úteis.
SEED_ATALHOS = [
    ('Diário Oficial de SP',     'documento'),
    ('Portal da Transparência',  'globo'),
    ('Holerite',                 'cifrao'),
    ('Requisição de Materiais',  'pasta'),
    ('Ponto Eletrônico',         'relogio'),
    ('SAP',                      'escudo'),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario    TEXT UNIQUE NOT NULL,
    nome       TEXT NOT NULL,
    senha_hash TEXT NOT NULL,
    admin      INTEGER NOT NULL DEFAULT 0,
    ativo      INTEGER NOT NULL DEFAULT 1,
    criado_em  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    ultimo_acesso TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS links (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo    TEXT NOT NULL,
    url       TEXT NOT NULL,
    descricao TEXT DEFAULT '',
    icone     TEXT DEFAULT '',
    simbolo   TEXT DEFAULT '',
    categoria TEXT DEFAULT '',
    situacao  TEXT DEFAULT '',
    cor       TEXT DEFAULT '#3a6d8c',
    ordem     INTEGER NOT NULL DEFAULT 0,
    ativo     INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS banners (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    arquivo TEXT NOT NULL DEFAULT '',
    cor     TEXT DEFAULT '',
    titulo  TEXT DEFAULT '',
    texto   TEXT DEFAULT '',
    url     TEXT DEFAULT '',
    ordem   INTEGER NOT NULL DEFAULT 0,
    ativo   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS lateral (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo     TEXT NOT NULL DEFAULT 'aviso',   -- 'aviso' | 'link'
    titulo   TEXT NOT NULL,
    conteudo TEXT DEFAULT '',
    url      TEXT DEFAULT '',
    ordem    INTEGER NOT NULL DEFAULT 0,
    ativo    INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS ramais (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    setor   TEXT NOT NULL,
    numeros TEXT NOT NULL,
    ativo   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS aniversariantes (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    nome  TEXT NOT NULL,
    dia   INTEGER NOT NULL,
    mes   INTEGER NOT NULL,
    cargo TEXT DEFAULT '',
    ativo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS escalas (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    turno   TEXT NOT NULL,
    equipe  TEXT DEFAULT '',
    horario TEXT DEFAULT '',
    efetivo TEXT DEFAULT '',
    ordem   INTEGER NOT NULL DEFAULT 0,
    ativo   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS chamados (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    numero  TEXT NOT NULL,
    titulo  TEXT NOT NULL,
    situacao TEXT DEFAULT 'aberto',
    data    TEXT DEFAULT '',
    ordem   INTEGER NOT NULL DEFAULT 0,
    ativo   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS menu_itens (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT NOT NULL,
    nome  TEXT NOT NULL,
    icone TEXT DEFAULT '',
    url   TEXT DEFAULT '',
    ordem INTEGER NOT NULL DEFAULT 0,
    ativo INTEGER NOT NULL DEFAULT 1
);
-- A lista "Páginas" da tela inicial. É própria: não depende do menu do topo
-- (menu_itens), então renomear um não mexe no outro.
CREATE TABLE IF NOT EXISTS paginas_lateral (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT NOT NULL,
    nome  TEXT NOT NULL,
    icone TEXT DEFAULT '',
    url   TEXT DEFAULT '',
    ordem INTEGER NOT NULL DEFAULT 0,
    ativo INTEGER NOT NULL DEFAULT 1
);
-- Os cartões da página inicial. Deixaram de ser cinco blocos especializados
-- (escala, aniversário, chamado…) e passaram a ser cartões iguais entre si: o
-- que muda de um para outro é o nome, a posição e o que se escreve dentro.
-- A chave é fixa (cartao1..cartao5) porque nomeia as configurações de
-- aparência; o nome visível fica em `nome` e pode ser trocado à vontade.
CREATE TABLE IF NOT EXISTS cartoes_painel (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    chave   TEXT UNIQUE NOT NULL,
    nome    TEXT NOT NULL,
    icone   TEXT DEFAULT 'prancheta',
    regiao  TEXT DEFAULT 'baixo',       -- topo | meio | baixo
    largura INTEGER NOT NULL DEFAULT 1,
    coluna  INTEGER NOT NULL DEFAULT 0, -- 0 = próxima vaga livre; 1..3 = fixa
    altura  INTEGER NOT NULL DEFAULT 0, -- 0 = automática; 1..4 = altura mínima
    -- O que o cartão desenha por dentro. 'itens' é o cartão comum, de lista
    -- livre; os demais são os três que têm desenho próprio e conteúdo vindo de
    -- outro cadastro. Todos são posicionados do mesmo jeito.
    tipo    TEXT NOT NULL DEFAULT 'itens',
    ordem   INTEGER NOT NULL DEFAULT 0,
    ativo   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS cartoes (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo  TEXT NOT NULL,
    icone   TEXT DEFAULT 'prancheta',
    texto   TEXT DEFAULT '',
    imagem  TEXT DEFAULT '',            -- arquivo em static/uploads
    img_pos TEXT DEFAULT 'topo',        -- topo | fundo | lado
    url     TEXT DEFAULT '',
    url_rot TEXT DEFAULT '',            -- rótulo do link no rodapé do cartão
    regiao  TEXT DEFAULT 'baixo',       -- topo | meio | baixo
    largura INTEGER NOT NULL DEFAULT 1, -- quantas colunas o cartão ocupa
    coluna  INTEGER NOT NULL DEFAULT 0, -- 0 = a próxima livre; 1..3 = fixa
    titulo_cor TEXT DEFAULT '',
    texto_cor  TEXT DEFAULT '',
    fundo_cor  TEXT DEFAULT '',
    ordem   INTEGER NOT NULL DEFAULT 0,
    ativo   INTEGER NOT NULL DEFAULT 1
);
-- Conteúdo das páginas do menu lateral. Cada item do menu (sem endereço
-- próprio) abre /modulo/<chave>, e esta tabela guarda o que aparece nela: uma
-- sequência de blocos de subtítulo, texto e imagem, na ordem escolhida.
CREATE TABLE IF NOT EXISTS pagina_blocos (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    chave   TEXT NOT NULL,                -- chave do item em menu_itens
    tipo    TEXT NOT NULL DEFAULT 'texto',-- subtitulo | texto | imagem
    texto   TEXT DEFAULT '',              -- subtítulo, parágrafos ou legenda
    arquivo TEXT DEFAULT '',              -- imagem em static/uploads
    ordem   INTEGER NOT NULL DEFAULT 0,
    ativo   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""

# Uma linha colada da lista de ramais: o setor vem primeiro e os números no
# fim. O grupo do setor é preguiçoso para "GAIOLA 0   307" sair como
# ("GAIOLA 0", "307") e não como ("GAIOLA", "0 307").
LINHA_RAMAL = re.compile(r'^(.*?)\s+((?:\d+\s*[/,\-–]\s*)*\d+)\s*$')


def interpretar_sistemas(texto):
    """Lê a lista colada de sistemas e devolve [(sigla, nome, url)].

    Aceita, por linha, "SIGLA | Nome | endereço" ou só "Nome | endereço"; o
    separador pode ser barra vertical, tabulação, ponto-e-vírgula ou dois ou
    mais espaços. A sigla, quando ausente, sai das iniciais do nome."""
    itens = []
    for linha in (texto or '').splitlines():
        linha = linha.strip()
        if not linha:
            continue
        partes = [p.strip() for p in re.split(r'\s*[|;	]\s*|\s{2,}', linha) if p.strip()]
        if len(partes) < 2:
            continue
        url = partes[-1]
        if not re.match(r'^(https?://|/|#)', url, re.IGNORECASE):
            url = 'http://' + url
        if len(partes) >= 3:
            sigla, nome = partes[0], ' '.join(partes[1:-1])
        else:
            nome = partes[0]
            iniciais = ''.join(p[0] for p in nome.split() if p[0].isalnum())
            sigla = (iniciais[:3] if len(iniciais) > 1 else nome[:3]).upper()
        itens.append((sigla[:5].upper(), nome, url))
    return itens


def interpretar_ramais(texto):
    """Lê o texto colado e devolve [(setor, números)]. Aceita colunas separadas
    por tabulação, ponto-e-vírgula, barra vertical ou vários espaços."""
    itens = []
    for linha in (texto or '').splitlines():
        linha = re.sub(r'[\t;|]+', '  ', linha).strip()
        if not linha:
            continue
        m = LINHA_RAMAL.match(linha)
        if not m:
            continue
        setor = m.group(1)
        # Tira rótulos de coluna que vêm junto quando a lista é copiada de uma
        # tabela ("ADMINISTRATIVO   Ramal   202 / 256").
        setor = re.sub(r'\s+(ramal|ramais|tel|telefone|fone)s?\.?\s*$', '',
                       setor, flags=re.IGNORECASE)
        setor = re.sub(r'[\s.…-]+$', '', setor).strip()
        setor = re.sub(r'\s{2,}', ' ', setor)
        numeros = re.sub(r'\s*([/,\-–])\s*', r' \1 ', m.group(2)).strip()
        numeros = re.sub(r'\s+', ' ', numeros)
        if setor and numeros:
            itens.append((setor, numeros))
    return itens


def db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


@app.teardown_appcontext
def _fecha_db(exc):
    con = g.pop('db', None)
    if con is not None:
        con.close()




def _nome_guardado(con, chave, padrao):
    """O nome que a unidade ja tinha dado ao cartao, se deu.

    Lido direto da conexao, e nao por cfg(): isto roda no import do modulo,
    fora de qualquer contexto de requisicao."""
    linha = con.execute('SELECT valor FROM config WHERE chave=?',
                        (f'titulo_{chave}',)).fetchone()
    return (linha[0].strip() if linha and linha[0].strip() else padrao)


def _adotar_cartoes_livres(con):
    """Os cartões livres viram cartões do painel com um item só.

    Eram a mesma ideia com menos recursos: um cartão com um conteúdo. Depois
    que o cartão comum passou a aceitar imagem, vídeo e posição da foto, manter
    os dois seria oferecer dois caminhos para a mesma coisa — foi o que a
    unidade apontou. A tabela `cartoes` fica de pé, sem tela, para o caso de
    algo se perder na tradução.
    """
    if con.execute("SELECT 1 FROM config WHERE chave='livres_adotados'").fetchone():
        return
    con.row_factory = sqlite3.Row
    try:
        livres = con.execute('SELECT * FROM cartoes ORDER BY ordem, id').fetchall()
    except sqlite3.OperationalError:
        livres = []          # instalação que nunca chegou a ter cartões livres
    for r in livres:
        chave = _proxima_chave_cartao(con)
        con.execute("INSERT INTO cartoes_painel (chave,nome,icone,regiao,"
                    "largura,coluna,ordem,tipo,ativo)"
                    " VALUES (?,?,?,?,?,?,?,'itens',?)",
                    (chave, r['titulo'], r['icone'], r['regiao'], r['largura'],
                     r['coluna'], 100 + r['ordem'], r['ativo']))
        _semear_aparencia(con, chave)
        con.execute("INSERT INTO lateral (tipo,titulo,conteudo,url,url_rot,"
                    "ordem,ativo,urgencia,destaque,titulo_cor,texto_cor,"
                    "fundo_cor,data,imagem,img_pos,video,cartao)"
                    " VALUES ('aviso',?,?,?,?,0,1,'informacao','nenhum',"
                    "?,?,?,'',?,?,'',?)",
                    (r['titulo'], r['texto'], r['url'], r['url_rot'],
                     r['titulo_cor'], r['texto_cor'], r['fundo_cor'],
                     r['imagem'], r['img_pos'], chave))
    con.row_factory = None
    con.execute("INSERT INTO config (chave,valor) VALUES ('livres_adotados','1')")


def _proxima_chave_cartao(con):
    """cartaoN livre. A chave nomeia as configurações de aparência, então nunca
    é reaproveitada — um cartão novo com a chave de um excluído herdaria as
    cores dele."""
    usadas = {r[0] for r in con.execute('SELECT chave FROM cartoes_painel')}
    n = 1
    while f'cartao{n}' in usadas:
        n += 1
    return f'cartao{n}'


def _semear_aparencia(con, chave):
    """Grava a aparência padrão do cartão novo.

    Escrita no banco, e não deixada para um valor implícito: assim o resto do
    sistema continua achando a chave onde sempre achou, sem caso especial para
    cartão criado depois."""
    for sufixo, valor in (('fonte', 'padrao'), ('cab_tam', CAB_TAM_PADRAO),
                          ('cab_cor', CAB_COR_PADRAO), ('titulo_tam', '0.83'),
                          ('titulo_cor', '#1e293b'), ('texto_tam', '0.74'),
                          ('texto_cor', '#7c8ba1')):
        con.execute('INSERT OR IGNORE INTO config (chave,valor) VALUES (?,?)',
                    (f'{chave}_{sufixo}', valor))


def _semear_cartoes(con):
    """Cria os cinco cartões e adota o conteúdo dos blocos antigos.

    Roda uma vez só, marcada em `config`. Os blocos especializados guardavam
    cada um as suas colunas (turno/equipe, dia/mês, número/situação); aqui elas
    viram título e texto, que é o que o cartão genérico sabe mostrar. As
    tabelas de origem ficam de pé, intocadas: se algo se perder na tradução, o
    dado original continua lá para ser conferido.
    """
    # Os tres de desenho proprio. Ordem negativa: continuam na frente dos
    # demais, como sempre estiveram, ate alguem arrasta-los.
    for chave, nome, icone, regiao, largura, ordem in CARTOES_FIXOS:
        con.execute('INSERT OR IGNORE INTO cartoes_painel'
                    ' (chave,nome,icone,regiao,largura,ordem,tipo,ativo)'
                    ' VALUES (?,?,?,?,?,?,?,1)',
                    (chave, _nome_guardado(con, chave, nome), icone, regiao,
                     largura, ordem, chave))

    # Antes da guarda: tem marca propria e precisa rodar tambem em instalacao
    # que ja passou pela migracao anterior.
    _adotar_cartoes_livres(con)

    # 1.8.0: "Acesso rápido" e "Atalhos" passam a largura total (uma vez só; quem
    # ajustar depois não é desfeito) e o cartão de notícias vai para a lateral.
    if not con.execute("SELECT 1 FROM config WHERE chave='layout_v18'").fetchone():
        con.execute("UPDATE cartoes_painel SET largura=3, coluna=0"
                    " WHERE chave IN ('sistemas','atalhos')")
        con.execute("INSERT OR REPLACE INTO config (chave,valor) VALUES ('layout_v18','1')")

    if con.execute("SELECT 1 FROM config WHERE chave='cartoes_migrados'").fetchone():
        return
    for chave, nome, icone, regiao, ordem in CARTOES_SEMENTE:
        con.execute('INSERT OR IGNORE INTO cartoes_painel'
                    ' (chave,nome,icone,regiao,ordem,ativo) VALUES (?,?,?,?,?,1)',
                    (chave, nome, icone, regiao, ordem))

    # Comunicados já eram itens de texto livre: só ganham dono.
    con.execute("UPDATE lateral SET cartao='cartao1' WHERE cartao=''")

    def adotar(consulta, destino, monta):
        try:
            linhas = con.execute(consulta).fetchall()
        except sqlite3.OperationalError:
            return          # tabela não existe nesta instalação
        for i, r in enumerate(linhas):
            titulo, corpo = monta(r)
            if not titulo:
                continue
            con.execute(
                'INSERT INTO lateral (tipo,titulo,conteudo,url,ordem,ativo,'
                'urgencia,destaque,data,cartao)'
                " VALUES ('aviso',?,?,'',?,?,'informacao','nenhum','',?)",
                (titulo, corpo, i, r['ativo'] if 'ativo' in r.keys() else 1, destino))

    con.row_factory = sqlite3.Row
    adotar('SELECT * FROM aniversariantes ORDER BY mes, dia', 'cartao2',
           lambda r: (r['nome'], '\n'.join(filter(None, [
               f"{r['dia']:02d}/{r['mes']:02d}", r['cargo']]))))
    adotar('SELECT * FROM escalas ORDER BY ordem, id', 'cartao3',
           lambda r: (r['turno'], '\n'.join(filter(None, [
               r['equipe'], r['horario'], r['efetivo']]))))
    adotar('SELECT * FROM chamados ORDER BY ordem, id', 'cartao4',
           lambda r: (r['titulo'], '\n'.join(filter(None, [
               r['numero'], r['situacao'], r['data']]))))
    adotar("SELECT * FROM links WHERE grupo='reserva' ORDER BY ordem, id", 'cartao5',
           lambda r: (r['titulo'], '\n'.join(filter(None, [
               r['descricao'], r['situacao']]))))
    con.row_factory = None

    con.execute("INSERT INTO config (chave,valor) VALUES ('cartoes_migrados','1')")


def init_db():
    """Cria o banco e o conteúdo inicial.

    O gunicorn sobe vários processos e todos importam este módulo ao mesmo
    tempo. O BEGIN IMMEDIATE serializa a primeira execução: um processo semeia
    e os demais esperam e encontram tudo pronto — sem usuário admin duplicado.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(ICONES_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.isolation_level = None
    con.executescript(SCHEMA)

    # Colunas acrescentadas depois da primeira versão. Instalações antigas já
    # têm dados, então nada de recriar tabela: só adiciona o que falta.
    for tabela, coluna, tipo in (
            ('links',    'grupo',    "TEXT NOT NULL DEFAULT 'sistema'"),
            ('links',    'simbolo',  "TEXT DEFAULT ''"),
            # Categoria agrupa os sistemas em subtítulos dentro do cartão
            # (Operacionais, Segurança, Administrativo). Vazia: sem subtítulo.
            ('links',    'categoria', "TEXT DEFAULT ''"),
            # Selo à direita nas reservas — "Disponível", "Em uso até 11:00".
            ('links',    'situacao',  "TEXT DEFAULT ''"),
            ('banners',  'cor',      "TEXT DEFAULT ''"),
            # Que ponto da foto fica visível quando a capa corta o resto.
            ('banners',  'posicao',  "TEXT DEFAULT '50% 50%'"),
            ('lateral',  'urgencia', "TEXT NOT NULL DEFAULT 'informacao'"),
            # nenhum | fundo | pulso — chama atenção sem depender de emoji
            ('lateral',  'destaque', "TEXT DEFAULT 'nenhum'"),
            # Ajustes por comunicado. Em branco: vale o padrão de Aparência.
            ('lateral',  'titulo_tam', "TEXT DEFAULT ''"),
            ('lateral',  'titulo_cor', "TEXT DEFAULT ''"),
            ('lateral',  'texto_tam',  "TEXT DEFAULT ''"),
            ('lateral',  'texto_cor',  "TEXT DEFAULT ''"),
            ('lateral',  'fundo_cor',  "TEXT DEFAULT ''"),
            # A qual cartão o item pertence. Vazio nas instalações antigas, em
            # que `lateral` era um bloco só — a migração abaixo os adota.
            ('lateral',  'cartao',  "TEXT DEFAULT ''"),
            # Conteúdo que o item pode carregar além do texto.
            ('lateral',  'imagem',  "TEXT DEFAULT ''"),
            ('lateral',  'video',   "TEXT DEFAULT ''"),
            ('lateral',  'url_rot', "TEXT DEFAULT ''"),
            ('lateral',  'img_pos', "TEXT DEFAULT 'topo'"),
            # Largura da imagem acima do texto, em % da área do texto. 0 = a
            # largura de sempre (a do cartão).
            ('lateral',  'img_larg', 'INTEGER NOT NULL DEFAULT 0'),
            # Onde a imagem (quando menor que o cartão) fica na horizontal:
            # 0 = encostada à esquerda, 50 = centralizada, 100 = à direita.
            ('lateral',  'img_x', 'INTEGER NOT NULL DEFAULT 0'),
            ('cartoes',  'coluna',  'INTEGER NOT NULL DEFAULT 0'),
            ('cartoes_painel', 'coluna', 'INTEGER NOT NULL DEFAULT 0'),
            ('cartoes_painel', 'altura', 'INTEGER NOT NULL DEFAULT 0'),
            ('cartoes_painel', 'z', 'INTEGER NOT NULL DEFAULT 0'),     # ordem de empilhamento (sobreposição)
            ('cartoes_painel', 'tipo', "TEXT NOT NULL DEFAULT 'itens'"),
            # Layout livre: posição em células de um quadro de 12 colunas e
            # linhas de 1,5rem. gw = 0 quer dizer "ainda sem posição".
            ('cartoes_painel', 'gx', 'INTEGER NOT NULL DEFAULT 0'),
            ('cartoes_painel', 'gy', 'INTEGER NOT NULL DEFAULT 0'),
            ('cartoes_painel', 'gw', 'INTEGER NOT NULL DEFAULT 0'),
            ('cartoes_painel', 'gh', 'INTEGER NOT NULL DEFAULT 0'),
            ('lateral',  'data',     "TEXT DEFAULT ''"),
            # Páginas de conteúdo: largura (% da página) e posição da imagem, estilo
            # do bloco de texto e se o texto é HTML formatado ou texto simples
            # (blocos criados na versão 1.3.0).
            ('pagina_blocos', 'larg',    'INTEGER NOT NULL DEFAULT 100'),
            ('pagina_blocos', 'alinh',   "TEXT DEFAULT 'centro'"),
            ('pagina_blocos', 'estilo',  "TEXT DEFAULT 'normal'"),
            ('pagina_blocos', 'formato', "TEXT DEFAULT 'texto'"),
            ('pagina_blocos', 'url',     "TEXT DEFAULT ''"),
            # Cabeçalho de matéria das páginas de conteúdo: chapéu, linha fina,
            # autor, datas, foto de capa com legenda e crédito, resumo
            # recolhível e "Leia também". Tudo opcional: página sem nenhum
            # destes campos continua saindo só com o título, como antes.
            ('paginas_lateral', 'corpo',          "TEXT DEFAULT ''"),     # texto único da página (editor livre)
            ('paginas_lateral', 'chapeu',         "TEXT DEFAULT ''"),
            ('paginas_lateral', 'linha_fina',     "TEXT DEFAULT ''"),
            ('paginas_lateral', 'autor',          "TEXT DEFAULT ''"),
            ('paginas_lateral', 'publicada_em',   "TEXT DEFAULT ''"),
            ('paginas_lateral', 'atualizada_em',  "TEXT DEFAULT ''"),
            ('paginas_lateral', 'capa',           "TEXT DEFAULT ''"),
            ('paginas_lateral', 'capa_legenda',   "TEXT DEFAULT ''"),
            ('paginas_lateral', 'capa_credito',   "TEXT DEFAULT ''"),
            ('paginas_lateral', 'resumo',         "TEXT DEFAULT ''"),
            ('paginas_lateral', 'mostrar_resumo', 'INTEGER NOT NULL DEFAULT 1'),
            # "Leia também" começa desligado: ligá-lo é escolha de cada página,
            # e as já existentes não ganham um bloco novo por conta da atualização.
            ('paginas_lateral', 'mostrar_leia',   'INTEGER NOT NULL DEFAULT 0'),
            ('noticias', 'ordem',    'INTEGER NOT NULL DEFAULT 0'),
            ('noticias', 'titulo_fonte', "TEXT NOT NULL DEFAULT ''"),
            ('noticias', 'titulo_cor',   "TEXT NOT NULL DEFAULT ''"),
            ('noticias', 'titulo_tam',   "TEXT NOT NULL DEFAULT ''"),
            ('cartao_conteudo', 'url', "TEXT NOT NULL DEFAULT ''"),
            ('ramais',   'destaque', 'INTEGER NOT NULL DEFAULT 0'),
            ('usuarios', 'ultimo_acesso', "TEXT DEFAULT ''")):
        existentes = {c[1] for c in con.execute(f'PRAGMA table_info({tabela})')}
        if coluna not in existentes:
            con.execute(f'ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}')

    _semear_cartoes(con)
    # Cartões genéricos já existentes ganham os campos de aparência novos (nome do cartão).
    for r in con.execute("SELECT chave FROM cartoes_painel WHERE tipo='itens'").fetchall():
        _semear_aparencia(con, r[0])

    # O texto dos botões era um ajuste só, valendo para sistemas e atalhos ao
    # mesmo tempo. Agora cada cartão tem o seu. Quem tinha personalizado herda o
    # valor nos dois — sem isto a mudança apagaria a escolha em silêncio.
    guardadas = {r[0]: r[1] for r in con.execute('SELECT chave, valor FROM config')}
    for antiga, sufixo in (('botao_sigla_tam', 'titulo_tam'),
                           ('botao_sigla_cor', 'titulo_cor'),
                           ('botao_nome_tam',  'texto_tam'),
                           ('botao_nome_cor',  'texto_cor')):
        if antiga not in guardadas:
            continue
        for pref in ('sistemas', 'atalhos'):
            nova = f'{pref}_{sufixo}'
            if nova not in guardadas:
                con.execute('INSERT INTO config (chave,valor) VALUES (?,?)',
                            (nova, guardadas[antiga]))

    # A chefia de plantão saiu do portal. A tabela some só se estiver vazia:
    # numa instalação que chegou a preencher, apagar seria destruir dado sem
    # aviso — ali ela fica parada, sem tela, e o backup continua levando.
    try:
        if not con.execute('SELECT 1 FROM plantao LIMIT 1').fetchone():
            con.execute('DROP TABLE plantao')
    except sqlite3.OperationalError:
        pass    # já não existe

    con.execute('BEGIN IMMEDIATE')

    for chave, valor in PADROES.items():
        con.execute('INSERT OR IGNORE INTO config (chave, valor) VALUES (?,?)',
                    (chave, valor))

    # Título das notícias: o padrão passou de vinho para azul. Uma vez só, troca quem ainda
    # estava no vinho antigo; depois disso, a cor escolhida no painel é respeitada.
    if not con.execute("SELECT 1 FROM config WHERE chave='noticias_azul_v1'").fetchone():
        con.execute("UPDATE config SET valor='#2563eb' WHERE chave='noticias_titulo_cor' AND valor='#9f1239'")
        con.execute("INSERT INTO config (chave,valor) VALUES ('noticias_azul_v1','1')")

    if not con.execute('SELECT 1 FROM links LIMIT 1').fetchone():
        for i, (t, u, d, sigla, cor) in enumerate(SEED_LINKS):
            con.execute('INSERT INTO links (titulo,url,descricao,icone,simbolo,cor,ordem)'
                        ' VALUES (?,?,?,?,?,?,?)', (t, u, d, sigla, 'aplicativo', cor, i))

    # Os atalhos chegaram depois da primeira versão, então o teste de "tabela
    # vazia" usado acima já não vale: quem instalou antes tem `links` cheia de
    # sistemas e nunca veria a faixa. O marcador em config resolve os dois
    # lados — entra uma vez em cada banco, e não volta se o administrador
    # apagar os atalhos por não querer nenhum.
    if not con.execute("SELECT 1 FROM config WHERE chave='seed_atalhos'").fetchone():
        ordem = con.execute("SELECT COALESCE(MAX(ordem),-1)+1 FROM links"
                            " WHERE grupo='atalho'").fetchone()[0]
        for i, (titulo, simbolo) in enumerate(SEED_ATALHOS):
            con.execute("INSERT INTO links (titulo,url,descricao,icone,simbolo,cor,"
                        "ordem,grupo) VALUES (?,'','','',?,'#3a6d8c',?,'atalho')",
                        (titulo, simbolo, ordem + i))
        con.execute("INSERT INTO config (chave,valor) VALUES ('seed_atalhos','1')")

    instalacao_nova = not con.execute('SELECT 1 FROM menu_itens LIMIT 1').fetchone()
    if instalacao_nova:
        for i, (chave, nome, icone, _) in enumerate(MENU):
            con.execute('INSERT INTO menu_itens (chave,nome,icone,ordem)'
                        ' VALUES (?,?,?,?)', (chave, nome, icone, i))
    _separar_paginas_laterais(con, instalacao_nova)
    _migrar_v19(con, instalacao_nova)

    if not con.execute('SELECT 1 FROM lateral LIMIT 1').fetchone():
        con.execute("INSERT INTO lateral (tipo,titulo,conteudo,ordem) VALUES"
                    " ('aviso','Bem-vindo',"
                    "'Use o painel de administração para publicar avisos, links e"
                    " imagens do banner.',0)")

    # Usuário administrador inicial. A senha vem do instalador (env) ou é
    # sorteada e impressa no log — nunca há senha fixa no código.
    if not con.execute('SELECT 1 FROM usuarios LIMIT 1').fetchone():
        senha = os.environ.get('INTRANET_ADMIN_SENHA') or secrets.token_urlsafe(9)
        con.execute('INSERT INTO usuarios (usuario,nome,senha_hash,admin)'
                    " VALUES ('admin','Administrador',?,1)",
                    (generate_password_hash(senha),))
        print('=' * 62, flush=True)
        print(' Usuário administrador criado:  admin', flush=True)
        print(f' Senha inicial:                 {senha}', flush=True)
        print(' Troque a senha após o primeiro acesso.', flush=True)
        print('=' * 62, flush=True)

    con.execute('COMMIT')
    con.close()


def cfg(chave=None):
    todas = {r['chave']: r['valor']
             for r in db().execute('SELECT chave, valor FROM config')}
    for k, v in PADROES.items():
        todas.setdefault(k, v)
    return todas if chave is None else todas.get(chave, '')


# ── autenticação ───────────────────────────────────────────────────────────────

def admin_obrigatorio(f):
    @wraps(f)
    def _wrap(*a, **kw):
        if not session.get('uid'):
            return redirect(url_for('login', proximo=request.path))
        if not session.get('admin'):
            abort(403)
        return f(*a, **kw)
    return _wrap


def token_csrf():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']


@app.before_request
def _valida_csrf():
    if request.method == 'POST':
        enviado = request.form.get('csrf', '')
        if not enviado or not secrets.compare_digest(enviado, session.get('csrf', '')):
            abort(400, 'Sessão expirada. Recarregue a página e tente de novo.')


VERSAO = '1.9.21'

MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho',
         'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

# Quantos itens cada cartão do painel mostra. O que passar disso fica na
# página "ver todos" — assim os cartões mantêm altura parecida e a página não
# cresce sem controle conforme os blocos vão sendo preenchidos.
# Abas da seção "Sistemas e atalhos". Reservas saíram daqui: o conteúdo delas
# é editado junto com os demais cartões, em "Blocos do painel".
GRUPOS_LINK = {
    'sistema': 'Acesso rápido aos sistemas',
    'atalho':  'Atalhos úteis',
}


def nome_do_bloco(chave, padrao):
    """Como o bloco se chama hoje, na língua da unidade.

    A aba mostra o nome que foi dado ao cartão, não o rótulo de fábrica: quem
    renomeou "Aniversariantes" para "Datas importantes" acha a aba com esse
    nome. O que a aba *faz* continua o mesmo — os campos e o desenho de cada
    bloco são próprios dele. Bloco sem cartão (o menu lateral) usa o padrão.
    """
    registrado = cartao_por_chave(chave)
    if registrado:
        return registrado['nome']
    return cfg(f'titulo_{chave}') if chave in dict(TITULOS_CARTAO) else padrao


def abas_links(atual):
    """Barra de abas da seção "Sistemas e atalhos": (rótulo, endereço, ativa).

    O menu lateral mora noutra tabela e é editado pelo motor de blocos, mas
    para quem usa é a mesma seção. Montando a barra num lugar só, as duas telas
    mostram as mesmas abas e o menu deixa de estar em dois lugares ao mesmo
    tempo — antes ele aparecia em "Blocos do painel", onde ninguém procurava.
    """
    plural = {'sistema': 'sistemas', 'atalho': 'atalhos'}
    itens = [(chave, nome_do_bloco(plural[chave], rotulo),
              url_for('admin_links', grupo=chave))
             for chave, rotulo in GRUPOS_LINK.items()]
    itens.append(('menu', BLOCOS['menu']['titulo'],
                  url_for('admin_painel', bloco='menu')))
    return [(rotulo, href, chave == atual) for chave, rotulo, href in itens]

# Sistemas e atalhos não têm limite: tudo o que está marcado como "Exibir na
# página inicial" aparece no cartão, que cresce conforme a lista. Havia um corte
# (16 e 8) que escondia o 17º sistema em diante — o item cadastrado só aparecia
# em "Ver todos" e parecia que o cadastro tinha falhado. Os ramais continuam
# limitados de propósito: o cartão é uma lista curta com busca.
#
# As duas chaves continuam aqui, com um número enorme, e não foram apagadas: um
# index.html de versão anterior ainda lê `limites.sistemas` e `limites.atalhos`,
# e sem as chaves a página inicial inteira cai com erro 500 se app.py e o
# template forem atualizados em momentos diferentes.
SEM_LIMITE = 10 ** 6
LIMITES = {
    'comunicados': 4, 'sistemas': SEM_LIMITE, 'atalhos': SEM_LIMITE,
    'aniversariantes': 4, 'ramais': 5, 'escalas': 6, 'chamados': 3,
    'reservas': 4,
}

# De onde cada bloco lê os itens na página "ver todos".
FONTES = {
    # Os cinco cartões do painel: mesma consulta, filtrada pelo cartão.
    **{c: ('lateral',
           "SELECT * FROM lateral WHERE ativo=1 AND cartao='" + c + "'"
           ' ORDER BY ordem, id', n, 'comunicados')
       for c, n, *_ in CARTOES_SEMENTE},
    'comunicados':     ('lateral', 'SELECT * FROM lateral WHERE ativo=1 ORDER BY ordem, id',
                        'Comunicados importantes', 'comunicados'),
    'atalhos':         ('links', "SELECT * FROM links WHERE ativo=1 AND grupo='atalho'"
                        ' ORDER BY ordem, id', 'Atalhos úteis', 'atalhos'),
    'reservas':        ('links', "SELECT * FROM links WHERE ativo=1 AND grupo='reserva'"
                        ' ORDER BY ordem, id', 'Reservas rápidas', 'reservas'),
    'escalas':         ('escalas', 'SELECT * FROM escalas WHERE ativo=1 ORDER BY ordem, id',
                        'Escalas', 'escalas'),
    'chamados':        ('chamados', 'SELECT * FROM chamados WHERE ativo=1 ORDER BY ordem, id',
                        'Chamados de TI', 'chamados'),
    'aniversariantes': ('aniversariantes',
                        'SELECT * FROM aniversariantes WHERE ativo=1 ORDER BY mes, dia',
                        'Aniversariantes do ano', 'aniversarios'),
}


@app.route('/lista/<chave>')
def lista(chave):
    """Página com todos os itens de um bloco — o painel mostra só os primeiros."""
    if chave == 'sistemas':
        return redirect(url_for('sistemas'))
    if chave == 'ramais':
        return redirect(url_for('ramais'))
    # Cartão criado depois da instalação não está em FONTES, que é montado uma
    # vez só. O nome e a consulta saem do próprio registro — sem isto, todo
    # cartão novo nasceria com o "Ver todos" quebrado.
    registrado = cartao_por_chave(chave)
    if registrado and registrado['tipo'] == 'itens':
        return render_template(
            'lista.html', chave=chave, titulo=registrado['nome'],
            macro='comunicados', marca_bloco=marca_atual('comunicados'), editavel=True,
            itens=db().execute('SELECT * FROM lateral WHERE ativo=1 AND cartao=?'
                               ' ORDER BY ordem, id', (chave,)).fetchall())
    if chave not in FONTES:
        abort(404)
    _, consulta, titulo, macro = FONTES[chave]
    return render_template('lista.html', chave=chave, titulo=titulo, macro=macro,
                           marca_bloco=marca_atual(macro),
                           editavel=bool(cartao_por_chave(chave)),
                           itens=db().execute(consulta).fetchall())

# Menu lateral. Os itens sem módulo próprio ainda levam a uma página que
# explica isso — some do menu é pior: o usuário procura e não acha.
MENU = [
    ('inicio',     'Início',              'inicio',     'index'),
    ('ramais',     'Ramais',              'telefone',   'ramais'),
]

# Páginas da barra lateral de uma instalação nova. Nome genérico: quem instala
# troca por o que fizer sentido; a chave só aparece no endereço da página.
PAGINAS_SEMENTE = [
    ('servidores', 'Link 1', 'usuarios'),
    ('documentos', 'Link 2', 'documento'),
    ('escalas',    'Link 3', 'calendario'),
    ('chamados',   'Link 4', 'fone'),
    ('reservas',   'Link 5', 'arquivo'),
    ('relatorios', 'Link 6', 'grafico'),
]


ROTAS_INTERNAS = {'inicio': 'index', 'ramais': 'ramais'}
MENU_PADRAO = {chave: (nome, icone) for chave, nome, icone, _ in MENU}


def _slug(texto):
    return re.sub(r'[^a-z0-9]+', '-', (texto or '').lower().strip()).strip('-') or 'pagina'


def _migrar_v19(con, instalacao_nova):
    """1.9: faixa escura do topo sem Ramais/Sistemas e itens do menu como
    "Link N". Cada ajuste roda uma única vez; o que o administrador mudar
    depois não é desfeito. (Sem row_factory aqui: colunas por posição.)"""
    def feito(marca):
        return con.execute('SELECT 1 FROM config WHERE chave=?', (marca,)).fetchone()

    def marca(m):
        con.execute("INSERT OR REPLACE INTO config (chave,valor) VALUES (?,'1')", (m,))

    if not feito('faixa_v19'):
        r = con.execute("SELECT valor FROM config WHERE chave='faixa_links'").fetchone()
        if r:
            padrao = ('ramais|/ramais', 'sistemas|/sistemas')
            linhas = [l for l in r[0].splitlines()
                      if re.sub(r'\s+', '', l).lower() not in padrao]
            con.execute("UPDATE config SET valor=? WHERE chave='faixa_links'",
                        ('\n'.join(linhas),))
        marca('faixa_v19')

    if not feito('menu_links_v19'):
        if not instalacao_nova:
            n = 0
            for tabela in ('menu_itens', 'paginas_lateral'):
                for rid, chave in con.execute(
                        f"SELECT id,chave FROM {tabela} WHERE chave NOT IN ('inicio','admin')"
                        ' ORDER BY ordem, id').fetchall():
                    n += 1
                    con.execute(f'UPDATE {tabela} SET nome=? WHERE id=?', (f'Link {n}', rid))
        marca('menu_links_v19')

    # 1.9.1: "Ramais" volta a ser Ramais (o Link 1 não é mais dele) e o Link 1
    # passa a levar às Notícias, como primeira página da lista.
    if not feito('menu_links_v19b'):
        if not instalacao_nova:
            con.execute("UPDATE menu_itens SET nome='Ramais' WHERE chave='ramais' AND nome='Link 1'")
            if not con.execute("SELECT 1 FROM paginas_lateral WHERE chave='noticias-link'").fetchone():
                menor = con.execute('SELECT COALESCE(MIN(ordem),0) FROM paginas_lateral').fetchone()[0]
                con.execute("INSERT INTO paginas_lateral (chave,nome,icone,url,ordem,ativo)"
                            " VALUES ('noticias-link','Link 1','','/noticias',?,1)", (menor - 1,))
        marca('menu_links_v19b')

    # 1.9.2: "Ramais" sai da barra de seções; ficam só o cartão da tela inicial e
    # a página /ramais (aberta pelo nome do cartão). Só desligado, nunca apagado:
    # dá para religar em Administração → Painel → Menu.
    if not feito('menu_ramais_v192'):
        con.execute("UPDATE menu_itens SET ativo=0 WHERE chave='ramais'")
        marca('menu_ramais_v192')


def _separar_paginas_laterais(con, instalacao_nova):
    """Desvincula a lista "Páginas" do menu do topo, uma única vez.

    Até a 1.4 as duas coisas eram a mesma tabela: renomear "Início" na lista
    lateral mudava o topo do portal. Agora a lista tem tabela própria.
    - Os itens que não são do sistema (nem Início, nem Ramais) passam para ela.
    - Se Início ou Ramais tinham sido renomeados ou apontados para outro
      endereço, é porque alguém os usava como link da lateral: viram uma
      página da lateral e o item do topo volta ao que era."""
    if con.execute("SELECT 1 FROM config WHERE chave='paginas_separadas'").fetchone():
        return
    # Sem a marca, a migração nunca terminou: recomeça do zero (uma tentativa
    # interrompida não pode deixar itens repetidos).
    con.execute('DELETE FROM paginas_lateral')
    ordem = 0
    usadas = {r[0] for r in con.execute('SELECT chave FROM paginas_lateral')}

    def nova(chave_base, nome, icone, url, ativo=1):
        nonlocal ordem
        chave, n = chave_base, 2
        while chave in usadas or chave in ('inicio', 'ramais', 'admin'):
            chave, n = f'{chave_base}-{n}', n + 1
        usadas.add(chave)
        con.execute('INSERT INTO paginas_lateral (chave,nome,icone,url,ordem,ativo)'
                    ' VALUES (?,?,?,?,?,?)', (chave, nome, icone, url, ordem, ativo))
        ordem += 1
        return chave

    if instalacao_nova:
        for chave, nome, icone in PAGINAS_SEMENTE:
            nova(chave, nome, icone, '')
    else:
        # Sem row_factory aqui (init_db usa tuplas): colunas por posição.
        for chave, nome, icone, url, ativo in con.execute(
                "SELECT chave,nome,icone,url,ativo FROM menu_itens WHERE chave NOT IN"
                " ('inicio','ramais','admin') ORDER BY ordem, id").fetchall():
            nova(chave, nome, icone, url, ativo)
        con.execute("DELETE FROM menu_itens WHERE chave NOT IN ('inicio','ramais','admin')")
        for rid, chave_s, nome_s, icone_s, url_s, ativo_s in con.execute(
                "SELECT id,chave,nome,icone,url,ativo FROM menu_itens"
                " WHERE chave IN ('inicio','ramais')").fetchall():
            nome, icone = MENU_PADRAO[chave_s]
            if nome_s != nome or url_s or (icone_s or '') != icone:
                chave = nova(_slug(nome_s), nome_s, icone_s, url_s, ativo_s)
                con.execute('UPDATE pagina_blocos SET chave=? WHERE chave=?', (chave, chave_s))
                con.execute("UPDATE menu_itens SET nome=?,icone=?,url='' WHERE id=?",
                            (nome, icone, rid))
    con.execute("INSERT INTO config (chave,valor) VALUES ('paginas_separadas','1')")


def montar_paginas():
    """Itens da lista "Páginas" da tela inicial (tabela própria)."""
    itens = []
    for r in db().execute('SELECT * FROM paginas_lateral WHERE ativo=1 ORDER BY ordem, id'):
        if r['url']:
            destino, externo = r['url'], not r['url'].startswith('/')
        else:
            destino, externo = url_for('modulo', chave=r['chave']), False
        itens.append({'chave': r['chave'], 'nome': r['nome'],
                      'ic': r['icone'] or '▸', 'href': destino, 'externo': externo})
    return itens


def montar_menu():
    """Menu lateral a partir do banco. Sem endereço próprio, o item usa a rota
    interna correspondente ou, na falta dela, a página de módulo em preparação."""
    itens = []
    for r in db().execute('SELECT * FROM menu_itens WHERE ativo=1 ORDER BY ordem, id'):
        if r['url']:
            destino, externo = r['url'], not r['url'].startswith('/')
        elif r['chave'] in ROTAS_INTERNAS:
            destino, externo = url_for(ROTAS_INTERNAS[r['chave']]), False
        else:
            destino, externo = url_for('modulo', chave=r['chave']), False
        itens.append({'chave': r['chave'], 'nome': r['nome'],
                      'ic': r['icone'] or '▸', 'href': destino, 'externo': externo})
    return itens


def endereco_seguro(url):
    """Endereço digitado à mão, pronto para ir num href.

    Aceita caminho interno (/ramais), http(s), mailto e tel; sem esquema,
    assume http. Qualquer outro esquema (javascript:, data:) vira vazio —
    quem edita é administrador, mas um href não deve executar código.
    """
    url = (url or '').strip()
    if not url:
        return ''
    if url.startswith('/') and not url.startswith('//'):
        return url
    esquema = re.match(r'^([a-z][a-z0-9+.\-]*):', url, re.I)
    if esquema:
        return url if esquema.group(1).lower() in ('http', 'https', 'mailto', 'tel') else ''
    return 'http://' + url


def linhas_faixa(texto):
    """Faixa de links do topo: "Nome | endereço" por linha. Sem endereço, o
    nome aparece como texto, sem link."""
    itens = []
    for linha in (texto or '').splitlines():
        nome, _, url = linha.partition('|')
        nome = nome.strip()
        if not nome:
            continue
        href = endereco_seguro(url)
        itens.append({'nome': nome, 'href': href,
                      'externo': bool(href) and not href.startswith('/')})
    return itens


def dados_destaque():
    """Cartão "Em destaque" da tela inicial, ou None se estiver desligado ou
    sem título (um cartão sem título seria só uma caixa colorida)."""
    c = cfg()
    if c.get('destaque_ativo') != '1' or not c.get('destaque_titulo', '').strip():
        return None
    href = endereco_seguro(c.get('destaque_url'))
    return {'rotulo': c.get('destaque_rotulo', '').strip(),
            'titulo': c['destaque_titulo'].strip(),
            'texto': c.get('destaque_texto', '').strip(),
            'cta': c.get('destaque_cta', '').strip(),
            'href': href, 'externo': bool(href) and not href.startswith('/')}


def _texto_em_paragrafos(texto):
    """Quebra o texto digitado em parágrafos (separados por linha em branco).
    Um parágrafo em que toda linha começa por "- " vira lista."""
    saida = []
    for bloco in re.split(r'\n\s*\n', (texto or '').replace('\r\n', '\n').strip('\n')):
        linhas = [l.rstrip() for l in bloco.split('\n') if l.strip()]
        if not linhas:
            continue
        if all(l.lstrip().startswith(('- ', '• ')) for l in linhas):
            saida.append({'lista': [l.lstrip()[2:].strip() for l in linhas]})
        else:
            saida.append({'linhas': [l.strip() for l in linhas]})
    return saida


def texto_para_html(texto):
    """Texto simples (blocos da versão 1.3.0) como HTML, para o editor e para a
    página. Tudo é escapado: o que foi digitado nunca vira marcação."""
    partes = []
    for p in _texto_em_paragrafos(texto):
        if 'lista' in p:
            partes.append('<ul>' + ''.join(f'<li>{escape(i)}</li>' for i in p['lista']) + '</ul>')
        else:
            partes.append('<p>' + '<br>'.join(str(escape(l)) for l in p['linhas']) + '</p>')
    return ''.join(partes)


# ── texto formatado das páginas ────────────────────────────────────────────────
# O editor da página grava HTML. Como esse HTML é mostrado a todos, nada do que
# chega do navegador é confiado: tudo passa por esta limpeza, que só deixa
# passar uma lista curta de tags e de propriedades de estilo. Script, evento
# (onclick…), iframe, classe e endereço javascript: nunca chegam à página.

_TAGS_OK = {'p', 'br', 'strong', 'em', 'u', 's', 'ul', 'ol', 'li', 'h2', 'h3',
            'h4', 'blockquote', 'a', 'span', 'div'}
_TAGS_COM_ESTILO = {'p', 'div', 'span', 'li', 'h2', 'h3', 'h4', 'blockquote'}
_CLASSES_IMG = {'im-p', 'im-m', 'im-g', 'im-c', 'im-esq', 'im-dir', 'im-centro', 'im-bloco', 'im-bloco-dir'}
_SINONIMOS = {'b': 'strong', 'i': 'em', 'strike': 's', 'del': 's', 'h1': 'h2',
              'h5': 'h4', 'h6': 'h4', 'font': 'span'}
_DESCARTA = {'script', 'style', 'iframe', 'object', 'embed', 'noscript',
             'template', 'svg', 'math', 'head', 'title'}
_FONT_SIZE = {'1': .75, '2': .875, '3': 1, '4': 1.125, '5': 1.5, '6': 2, '7': 3}
_FONT_PALAVRA = {'xx-small': .6, 'x-small': .7, 'small': .875, 'medium': 1,
                 'large': 1.25, 'x-large': 1.5, 'xx-large': 2, 'xxx-large': 3}
_COR = re.compile(r'^(#[0-9a-f]{3}|#[0-9a-f]{6})$', re.I)
_RGB = re.compile(r'^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*[\d.]+\s*)?\)$', re.I)
_TAM = re.compile(r'^(\d+(?:\.\d+)?)(rem|em|px|%)$')


def _cor_limpa(valor):
    valor = (valor or '').strip()
    if _COR.match(valor):
        return valor.lower()
    m = _RGB.match(valor)
    if m and all(int(x) <= 255 for x in m.groups()):
        return '#%02x%02x%02x' % tuple(int(x) for x in m.groups())
    return ''


def _estilo_limpo(css):
    """Só as propriedades que o editor produz, com valores conferidos."""
    saida = []
    for decl in (css or '').split(';'):
        prop, _, valor = decl.partition(':')
        prop, valor = prop.strip().lower(), valor.strip().lower()
        if prop in ('color', 'background-color'):
            c = _cor_limpa(valor)
            if c:
                saida.append(f'{prop}:{c}')
        elif prop == 'font-size':
            rem = _FONT_PALAVRA.get(valor)
            m = _TAM.match(valor)
            if m:
                n, un = float(m.group(1)), m.group(2)
                rem = {'rem': n, 'em': n, 'px': n / 16, '%': n / 100}[un]
            if rem is not None and .5 <= rem <= 6:        # 8 a 96 px
                saida.append(f'font-size:{round(rem, 3)}rem')
        elif prop == 'text-align' and valor in ('left', 'center', 'right', 'justify'):
            saida.append(f'text-align:{valor}')
        elif prop == 'font-weight' and valor in ('bold', '700', '600', '800'):
            saida.append('font-weight:700')
        elif prop == 'font-style' and valor == 'italic':
            saida.append('font-style:italic')
        elif prop == 'text-decoration' and valor in ('underline', 'line-through'):
            saida.append(f'text-decoration:{valor}')
    return ';'.join(saida)


class _LimpaHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.saida, self.pilha, self.pular = [], [], 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _DESCARTA:
            self.pular += 1
            return
        if self.pular:
            return
        original = tag
        tag = _SINONIMOS.get(tag, tag)
        attrs = {k.lower(): (v or '') for k, v in attrs}
        emitida = None
        if tag == 'img':
            # Só imagens da própria biblioteca (static/uploads); nada de endereço
            # externo, data: ou javascript:.
            m = re.fullmatch(r'/static/uploads/([A-Za-z0-9._\-]+\.(?:png|jpe?g|gif|webp))',
                             attrs.get('src', '').strip())
            if m:
                alt = escape(attrs.get('alt', '')[:300])
                # Tamanho e posição escolhidos no editor; só valores conhecidos.
                cls = ' '.join(c for c in attrs.get('class', '').split() if c in _CLASSES_IMG)
                cls = f' class="{cls}"' if cls else ''
                # Largura arrastada no editor, em % (5 a 100); nada de outro CSS.
                # Largura em pixels (campo "Largura" do editor); vale mais que a em %.
                px = re.fullmatch(r'\s*(\d{1,4})(?:\.\d+)?\s*(?:px)?\s*', attrs.get('data-px', '')) or \
                    re.search(r'(?<![-\w])width\s*:\s*(\d{1,4})(?:\.\d+)?px', attrs.get('style', ''))
                w = None if px else (re.search(r'(\d{1,3})(?:\.\d+)?\s*%?', attrs.get('data-w', '')) or
                                     re.search(r'width\s*:\s*(\d{1,3})(?:\.\d+)?%', attrs.get('style', '')))
                if px:
                    estilo_w = f' style="width:{max(20, min(2000, int(px.group(1))))}px"'
                else:
                    estilo_w = f' style="width:{max(5, min(100, int(w.group(1))))}%"' if w else ''
                self.saida.append(f'<img src="/static/uploads/{m.group(1)}" alt="{alt}" loading="lazy"{cls}{estilo_w}>')
            return
        if tag in _TAGS_OK:
            estilo = _estilo_limpo(attrs.get('style'))
            if original == 'font':                # <font color size> do editor
                extra = []
                c = _cor_limpa(attrs.get('color'))
                if c:
                    extra.append(f'color:{c}')
                if attrs.get('size') in _FONT_SIZE:
                    extra.append(f"font-size:{_FONT_SIZE[attrs['size']]}rem")
                estilo = ';'.join(filter(None, [estilo] + extra))
            if tag == 'br':
                self.saida.append('<br>')
                return
            marcas = ''
            if tag == 'a':
                href = endereco_seguro(attrs.get('href'))
                if href:
                    ext = ' target="_blank" rel="noopener"' if not href.startswith('/') else ''
                    marcas = f' href="{escape(href)}"{ext}'
                    emitida = tag
            else:
                emitida = tag
            if emitida == 'div':
                # Figura (imagem + texto na mesma largura): só estas classes e a largura em px.
                cls = [c for c in attrs.get('class', '').split() if c in ('fig', 'fig-e', 'fig-c', 'fig-d')]
                if 'fig' in cls:
                    marcas += f' class="{" ".join(cls)}"'
                    mw = re.search(r'(?<![-\w])width\s*:\s*(\d{1,4})(?:\.\d+)?px', attrs.get('style', ''))
                    if mw:
                        estilo = ';'.join(filter(None, [estilo, f'width:{max(20, min(2000, int(mw.group(1))))}px']))
            if emitida:
                if estilo and tag in _TAGS_COM_ESTILO:
                    marcas += f' style="{escape(estilo)}"'
                self.saida.append(f'<{tag}{marcas}>')
        self.pilha.append((original, emitida))

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _DESCARTA:
            self.pular = max(0, self.pular - 1)
            return
        if self.pular:
            return
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i][0] == tag:
                while len(self.pilha) > i:
                    _, emitida = self.pilha.pop()
                    if emitida:
                        self.saida.append(f'</{emitida}>')
                return

    def handle_data(self, dados):
        if not self.pular:
            self.saida.append(str(escape(dados)))

    def resultado(self):
        while self.pilha:
            _, emitida = self.pilha.pop()
            if emitida:
                self.saida.append(f'</{emitida}>')
        return ''.join(self.saida)


def limpa_html(html):
    """HTML do editor da página, reduzido ao que é permitido (ver acima)."""
    p = _LimpaHTML()
    p.feed((html or '')[:60000])
    p.close()
    return p.resultado()


def so_texto(html):
    """O texto visível de um trecho de HTML, para saber se o bloco está vazio."""
    return re.sub(r'<[^>]+>', '', html or '').replace('&nbsp;', ' ').strip()


ALINHA_IMG = {'esq': 'flex-start', 'centro': 'center', 'dir': 'flex-end'}
ROTULO_ALINHA = {'esq': 'À esquerda', 'centro': 'Centralizada', 'dir': 'À direita'}
LARGURAS_IMG = {100: 'Largura total', 75: '3/4 da largura', 50: 'Metade',
                33: 'Um terço', 25: 'Um quarto'}
ESTILOS_TEXTO = {'normal': 'Normal', 'destaque': 'Destaque (fundo azul claro)',
                 'aviso': 'Aviso (fundo amarelo)', 'quadro': 'Quadro (com contorno)'}


def agrupar_blocos(linhas):
    """Blocos da página prontos para desenhar. Imagens seguidas entram na mesma
    fileira e se acomodam lado a lado conforme a largura de cada uma."""
    saida = []
    for b in linhas:
        ativo = bool(b['ativo'])
        if b['tipo'] == 'imagem':
            if not b['arquivo']:
                continue
            item = {'id': b['id'], 'arquivo': b['arquivo'], 'ativo': ativo,
                    'legenda': b['texto'] or '',
                    'url': endereco_seguro(b['url']),
                    'larg': b['larg'] if b['larg'] in LARGURAS_IMG else 100,
                    'alinh': b['alinh'] if b['alinh'] in ALINHA_IMG else 'centro'}
            if saida and saida[-1]['tipo'] == 'imagens':
                saida[-1]['itens'].append(item)
            else:
                saida.append({'tipo': 'imagens', 'itens': [item]})
        elif b['tipo'] == 'subtitulo':
            if (b['texto'] or '').strip():
                saida.append({'tipo': 'subtitulo', 'id': b['id'], 'ativo': ativo,
                              'texto': b['texto'].strip(), 'url': endereco_seguro(b['url'])})
        elif b['tipo'] == 'botao':
            if (b['texto'] or '').strip() and endereco_seguro(b['url']):
                saida.append({'tipo': 'botao', 'id': b['id'], 'ativo': ativo,
                              'texto': b['texto'].strip(), 'url': endereco_seguro(b['url']),
                              'alinh': b['alinh'] if b['alinh'] in ALINHA_IMG else 'esq'})
        else:
            html = (limpa_html(b['texto']) if b['formato'] == 'html'
                    else texto_para_html(b['texto']))
            if so_texto(html) or '<li' in html or '<img' in html:
                saida.append({'tipo': 'texto', 'id': b['id'], 'ativo': ativo,
                              'html': Markup(html),
                              'estilo': b['estilo'] if b['estilo'] in ESTILOS_TEXTO else 'normal'})
    for g in saida:
        if g['tipo'] == 'imagens':
            g['justifica'] = ALINHA_IMG[g['itens'][0]['alinh']]
    return saida


def _dt_banco(valor):
    """'2026-10-21T05:30' (campo datetime-local) -> '2026-10-21 05:30:00'.
    Devolve '' se não for uma data válida."""
    valor = (valor or '').strip().replace('T', ' ')
    for formato in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(valor, formato).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
    return ''


def _dt_exibe(valor):
    """'2026-10-21 05:30:00' -> '21/10/2026 05h30'."""
    try:
        return datetime.strptime((valor or '')[:16], '%Y-%m-%d %H:%M').strftime('%d/%m/%Y %Hh%M')
    except ValueError:
        return ''


def _dt_campo(valor):
    """'2026-10-21 05:30:00' -> '2026-10-21T05:30' (valor de datetime-local)."""
    return (valor or '')[:16].replace(' ', 'T')


def pagina_tocada(con, chave):
    """Marca a página como atualizada agora. Chamada a cada alteração do
    conteúdo, para o "Atualizada em" do cabeçalho nunca ficar desatualizado."""
    con.execute("UPDATE paginas_lateral SET atualizada_em=datetime('now','localtime')"
                " WHERE chave=?", (chave,))


def cabecalho_pagina(item):
    """Cabeçalho de matéria de uma página de conteúdo, pronto para o template:
    chapéu, linha fina, autor e datas, foto de capa e resumo. Campo vazio fica
    de fora; página sem nenhum deles mostra só o título, como sempre mostrou."""
    def txt(campo):
        return (item[campo] or '').strip()
    autor = txt('autor')
    publicada = _dt_exibe(item['publicada_em'])
    atualizada = _dt_exibe(item['atualizada_em'])
    # "Atualizada em" só acompanha uma assinatura: numa página sem autor nem data
    # de publicação ele apareceria sozinho, só porque alguém mexeu num bloco.
    if not (autor or publicada) or atualizada == publicada:
        atualizada = ''
    capa = os.path.basename(item['capa'] or '')
    if capa and not os.path.isfile(os.path.join(UPLOAD_DIR, capa)):
        capa = ''
    legenda = txt('capa_legenda')
    resumo = [l.strip()[:200] for l in (item['resumo'] or '').splitlines() if l.strip()][:6]
    return {
        'chapeu': txt('chapeu'), 'linha_fina': txt('linha_fina'), 'autor': autor,
        'publicada': publicada, 'atualizada': atualizada,
        'capa': capa,
        'capa_url': url_for('static', filename='uploads/' + capa) if capa else '',
        'capa_alt': modulos.midia.alt_de(capa, legenda) if capa else '',
        'legenda': legenda, 'credito': txt('capa_credito'),
        'resumo': resumo if item['mostrar_resumo'] else [],
        'leia': bool(item['mostrar_leia']),
    }


def leia_tambem(limite=3):
    """As últimas notícias publicadas, para o "Leia também" no fim da página."""
    saida = []
    for n in modulos.noticias.recentes(limite):
        destino = n['destino_url'] or url_for('noticia', slug=n['slug'])
        saida.append({'titulo': n['titulo'], 'url': destino,
                      'externo': destino.startswith('http'),
                      'data': modulos.noticias._data_br(n['publicar_em']),
                      'capa': n['capa'] or '',
                      'alt': n['capa_alt'] or ''})
    return saida


def blocos_para_html(linhas):
    """Blocos antigos da página (subtítulo, texto, imagem, botão) como um único
    HTML, para abrir no editor livre sem perder o que já foi escrito."""
    partes = []
    for b in linhas:
        if not b['ativo']:
            continue
        t = b['tipo']
        if t == 'subtitulo' and (b['texto'] or '').strip():
            partes.append(f"<h2>{escape(b['texto'].strip())}</h2>")
        elif t == 'texto':
            partes.append(limpa_html(b['texto']) if b['formato'] == 'html'
                          else str(texto_para_html(b['texto'])))
        elif t == 'imagem' and b['arquivo']:
            cls = {'esq': 'im-bloco', 'dir': 'im-bloco-dir'}.get(b['alinh'], 'im-centro')
            w = f' data-w="{int(b["larg"])}"' if (b['larg'] or 100) < 100 else ''
            img = (f'<img src="/static/uploads/{escape(os.path.basename(b["arquivo"]))}" '
                   f'alt="{escape(b["texto"] or "")}" class="{cls}"{w}>')
            if b['url']:
                img = f'<a href="{escape(b["url"])}">{img}</a>'
            partes.append(f'<p>{img}</p>')
        elif t == 'botao' and b['url']:
            partes.append(f'<p><a href="{escape(b["url"])}">{escape(b["texto"] or b["url"])}</a></p>')
    return limpa_html(''.join(partes))


@app.route('/modulo/<chave>')
def modulo(chave):
    row = db().execute('SELECT * FROM paginas_lateral WHERE chave=?', (chave,)).fetchone()
    if not row:
        abort(404)
    cab = cabecalho_pagina(row)
    leia = leia_tambem() if cab['leia'] else []
    admin = bool(session.get('admin'))
    # O administrador vê também os blocos ocultos (esmaecidos): é por eles que
    # edita a página diretamente, com o botão direito.
    linhas = db().execute('SELECT * FROM pagina_blocos WHERE chave=?'
                          + ('' if admin else ' AND ativo=1') + ' ORDER BY ordem, id',
                          (chave,)).fetchall()
    cru = []
    if admin:
        for b in linhas:
            html = ''
            if b['tipo'] == 'texto':
                html = (limpa_html(b['texto']) if b['formato'] == 'html'
                        else texto_para_html(b['texto']))
            cru.append({'id': b['id'], 'tipo': b['tipo'], 'ativo': bool(b['ativo']),
                        'texto': html if b['tipo'] == 'texto' else (b['texto'] or ''),
                        'url': b['url'] or '', 'larg': b['larg'], 'alinh': b['alinh'],
                        'estilo': b['estilo'],
                        'imagem': url_for('static', filename='uploads/' + b['arquivo'])
                                  if b['arquivo'] else ''})
    corpo = limpa_html(row['corpo'] or '') if (row['corpo'] or '').strip() else ''
    return render_template('modulo.html', chave=chave, nome=row['nome'],
                           cab=cab, leia=leia, corpo=Markup(corpo),
                           corpo_editar=Markup(corpo or (blocos_para_html(linhas) if admin else '')),
                           cab_campos=row if admin else None,
                           blocos=agrupar_blocos(linhas), edicao=admin, blocos_cru=cru,
                           destinos=destinos_de_links() if admin else [],
                           larguras=LARGURAS_IMG, alinhamentos=ROTULO_ALINHA,
                           estilos=ESTILOS_TEXTO)


DIAS_SEMANA = ['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira',
               'sexta-feira', 'sábado', 'domingo']


def data_extenso():
    """"segunda-feira, 19 de outubro" — para a faixa do topo. Calculada a cada
    resposta, pelo mesmo motivo do ano do rodapé."""
    h = datetime.now()
    return f'{DIAS_SEMANA[h.weekday()]}, {h.day} de {MESES[h.month - 1].lower()}'


@app.context_processor
def _injeta():
    fundo, fundo_v = fundo_atual()
    logo, logo_v = logo_atual()
    # tem_ramais fica aqui porque o menu lateral aparece em todas as páginas
    tem_ramais = db().execute(
        'SELECT 1 FROM ramais WHERE ativo=1 LIMIT 1').fetchone() is not None
    menu = montar_menu()
    if session.get('admin'):
        menu.append({'chave': 'admin', 'nome': 'Administração', 'ic': 'engrenagem',
                     'href': url_for('admin'), 'externo': False})
    # Contadores dos sinos da barra superior. São dados reais — chamado ainda
    # não concluído e comunicado marcado como urgente; sem isso o número seria
    # enfeite com aparência de aviso.
    aviso_chamados = db().execute(
        "SELECT COUNT(*) c FROM chamados WHERE ativo=1 AND situacao<>'concluido'"
    ).fetchone()['c']
    aviso_comunicados = db().execute(
        "SELECT COUNT(*) c FROM lateral WHERE ativo=1 AND urgencia='urgente'"
    ).fetchone()['c']
    return {'cfg': cfg(), 'csrf_token': token_csrf(),
            'faixa_links': linhas_faixa(cfg('faixa_links')),
            'destaque': dados_destaque(),
            'fundo_nome': fundo, 'fundo_versao': fundo_v,
            'logo_nome': logo, 'logo_versao': logo_v,
            'tem_ramais': tem_ramais, 'menu': menu, 'versao': VERSAO,
            'paginas_lateral': montar_paginas(),
            # calculado a cada resposta: a virada de ano não exige reiniciar
            'ano_atual': datetime.now().year,
            'data_extenso': data_extenso(),
            'meses': MESES,
            'mes_numero': datetime.now().month,
            'mes_atual_nome': MESES[datetime.now().month - 1],
            'limites': LIMITES, 'icones': sorted(ICONES),
            # Resolvida aqui: o template não deve escolher pilha de fonte, e
            # assim só entra no <style> um valor da lista fechada.
            'fonte_comunicado': FONTES_TEXTO.get(
                cfg('com_fonte'), FONTES_TEXTO['padrao'])[1],
            # Uma pilha de fontes por cartão, já resolvida: o template não deve
            # escolher família, e assim só entra no <style> valor da lista.
            'aparencia_cartoes': [
                (pref, FONTES_TEXTO.get(cfg(f'{pref}_fonte'),
                                        FONTES_TEXTO['padrao'])[1])
                for pref in prefixos_aparencia()],
            'icones_proprios': icones_enviados(), 'prefixo_icone': ICONE_ARQ,
            'aviso_chamados': aviso_chamados,
            'aviso_comunicados': aviso_comunicados,
            'usuario_nome': session.get('nome'),
            'ultimo_acesso': session.get('ultimo_acesso'),
            'eh_admin': bool(session.get('admin')),
            # Só a página /editor mostra os controles de edição; a inicial,
            # mesmo para o administrador, é o portal como todos o veem.
            'modo_edicao': bool(session.get('admin'))
                           and request.endpoint == 'editor'}


@app.template_filter('texto_longo')
def _texto_longo(texto, linhas=5, caracteres=320):
    """O comunicado não cabe no cartão do painel?

    Decidido aqui, e não no CSS, porque a folha não tem como saber se o texto
    transbordou — e esmaecer o fim de um comunicado curto pareceria defeito.
    Conta as duas coisas: muitas linhas curtas ocupam altura igual a poucas
    linhas longas."""
    texto = texto or ''
    return len(texto.splitlines()) > linhas or len(texto) > caracteres


# Linha que começa por marcador: emoji, bullet, travessão, "1." ou "a)". Só
# essas ganham recuo pendente — é para elas que ele foi feito, para o texto que
# dobra alinhar embaixo do texto e não embaixo do símbolo. Em prosa corrida não
# há símbolo à esquerda, e o recuo virava um degrau em toda linha que dobrava.
_MARCADORES = '-–—*+•·▪▫◦‣⁃▶►'
_MARCADOR = re.compile(
    rf'^\s*(?:[{re.escape(_MARCADORES)}]|\d{{1,3}}[.)]|[a-zA-Z][.)])\s'
    r'|^\s*[←-⇿☀-➿⬀-⯿\U0001F000-\U0001FAFF]'
)


@app.template_filter('linhas')
def _linhas(texto):
    """Cada linha do comunicado vira um bloco próprio.

    É o que permite o recuo pendente: a linha que dobra sozinha volta alinhada
    ao texto, não à margem — e o emoji do começo fica solto à esquerda, como
    numa lista. Não dá para fazer isso digitando espaço, porque o ponto da
    quebra muda com a largura da tela.

    O recuo vale só para linha que abre com marcador. Aplicado a todas, ele
    deslocava para a direita cada linha dobrada de um parágrafo comum, sem nada
    à esquerda que justificasse a sobra.

    Linha vazia vira um bloco vazio, que o CSS transforma em respiro."""
    partes = (texto or '').splitlines() or ['']
    pedacos = []
    for linha in partes:
        classes = 'linha-com'
        if not linha.strip():
            classes += ' linha-vazia'
        # Testado no texto cru: depois do escape um "-" continua "-", mas
        # qualquer marcador que vire entidade deixaria de casar.
        elif _MARCADOR.match(linha):
            classes += ' linha-recuo'
        pedacos.append(f'<span class="{classes}">{escape(linha)}</span>')
    return Markup(''.join(pedacos))


@app.template_filter('iniciais')
def _iniciais(nome):
    """Iniciais para o avatar: primeiro e último nome. Nome único devolve as
    duas primeiras letras, senão o círculo fica com uma letra solta."""
    partes = [p for p in (nome or '').split() if p]
    if not partes:
        return '?'
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


@app.template_filter('sigla_turno')
def _sigla_turno(nome):
    """Sigla curta para o círculo da escala.

    "Turno I", "Turno II" e "Turno III" começam todos com as mesmas duas
    letras — cortar em dois caracteres dava "TU" em todos e o círculo deixava
    de distinguir coisa alguma. Número romano no fim vira algarismo."""
    palavras = [p for p in (nome or '').split() if p]
    if not palavras:
        return '?'
    romanos = {'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'V': '5',
               'VI': '6', 'VII': '7', 'VIII': '8', 'IX': '9', 'X': '10'}
    ultimo = palavras[-1].upper().strip('.º°')
    if len(palavras) > 1 and ultimo in romanos:
        return (palavras[0][0] + romanos[ultimo]).upper()
    if len(palavras) > 1:
        return (palavras[0][0] + palavras[-1][0]).upper()
    return palavras[0][:2].upper()


@app.template_filter('partes_numeros')
def _partes_numeros(txt):
    """Separa "202 / 256" nos números que compõem o ramal, para o cartão
    alinhá-los em colunas próprias em vez de imprimir a linha inteira."""
    return [p for p in re.split(r'\s*[/,;–—-]\s*|\s{2,}', (txt or '').strip()) if p]


@app.template_filter('icone_valido')
def _icone_valido(valor):
    """Nome de ícone para marcar no seletor — traduz o emoji de instalações
    antigas para o desenho equivalente."""
    return nome_icone(valor)


# ── páginas públicas (exigem login) ────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        usuario = (request.form.get('usuario') or '').strip()
        senha   = request.form.get('senha') or ''
        espera = modulos.seguranca.espera_login(usuario)
        if espera:
            minutos = -(-espera // 60)
            modulos.auditoria.registrar('login bloqueado', usuario, 'muitas tentativas', usuario=usuario)
            return render_template(
                'login.html', erro=f'Muitas tentativas de acesso. Tente de novo em {minutos} minuto(s).'), 429
        row = db().execute('SELECT * FROM usuarios WHERE usuario=? AND ativo=1',
                           (usuario,)).fetchone()
        if row and check_password_hash(row['senha_hash'], senha):
            modulos.seguranca.limpa_falhas(usuario)
            session.clear()
            session['uid']   = row['id']
            session['user']  = row['usuario']
            session['nome']  = row['nome']
            session['admin'] = bool(row['admin'])
            # Guarda o acesso anterior antes de gravar o de agora — quem entra
            # quer ver quando esteve aqui da última vez, não o relógio atual.
            session['ultimo_acesso'] = row['ultimo_acesso'] or ''
            modulos.auditoria.registrar('login', row['usuario'], 'acesso ao portal')
            con = db()
            con.execute("UPDATE usuarios SET ultimo_acesso=datetime('now','localtime')"
                        ' WHERE id=?', (row['id'],))
            con.commit()
            # Administrador entra direto no editor do portal; os demais, no portal.
            destino = request.args.get('proximo') or (
                url_for('editor') if session['admin'] else url_for('index'))
            # Só aceita caminho interno — evita redirecionar para site externo
            if not destino.startswith('/') or destino.startswith('//'):
                destino = url_for('index')
            return redirect(destino)
        modulos.seguranca.registra_falha(usuario)
        modulos.auditoria.registrar('login falhou', usuario, 'usuário ou senha inválidos', usuario=usuario)
        erro = 'Usuário ou senha inválidos.'
    return render_template('login.html', erro=erro)


@app.route('/sistemas')
def sistemas():
    """Página "Ver todos" dos sistemas, com os atalhos e reservas ao lado."""
    con = db()
    return render_template(
        'sistemas.html',
        sistemas=agrupar_por_categoria(
            con.execute("SELECT * FROM links WHERE ativo=1 AND grupo='sistema'"
                        ' ORDER BY ordem, id').fetchall()),
        atalhos=con.execute("SELECT * FROM links WHERE ativo=1 AND grupo='atalho'"
                            ' ORDER BY ordem, id').fetchall(),
        reservas=con.execute("SELECT * FROM links WHERE ativo=1 AND grupo='reserva'"
                             ' ORDER BY ordem, id').fetchall())


@app.route('/ramais')
def ramais():
    """Lista de ramais — aberta, como a página inicial. A busca é feita no
    navegador, então filtra enquanto se digita, sem recarregar."""
    return render_template('ramais.html', itens=db().execute(
        'SELECT * FROM ramais WHERE ativo=1 ORDER BY setor COLLATE NOCASE, id'
    ).fetchall())


@app.route('/sair')
def sair():
    session.clear()
    return redirect(url_for('index'))


def saudacao():
    """Bom dia / Boa tarde / Boa noite, pelo relógio do servidor."""
    hora = datetime.now().hour
    if hora < 12:
        return 'Bom dia'
    return 'Boa tarde' if hora < 18 else 'Boa noite'


def agrupar_por_categoria(itens):
    """[(categoria, [itens])] preservando a ordem cadastrada.

    O grupo sem categoria vai sempre na frente. Ele é desenhado sem subtítulo,
    então em qualquer outra posição os itens dele apareceriam logo abaixo do
    título do grupo anterior e passariam por ser daquela categoria."""
    grupos, indice = [], {}
    for item in itens:
        chave = (item['categoria'] or '').strip()
        if chave not in indice:
            indice[chave] = len(grupos)
            grupos.append((chave, []))
        grupos[indice[chave]][1].append(item)
    return sorted(grupos, key=lambda g: g[0] != '')


def ramais_do_painel(con):
    """Ramais do cartão da página inicial.

    Sem nenhum marcado como destaque o cartão apareceria vazio mesmo com a
    lista cheia — o que acontece logo após instalar ou restaurar um backup
    antigo. Nesse caso mostra os primeiros em ordem alfabética."""
    marcados = con.execute('SELECT * FROM ramais WHERE ativo=1 AND destaque=1'
                           ' ORDER BY setor COLLATE NOCASE').fetchall()
    if marcados:
        return marcados
    return con.execute('SELECT * FROM ramais WHERE ativo=1'
                       ' ORDER BY setor COLLATE NOCASE LIMIT ?',
                       (LIMITES['ramais'],)).fetchall()


@app.route('/editor')
@admin_obrigatorio
def editor():
    """O portal em modo de edição: o administrador entra aqui ao fazer login.
    É a mesma página inicial, com os controles de edição (nome do cartão leva
    à edição, imagens redimensionáveis, layout livre arrastável)."""
    return index()


@app.route('/')
def index():
    """Painel inicial — aberto a qualquer pessoa da rede. O login existe só
    para o gerenciamento do conteúdo (ver as rotas /admin).

    Os cartões existem sempre, mesmo vazios: assim a página não muda de forma
    conforme vai sendo preenchida."""
    con = db()
    mes = datetime.now().month

    def quantos(consulta):
        return con.execute(consulta).fetchone()[0]

    def quantos_cartao(conexao, chave):
        return conexao.execute('SELECT COUNT(*) FROM lateral'
                               ' WHERE ativo=1 AND cartao=?', (chave,)).fetchone()[0]

    # A faixa de indicadores do layout tem cinco cartões. Estes são os cinco
    # números que a unidade realmente tem no banco — contador de módulo que
    # ainda não existe seria enfeite, e enfeite com cara de dado engana quem lê.
    # Cada indicador espelha um cartão: número, nome e ícone saem do próprio
    # cartão, não de rótulos fixos aqui. Com cartões genéricos não há mais
    # "escala" nem "chamado" para contar, e nome fixo sobre conteúdo livre
    # enganaria quem lê — trocar o ícone do cartão troca o do indicador junto.
    registrados = {c['chave']: c for c in cartoes_do_painel(so_ativos=True)}

    def icone_de(chave, padrao):
        cartao = registrados.get(chave)
        return cartao['icone'] if cartao else padrao

    numeros = [
        (quantos("SELECT COUNT(*) FROM links WHERE ativo=1 AND grupo='sistema'"),
         # Rótulo curto de propósito: o nome do cartão pode ser longo, e aqui
         # ele dividiria espaço com o número numa caixa estreita.
         'Sistemas', 'Disponíveis', icone_de('sistemas', 'grade'), 'azul'),
        (quantos('SELECT COUNT(*) FROM ramais WHERE ativo=1'),
         'Ramais', 'Cadastrados', icone_de('ramais', 'telefone'), 'verde'),
        (quantos('SELECT COUNT(*) FROM lateral WHERE ativo=1'),
         'Itens', 'Publicados', 'megafone', 'laranja'),
    ]
    # Só os cartões de lista têm item para contar. Sem o filtro, o primeiro do
    # registro é o de sistemas, que apareceria com zero.
    com_itens = [c for c in registrados.values() if c['tipo'] == 'itens']
    for c, tom in zip(com_itens[1:3], ('roxo', 'vermelho')):
        numeros.append((quantos_cartao(con, c['chave']), c['nome'],
                        'Itens visíveis', c['icone'], tom))

    sistemas_todos = con.execute(
        "SELECT * FROM links WHERE ativo=1 AND grupo='sistema'"
        ' ORDER BY ordem, id').fetchall()

    # A busca do cartão de ramais precisa alcançar a lista inteira, não só as
    # linhas em destaque — senão procura no que já está à vista. Os demais vão
    # para a página escondidos e aparecem quando casam com o que se digita.
    destaques = ramais_do_painel(con)
    em_destaque = {r['id'] for r in destaques}

    # Agrupados por região aqui, e não no template: assim o Jinja só percorre a
    # lista da região que está desenhando, em vez de filtrar a lista inteira
    # três vezes. Região desconhecida (banco antigo, valor editado à mão) cai
    # em "baixo" — some do lugar certo é melhor que sumir da página.
    # Os cinco cartoes do painel e os itens de cada um, agrupados por regiao.
    itens_por_cartao = {}
    for r in con.execute('SELECT * FROM lateral WHERE ativo=1 ORDER BY ordem, id'):
        itens_por_cartao.setdefault(r['cartao'], []).append(r)
    cartoes_painel = {chave: [] for chave in CARTAO_REGIOES}
    for c in cartoes_do_painel(so_ativos=True):
        regiao = c['regiao'] if c['regiao'] in CARTAO_REGIOES else 'baixo'
        cartoes_painel[regiao].append((c, itens_por_cartao.get(c['chave'], [])))
    for regiao in cartoes_painel:
        cartoes_painel[regiao].sort(key=lambda par: par[0]['ordem'])

    livre = layout_livre_ativo()
    cartoes_livre = []
    lateral_livre = {}
    if livre:
        _livre_converter(con)
        _lateral_garantir(con)
        lateral_livre = _lateral_posicoes(con)
        for c in cartoes_do_painel(so_ativos=True):
            cartoes_livre.append((c, itens_por_cartao.get(c['chave'], [])))
        cartoes_livre.sort(key=lambda par: (par[0]['gy'], par[0]['gx']))

    return render_template(
        'index.html', numeros=numeros, saudacao=saudacao(),
        noticias_recentes=modulos.noticias.recentes(modulos.noticias.vitrine()[2]),
        noticias_vitrine=modulos.noticias.vitrine(),
        cartoes_painel=cartoes_painel, livre=livre, cartoes_livre=cartoes_livre,
        lateral_livre=lateral_livre,
        destinos_links=destinos_de_links() if session.get('admin') else [],
        dados_conteudo=modulos.cartoes.dados_edicao() if session.get('admin') else {},
        cartoes_ocultos=modulos.cartoes.ocultos() if (session.get('admin') and livre) else [],
        sistemas=agrupar_por_categoria(sistemas_todos),
        sistemas_total=len(sistemas_todos),
        atalhos=con.execute("SELECT * FROM links WHERE ativo=1 AND grupo='atalho'"
                            ' ORDER BY ordem, id').fetchall(),
        reservas=con.execute("SELECT * FROM links WHERE ativo=1 AND grupo='reserva'"
                             ' ORDER BY ordem, id').fetchall(),
        chamados=con.execute('SELECT * FROM chamados WHERE ativo=1 ORDER BY ordem, id'
                             ).fetchall(),
        banners=con.execute('SELECT * FROM banners WHERE ativo=1 ORDER BY ordem, id').fetchall(),
        comunicados=con.execute('SELECT * FROM lateral WHERE ativo=1 ORDER BY ordem, id').fetchall(),
        escalas=con.execute('SELECT * FROM escalas WHERE ativo=1 ORDER BY ordem, id').fetchall(),
        aniversariantes=con.execute(
            'SELECT * FROM aniversariantes WHERE ativo=1 AND mes=? ORDER BY dia',
            (mes,)).fetchall(),
        ramais_destaque=destaques,
        ramais_extras=[r for r in con.execute(
            'SELECT * FROM ramais WHERE ativo=1 ORDER BY setor COLLATE NOCASE, id')
            if r['id'] not in em_destaque],
        ramais_total=con.execute(
            'SELECT COUNT(*) FROM ramais WHERE ativo=1').fetchone()[0],
        ramais_sem_destaque=not con.execute(
            'SELECT 1 FROM ramais WHERE ativo=1 AND destaque=1 LIMIT 1').fetchone(),
    )


# ── administração ──────────────────────────────────────────────────────────────

# Formatos de video que o navegador toca sozinho, sem plugin nem player
# externo — o portal e de rede interna e nao carrega nada de fora.
VIDEO_EXTS = {'.mp4', '.webm', '.ogg', '.ogv'}


def salva_upload(campo, atual='', exts=None):
    """Grava um arquivo enviado e devolve o nome final (ou o atual, se nada veio)."""
    arq = request.files.get(campo)
    if not arq or not arq.filename:
        # Imagem escolhida na biblioteca (campo "<campo>_biblioteca"): reaproveita
        # o arquivo já enviado em vez de gravar outra cópia.
        escolhida = os.path.basename(request.form.get(campo + '_biblioteca', '') or '')
        if (escolhida and not exts and modulos.midia.registrada(escolhida)
                and os.path.isfile(os.path.join(UPLOAD_DIR, escolhida))):
            return escolhida
        return atual
    ext = os.path.splitext(arq.filename)[1].lower()
    if ext not in (exts or EXT_OK):
        raise ValueError('Formato de vídeo não aceito. Use MP4, WEBM ou OGG.'
                         if exts else
                         'Formato não aceito. Use PNG, JPG, WEBP ou GIF.')
    if not modulos.seguranca.conteudo_confere(arq, ext):
        raise ValueError('O arquivo não é uma imagem ou vídeo válido: o conteúdo não '
                         'corresponde ao formato informado.')
    nome = f"{secrets.token_hex(8)}{ext}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    arq.save(os.path.join(UPLOAD_DIR, nome))
    modulos.midia.registrar_arquivo(nome, arq.filename,
                                    os.path.getsize(os.path.join(UPLOAD_DIR, nome)))
    return nome


def remove_upload(nome):
    if not nome:
        return
    # Imagem catalogada na biblioteca só sai por ela (e só se não estiver em uso):
    # outra página, banner ou notícia pode estar usando o mesmo arquivo.
    if modulos.midia.registrada(nome):
        return
    caminho = os.path.join(UPLOAD_DIR, secure_filename(nome))
    if os.path.isfile(caminho):
        try:
            os.remove(caminho)
        except OSError:
            pass


def _apaga_arquivos(nomes):
    """Remove os arquivos indicados de static/ — só um formato vale por vez."""
    for nome in nomes:
        caminho = os.path.join(STATIC_DIR, nome)
        if os.path.isfile(caminho):
            try:
                os.remove(caminho)
            except OSError:
                pass


def _troca_imagem_fixa(campo, base, nomes, exts):
    """Substitui static/<base>.<ext> pelo arquivo enviado no formulário.
    Devolve mensagem de erro ou None."""
    enviado = request.files.get(campo)
    if not enviado or not enviado.filename:
        return None
    ext = os.path.splitext(enviado.filename)[1].lower()
    if ext not in exts:
        return f"Formato não aceito para {campo}. Use {', '.join(sorted(exts))}."
    _apaga_arquivos(nomes)
    enviado.save(os.path.join(STATIC_DIR, base + ext))
    return None


def _int(valor, padrao=0):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


def reordenar(tabela):
    """Grava a nova ordem vinda do arrastar-e-soltar.

    Recebe os ids na sequência desejada e regrava a coluna `ordem` como
    0,1,2... — assim a ordem fica sempre normalizada, sem buracos nem empates.
    Responde 204 (sem conteúdo) porque a página não precisa recarregar.
    """
    ids = [int(x) for x in request.form.get('ids', '').split(',')
           if x.strip().lstrip('-').isdigit()]
    if not ids:
        return ('', 400)
    con = db()
    # Só reordena o que existe nesta tabela — ids forjados são ignorados.
    validos = {r['id'] for r in con.execute(f'SELECT id FROM {tabela}')}
    for posicao, ident in enumerate(i for i in ids if i in validos):
        con.execute(f'UPDATE {tabela} SET ordem=? WHERE id=?', (posicao, ident))
    con.commit()
    return ('', 204)


@app.route('/admin')
@admin_obrigatorio
def admin():
    con = db()
    return render_template('admin.html', total={
        'links':   con.execute('SELECT COUNT(*) c FROM links').fetchone()['c'],
        'banners': con.execute('SELECT COUNT(*) c FROM banners').fetchone()['c'],
        'lateral': con.execute('SELECT COUNT(*) c FROM lateral').fetchone()['c'],
        'ramais': con.execute('SELECT COUNT(*) c FROM ramais').fetchone()['c'],
        'usuarios': con.execute('SELECT COUNT(*) c FROM usuarios').fetchone()['c'],
    })


@app.route('/admin/links', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_links():
    con = db()
    if request.method == 'POST':
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))
        if acao == 'titulo_cartao':
            # 'sistema'/'atalho' são os grupos; os cartões chamam-se no plural.
            grupo = request.form.get('grupo', 'sistema')
            if grupo in GRUPOS_LINK:
                salvar_titulo_cartao({'sistema': 'sistemas',
                                      'atalho': 'atalhos'}[grupo])
            return redirect(url_for('admin_links', grupo=grupo))
        if acao == 'aparencia_cartao':
            grupo = request.form.get('grupo', 'sistema')
            if grupo in GRUPOS_LINK:
                salvar_aparencia_cartao({'sistema': 'sistemas',
                                         'atalho': 'atalhos'}[grupo])
            return redirect(url_for('admin_links', grupo=grupo))
        if acao == 'ordenar':
            return reordenar('links')
        if acao == 'importar':
            grupo = request.form.get('grupo_destino', 'sistema')
            if grupo not in ('sistema', 'atalho', 'reserva'):
                grupo = 'sistema'
            itens = interpretar_sistemas(request.form.get('lista', ''))
            if not itens:
                flash('Nenhuma linha reconhecida. Use uma linha por sistema, '
                      'no formato: SIGLA | Nome | endereço', 'erro')
            else:
                base = con.execute('SELECT COALESCE(MAX(ordem),-1)+1 o FROM links'
                                   ' WHERE grupo=?', (grupo,)).fetchone()['o']
                cores = ['#2563c9', '#2a8f8a', '#c9a227', '#4a5b68', '#6455a8', '#3a6d8c']
                simbolo = {'sistema': 'aplicativo', 'atalho': 'documento',
                           'reserva': 'calendario'}[grupo]
                for i, (sigla, nome, url) in enumerate(itens):
                    con.execute('INSERT INTO links (titulo,url,descricao,icone,simbolo,'
                                'cor,ordem,ativo,grupo) VALUES (?,?,?,?,?,?,?,1,?)',
                                (nome, url, '', sigla, simbolo, cores[i % len(cores)],
                                 base + i, grupo))
                flash(f'{len(itens)} itens importados.', 'ok')
            con.commit()
            return redirect(url_for('admin_links'))
        if acao == 'excluir':
            con.execute('DELETE FROM links WHERE id=?', (ident,))
            flash('Link removido.', 'ok')
        else:
            grupo = request.form.get('grupo', 'sistema')
            dados = (request.form.get('titulo', '').strip(),
                     request.form.get('url', '').strip(),
                     request.form.get('descricao', '').strip(),
                     request.form.get('icone', '').strip()[:5],
                     nome_icone(request.form.get('simbolo')),
                     request.form.get('categoria', '').strip(),
                     request.form.get('situacao', '').strip(),
                     request.form.get('cor', '#3a6d8c'),
                     _int(request.form.get('ordem')),
                     1 if request.form.get('ativo') else 0,
                     grupo if grupo in ('sistema', 'atalho', 'reserva') else 'sistema')
            # Só o título é obrigatório. O endereço fica para depois: monta-se
            # a fileira de botões primeiro e informa-se o link de cada um
            # conforme se descobre — em sistema interno o endereço muda de
            # unidade para unidade. Sem URL o botão aparece e não é link.
            if not dados[0]:
                flash('O título é obrigatório.', 'erro')
            elif ident:
                con.execute('UPDATE links SET titulo=?,url=?,descricao=?,icone=?,'
                            'simbolo=?,categoria=?,situacao=?,cor=?,ordem=?,ativo=?,'
                            'grupo=? WHERE id=?', dados + (ident,))
                flash('Link atualizado.', 'ok')
            else:
                con.execute('INSERT INTO links (titulo,url,descricao,icone,simbolo,'
                            'categoria,situacao,cor,ordem,ativo,grupo)'
                            ' VALUES (?,?,?,?,?,?,?,?,?,?,?)', dados)
                flash('Link adicionado.', 'ok')
        con.commit()
        return redirect(url_for('admin_links',
                                grupo=request.form.get('grupo')
                                or request.form.get('grupo_destino') or 'sistema'))

    editar = None
    if request.args.get('editar'):
        editar = con.execute('SELECT * FROM links WHERE id=?',
                             (_int(request.args['editar']),)).fetchone()
    # Cada grupo tem sua própria aba: antes atalhos e reservas ficavam
    # escondidos num seletor dentro do cadastro de sistemas.
    grupo = request.args.get('grupo', editar['grupo'] if editar else 'sistema')
    if grupo not in GRUPOS_LINK:
        grupo = 'sistema'
    return render_template(
        'admin_links.html', editar=editar, grupo=grupo, grupos=GRUPOS_LINK,
        abas=abas_links(grupo),
        cartao=dados_titulo_cartao({'sistema': 'sistemas',
                                    'atalho': 'atalhos'}[grupo]),
        nome_atual=nome_do_bloco({'sistema': 'sistemas',
                                  'atalho': 'atalhos'}[grupo], GRUPOS_LINK[grupo]),
        icones_cartao=dados_icone_cartao({'sistema': 'sistemas',
                                          'atalho': 'atalhos'}[grupo]),
        nome_bloco=nome_do_bloco({'sistema': 'sistemas',
                                  'atalho': 'atalhos'}[grupo], GRUPOS_LINK[grupo]),
        aparencia=dados_aparencia_cartao({'sistema': 'sistemas',
                                          'atalho': 'atalhos'}[grupo]),
        fontes=FONTES_TEXTO,
        # Alimenta o datalist do campo Categoria: reaproveitar o que já existe
        # evita "Segurança" e "Seguranca" virarem dois grupos.
        categorias=[r['categoria'] for r in con.execute(
            "SELECT DISTINCT categoria FROM links WHERE grupo='sistema'"
            " AND categoria<>'' ORDER BY categoria COLLATE NOCASE")],
        itens=con.execute('SELECT * FROM links WHERE grupo=? ORDER BY ordem, id',
                          (grupo,)).fetchall())


@app.route('/admin/banners', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_banners():
    con = db()
    if request.method == 'POST':
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))
        if acao == 'ordenar':
            return reordenar('banners')
        if acao == 'excluir':
            row = con.execute('SELECT arquivo FROM banners WHERE id=?',
                              (ident,)).fetchone()
            if row:
                remove_upload(row['arquivo'])
            con.execute('DELETE FROM banners WHERE id=?', (ident,))
            flash('Imagem removida.', 'ok')
        else:
            atual = ''
            if ident:
                row = con.execute('SELECT arquivo FROM banners WHERE id=?',
                                  (ident,)).fetchone()
                atual = row['arquivo'] if row else ''
            try:
                arquivo = salva_upload('imagem', atual)
            except ValueError as e:
                flash(str(e), 'erro')
                return redirect(url_for('admin_banners'))
            # Um slide é uma foto ou uma cor sólida. Marcar "usar cor" descarta
            # a imagem: guardar as duas deixaria a dúvida de qual manda.
            usar_cor = bool(request.form.get('usar_cor'))
            cor = cor_hexa(request.form.get('cor'), '') if usar_cor else ''
            if usar_cor and not cor:
                flash('Escolha uma cor válida.', 'erro')
                return redirect(url_for('admin_banners'))
            if usar_cor and arquivo:
                remove_upload(arquivo)
                arquivo = ''
            if not arquivo and not cor:
                flash('Escolha uma imagem ou marque "usar cor sólida".', 'erro')
                return redirect(url_for('admin_banners'))
            dados = (arquivo, cor,
                     request.form.get('titulo', '').strip(),
                     request.form.get('texto', '').strip(),
                     request.form.get('url', '').strip(),
                     posicao_capa(request.form.get('posicao')),
                     _int(request.form.get('ordem')),
                     1 if request.form.get('ativo') else 0)
            if ident:
                if atual and atual != arquivo:
                    remove_upload(atual)
                con.execute('UPDATE banners SET arquivo=?,cor=?,titulo=?,texto=?,'
                            'url=?,posicao=?,ordem=?,ativo=? WHERE id=?',
                            dados + (ident,))
                flash('Banner atualizado.', 'ok')
            else:
                con.execute('INSERT INTO banners (arquivo,cor,titulo,texto,url,'
                            'posicao,ordem,ativo) VALUES (?,?,?,?,?,?,?,?)', dados)
                flash('Banner adicionado.', 'ok')
        con.commit()
        return redirect(url_for('admin_banners'))

    editar = None
    if request.args.get('editar'):
        editar = con.execute('SELECT * FROM banners WHERE id=?',
                             (_int(request.args['editar']),)).fetchone()
    return render_template(
        'admin_banners.html', editar=editar,
        itens=con.execute('SELECT * FROM banners ORDER BY ordem, id').fetchall())


TIPOS_CARTAO = {
    'sistemas': 'Acesso rápido aos sistemas', 'atalhos': 'Atalhos úteis',
    'ramais': 'Ramais', 'noticias': 'Últimas notícias',
    'itens': 'Cartão de itens (comunicados)', 'conteudo': 'Cartão de texto e imagem',
}


def _editar_conteudo_cartao(c):
    """(rótulo, endereço) da tela que edita o que há DENTRO do cartão."""
    t, k = c['tipo'], c['chave']
    if t == 'sistemas':
        return 'Editar sistemas', url_for('admin_links', grupo='sistema')
    if t == 'atalhos':
        return 'Editar atalhos', url_for('admin_links', grupo='atalho')
    if t == 'ramais':
        return 'Editar ramais', url_for('admin_ramais')
    if t == 'noticias':
        return 'Editar notícias', url_for('conteudos', tipo='noticia')
    if t == 'conteudo':
        return 'Editar conteúdo', url_for('conteudos_editor', tipo='cartao', ident=k)
    return 'Editar itens', url_for('admin_lateral', cartao=k)


@app.route('/admin/cartoes', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_cartoes():
    """Todos os cartões do portal numa tela só: nome, conteúdo e aparência."""
    if request.method == 'POST':
        chave = request.form.get('cartao', '')
        if not cartao_por_chave(chave):
            abort(400)
        acao = request.form.get('acao')
        if acao == 'aparencia_cartao':
            salvar_aparencia_cartao(chave)
        elif acao == 'titulo_cartao':
            if (request.form.get('titulo_cartao') or '').strip():
                salvar_nome_cartao_painel(chave)
            else:
                flash('O nome do cartão não pode ficar em branco.', 'erro')
        return redirect(url_for('admin_cartoes') + '#c-' + chave)
    cartoes = []
    for c in cartoes_do_painel():
        rotulo, destino = _editar_conteudo_cartao(c)
        cartoes.append({'c': c, 'tipo': TIPOS_CARTAO.get(c['tipo'], c['tipo']),
                        'rotulo': rotulo, 'destino': destino,
                        'aparencia': dados_aparencia_cartao(c['chave'])})
    return render_template('admin_cartoes.html', cartoes=cartoes, fontes=FONTES_TEXTO,
                           regioes=CARTAO_REGIOES)


@app.route('/admin/lateral', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_lateral():
    con = db()
    if request.method == 'POST':
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))
        # Qual dos cinco cartoes esta sendo editado. Vem do formulario no POST
        # e da URL no GET; chave desconhecida cai no primeiro.
        chave = request.form.get('cartao') or ''
        if not cartao_por_chave(chave):
            chave = CARTOES_SEMENTE[0][0]
        volta = url_for('admin_lateral', cartao=chave)

        if acao == 'novo_cartao':
            nova = _proxima_chave_cartao(con)
            proxima_ordem = con.execute(
                'SELECT COALESCE(MAX(ordem),0)+1 FROM cartoes_painel').fetchone()[0]
            con.execute('INSERT INTO cartoes_painel (chave,nome,icone,regiao,'
                        'largura,coluna,ordem,tipo,ativo)'
                        " VALUES (?,?,'prancheta','baixo',1,0,?,'itens',1)",
                        (nova, 'Cartão ' + nova.replace('cartao', ''),
                         proxima_ordem))
            _semear_aparencia(con, nova)
            con.commit()
            flash('Cartão criado. Arraste-o no mapa para posicionar.', 'ok')
            return redirect(url_for('admin_lateral', cartao=nova))

        if acao == 'excluir_cartao':
            # O último não sai: sem nenhum cartão a tela não teria o que abrir.
            quantos = con.execute("SELECT COUNT(*) FROM cartoes_painel"
                                  " WHERE tipo='itens'").fetchone()[0]
            if quantos <= 1:
                flash('Este é o último cartão — crie outro antes de excluí-lo.',
                      'erro')
                return redirect(volta)
            for linha in con.execute('SELECT imagem, video FROM lateral'
                                     ' WHERE cartao=?', (chave,)):
                remove_upload(linha['imagem'])
                remove_upload(linha['video'])
            con.execute('DELETE FROM lateral WHERE cartao=?', (chave,))
            con.execute('DELETE FROM cartoes_painel WHERE chave=? AND '
                        "tipo='itens'", (chave,))
            con.commit()
            flash('Cartão e itens removidos.', 'ok')
            return redirect(url_for('admin_lateral'))

        if acao == 'titulo_cartao':
            salvar_nome_cartao_painel(chave)
            return redirect(volta)
        if acao == 'aparencia_cartao':
            salvar_aparencia_cartao(chave)
            return redirect(volta)
        if acao == 'ordenar':
            return reordenar('lateral')
        if acao == 'excluir':
            linha = con.execute('SELECT imagem, video FROM lateral WHERE id=?',
                                (ident,)).fetchone()
            # Arquivos enviados saem junto: item apagado deixaria orfao em
            # uploads/, ocupando espaco sem nada apontando para ele.
            if linha:
                remove_upload(linha['imagem'])
                remove_upload(linha['video'])
            con.execute('DELETE FROM lateral WHERE id=?', (ident,))
            flash('Item removido.', 'ok')
        else:
            urg  = request.form.get('urgencia', 'informacao')
            dest = request.form.get('destaque', 'nenhum')
            atuais = con.execute('SELECT imagem, video FROM lateral WHERE id=?',
                                 (ident,)).fetchone() if ident else None
            try:
                imagem = salva_upload('imagem', atuais['imagem'] if atuais else '')
                video = salva_upload('video', atuais['video'] if atuais else '',
                                     VIDEO_EXTS)
            except ValueError as e:
                flash(str(e), 'erro')
                return redirect(volta)
            for campo, novo, antigo in (('imagem', imagem, atuais['imagem'] if atuais else ''),
                                        ('video', video, atuais['video'] if atuais else '')):
                if novo != antigo:
                    remove_upload(antigo)
                if request.form.get('remover_' + campo):
                    remove_upload(novo)
                    if campo == 'imagem':
                        imagem = ''
                    else:
                        video = ''
            dados = (request.form.get('tipo', 'aviso'),
                     request.form.get('titulo', '').strip(),
                     # strip() inteiro comeria a indentacao da primeira linha:
                     # tira so as quebras das pontas e o espaco do fim.
                     request.form.get('conteudo', '').strip('\r\n').rstrip(),
                     request.form.get('url', '').strip(),
                     _int(request.form.get('ordem')),
                     1 if request.form.get('ativo') else 0,
                     urg if urg in ('urgente', 'comunicado', 'informacao') else 'informacao',
                     dest if dest in DESTAQUES_COMUNICADO else 'nenhum',
                     # Vazio quer dizer "usa o padrão de Aparência" — por isso
                     # o padrão dos validadores aqui é a string vazia.
                     medida(request.form.get('titulo_tam'), '', 0.6, 2.0)
                     if request.form.get('titulo_tam', '').strip() else '',
                     cor_hexa(request.form.get('titulo_cor'), ''),
                     medida(request.form.get('texto_tam'), '', 0.6, 2.0)
                     if request.form.get('texto_tam', '').strip() else '',
                     cor_hexa(request.form.get('texto_cor'), ''),
                     cor_hexa(request.form.get('fundo_cor'), ''),
                     request.form.get('data', '').strip(),
                     imagem, video,
                     request.form.get('url_rot', '').strip(),
                     (request.form.get('img_pos')
                      if request.form.get('img_pos') in CARTAO_IMG_POS else 'topo'),
                     chave)
            # O título é opcional (o nome do cartão já titula o bloco), mas o
            # item precisa ter algo para mostrar: texto, imagem, vídeo ou link.
            if not (dados[1] or dados[2] or dados[3] or imagem or video):
                flash('Preencha ao menos um destes: título, texto, link, '
                      'imagem ou vídeo.', 'erro')
            elif ident:
                con.execute('UPDATE lateral SET tipo=?,titulo=?,conteudo=?,url=?,'
                            'ordem=?,ativo=?,urgencia=?,destaque=?,titulo_tam=?,'
                            'titulo_cor=?,texto_tam=?,texto_cor=?,fundo_cor=?,'
                            'data=?,imagem=?,video=?,url_rot=?,img_pos=?,cartao=?'
                            ' WHERE id=?', dados + (ident,))
                flash('Item atualizado.', 'ok')
                volta = url_for('admin_lateral', cartao=chave, editar=ident)
            else:
                con.execute('INSERT INTO lateral (tipo,titulo,conteudo,url,ordem,'
                            'ativo,urgencia,destaque,titulo_tam,titulo_cor,'
                            'texto_tam,texto_cor,fundo_cor,data,imagem,video,'
                            'url_rot,img_pos,cartao)'
                            ' VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', dados)
                flash('Item adicionado.', 'ok')
        con.commit()
        return redirect(volta)

    chave = request.args.get('cartao') or ''
    if not cartao_por_chave(chave):
        chave = CARTOES_SEMENTE[0][0]
    # Itens (comunicados) são editados no editor único de Conteúdos.
    if request.args.get('editar'):
        return redirect(url_for('conteudos_editor', tipo='comunicado',
                                ident=_int(request.args['editar'])))
    if request.args.get('novo'):
        return redirect(url_for('conteudos_editor', tipo='comunicado', ident='novo', cartao=chave))
    editar = None
    return render_template(
        'admin_lateral.html', editar=editar, destaques=DESTAQUES_COMUNICADO,
        paleta=PALETA, paleta_fundo=PALETA_FUNDO,
        abas=abas_painel(chave), fontes=FONTES_TEXTO,
        cartao_atual=cartao_por_chave(chave),
        icones_cartao=dados_icone_cartao(chave), img_pos=CARTAO_IMG_POS,
        aparencia=dados_aparencia_cartao(chave),
        itens=con.execute('SELECT * FROM lateral WHERE cartao=?'
                          ' ORDER BY ordem, id', (chave,)).fetchall())


@app.route('/admin/imagem-tamanho/<int:item>', methods=['POST'])
@admin_obrigatorio
def admin_imagem_tamanho(item):
    """Grava o tamanho e a posição que o administrador deu à imagem de um item,
    arrastando a borda dela (tamanho) ou a imagem inteira (posição) no painel.

    `larg`: 0 volta ao padrão; o resto fica entre 10 e 100 (% da largura do
    texto do item). `x`: 0 a 100, onde a imagem fica na horizontal (50 = centro).
    Cada campo só é gravado se vier no pedido."""
    vals = {}
    if 'larg' in request.form:
        larg = _int(request.form.get('larg'))
        larg = 0 if larg <= 0 else max(10, min(100, larg))
        vals['img_larg'] = larg
        if larg == 0:                 # voltar ao padrão também recentraliza
            vals['img_x'] = 0
    if 'x' in request.form and vals.get('img_larg', 1) != 0:
        vals['img_x'] = max(0, min(100, _int(request.form.get('x'))))
    if not vals:
        abort(400)
    con = db()
    cur = con.execute('UPDATE lateral SET '
                      + ','.join(c + '=?' for c in vals) + ' WHERE id=?',
                      tuple(vals.values()) + (item,))
    con.commit()
    if not cur.rowcount:
        abort(404)
    return jsonify(ok=True)


# ── layout livre ───────────────────────────────────────────────────────────────
# Um quadro único de 12 colunas, com linhas de 1,5rem. Cada cartão guarda onde
# começa (gx, gy) e quanto ocupa (gw, gh), em células. A grade garante o
# alinhamento; o administrador arrasta na própria página (static/livre.js).
LIVRE_COLUNAS = 12
LIVRE_ALT_MIN = 4
LIVRE_ALT_MAX = 200


def layout_livre_ativo():
    return cfg('layout_livre') == '1'


# A lista de páginas e o cartão "Em destaque" (a barra lateral) também são
# cartões do quadro livre. Não são linhas de `cartoes_painel`; a posição de
# cada um fica em `config` como "gx,gy,gw,gh".
LATERAL_LIVRE = {'paginas': 'livre_pos_paginas', 'destaque': 'livre_pos_destaque'}
LATERAL_COLUNAS = 3          # largura inicial da barra, em colunas do quadro


def _lateral_posicoes(con):
    """Posição dos cartões da barra lateral no quadro livre ({chave: dict})."""
    saida = {}
    for chave, k in LATERAL_LIVRE.items():
        r = con.execute('SELECT valor FROM config WHERE chave=?', (k,)).fetchone()
        try:
            gx, gy, gw, gh = [int(x) for x in (r['valor'] if r else '').split(',')]
        except ValueError:
            continue
        saida[chave] = {'chave': chave, 'gx': gx, 'gy': gy, 'gw': gw, 'gh': gh}
    return saida


def lateral_desenhada(chave):
    """A lista de páginas só ocupa o quadro quando está ligada em Navegação.
    O cartão "Em destaque" aparece sempre no editor (desligado, com o convite
    para ligar). Um cartão que não é desenhado não pode bloquear o espaço dele."""
    if chave == 'paginas':
        return cfg('lista_paginas_ativa') == '1'
    return True


def _lateral_gravar(con, chave, gx, gy, gw, gh):
    con.execute('INSERT INTO config (chave,valor) VALUES (?,?) '
                'ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                (LATERAL_LIVRE[chave], f'{gx},{gy},{gw},{gh}'))


def _lateral_garantir(con):
    """Dá lugar à barra lateral no quadro, uma única vez.

    Os cartões que já existem são espremidos para as colunas da direita (as
    fronteiras são arredondadas juntas, então nada passa a se sobrepor) e a
    barra ocupa as colunas da esquerda."""
    if con.execute("SELECT 1 FROM config WHERE chave='livre_lateral'").fetchone() \
            and len(_lateral_posicoes(con)) == len(LATERAL_LIVRE):
        return
    n = LATERAL_COLUNAS
    util = LIVRE_COLUNAS - n
    for c in con.execute('SELECT chave,gx,gw FROM cartoes_painel WHERE gw>0').fetchall():
        x0 = round(c['gx'] * util / LIVRE_COLUNAS)
        x1 = max(x0 + 1, round((c['gx'] + c['gw']) * util / LIVRE_COLUNAS))
        con.execute('UPDATE cartoes_painel SET gx=?,gw=? WHERE chave=?',
                    (n + x0, x1 - x0, c['chave']))
    _lateral_gravar(con, 'paginas', 0, 0, n, 16)
    _lateral_gravar(con, 'destaque', 0, 16, n, 9)
    con.execute("INSERT OR REPLACE INTO config (chave,valor) VALUES ('livre_lateral','1')")
    con.commit()


def _livre_converter(con, so_sem_posicao=True):
    """Dá posição no quadro livre a partir das regiões e colunas de hoje.

    Cada região é empilhada abaixo da anterior; dentro dela, o cartão desce até
    onde a sua faixa de colunas está livre. É uma aproximação do que o
    navegador fazia — o administrador ajusta o resto arrastando."""
    todos = [dict(r) for r in con.execute(
        'SELECT * FROM cartoes_painel WHERE ativo=1 ORDER BY ordem, id')]
    if so_sem_posicao and all(c['gw'] > 0 for c in todos):
        return
    topo = [0] * LIVRE_COLUNAS
    # Primeira vez (ninguém tem posição ainda): parte das colunas de hoje.
    if so_sem_posicao and any(c['gw'] > 0 for c in todos):
        # Só os que faltam: entram no fim, sem mexer nos que já têm lugar.
        for c in todos:
            if c['gw'] > 0:
                for i in range(c['gx'], min(LIVRE_COLUNAS, c['gx'] + c['gw'])):
                    topo[i] = max(topo[i], c['gy'] + c['gh'])
        for p in _lateral_posicoes(con).values():
            for i in range(p['gx'], min(LIVRE_COLUNAS, p['gx'] + p['gw'])):
                topo[i] = max(topo[i], p['gy'] + p['gh'])
        base = max(topo)
        for c in todos:
            if c['gw'] > 0:
                continue
            w = 4
            h = 10 * ((c['altura'] or 0) + 1)
            y = base
            con.execute('UPDATE cartoes_painel SET gx=0,gy=?,gw=?,gh=? WHERE chave=?',
                        (y, w, h, c['chave']))
            base = y + h
        con.commit()
        return
    inicio = 0
    for regiao, colunas in COLUNAS_POR_REGIAO.items():
        grupo = [c for c in todos
                 if (c['regiao'] if c['regiao'] in COLUNAS_POR_REGIAO else 'baixo') == regiao]
        if not grupo:
            continue
        distribuir_em_colunas(grupo, colunas)
        larg_col = LIVRE_COLUNAS // colunas
        altura = [inicio] * LIVRE_COLUNAS
        for c in grupo:
            n = min(c['largura'] or 1, colunas)
            x = (c['coluna_efetiva'] - 1) * larg_col
            w = n * larg_col
            x = min(x, LIVRE_COLUNAS - w)
            h = 10 * ((c['altura'] or 0) + 1)
            y = max(altura[x:x + w])
            for i in range(x, x + w):
                altura[i] = y + h
            con.execute('UPDATE cartoes_painel SET gx=?,gy=?,gw=?,gh=? WHERE chave=?',
                        (x, y, w, h, c['chave']))
        inicio = max(altura)
    con.commit()


def _livre_sobrepoe(a, b):
    return (a['gx'] < b['gx'] + b['gw'] and b['gx'] < a['gx'] + a['gw']
            and a['gy'] < b['gy'] + b['gh'] and b['gy'] < a['gy'] + a['gh'])


@app.route('/admin/layout-livre', methods=['POST'])
@admin_obrigatorio
def admin_layout_livre():
    """Liga/desliga o layout livre; `refazer` recalcula tudo a partir das colunas."""
    con = db()
    acao = request.form.get('acao')
    if acao in ('ativar', 'refazer'):
        _livre_converter(con, so_sem_posicao=(acao == 'ativar'))
        if acao == 'refazer':
            con.execute("DELETE FROM config WHERE chave='livre_lateral'")
        valor = '1'
    elif acao == 'desativar':
        valor = '0'
    else:
        abort(400)
    con.execute('INSERT INTO config (chave,valor) VALUES (?,?) '
                'ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                ('layout_livre', valor))
    con.commit()
    if request.form.get('json'):
        return jsonify(ok=True)
    if valor == '1':
        flash('Layout livre ativado. Use "Editar layout" para arrastar.', 'ok')
        return redirect(url_for('editor'))
    flash('Voltou ao layout em colunas.', 'ok')
    return redirect(url_for('admin_mapa'))


@app.route('/admin/cartao-pos', methods=['POST'])
@admin_obrigatorio
def admin_cartao_pos():
    """Salva a posição de um ou mais cartões no quadro livre.

    Confere tudo junto antes de gravar: dentro do quadro, tamanho razoável e
    sem sobrepor outro cartão. Se algo falha, nada é gravado."""
    con = db()
    try:
        lista = json.loads(request.form.get('posicoes') or '[]')
    except ValueError:
        abort(400)
    if not isinstance(lista, list) or not lista:
        abort(400)
    cartoes = {r['chave']: dict(r) for r in con.execute(
        'SELECT * FROM cartoes_painel WHERE ativo=1')}
    cartoes.update({k: v for k, v in _lateral_posicoes(con).items()
                    if lateral_desenhada(k)})
    novos = {}
    for p in lista:
        chave = str(p.get('chave', ''))
        if chave not in cartoes:
            abort(404)
        gx, gy = _int(p.get('gx')), _int(p.get('gy'))
        gw, gh = _int(p.get('gw')), _int(p.get('gh'))
        if not (0 <= gx and 1 <= gw and gx + gw <= LIVRE_COLUNAS
                and 0 <= gy <= 10000 and LIVRE_ALT_MIN <= gh <= LIVRE_ALT_MAX):
            return jsonify(ok=False, erro='Posição fora do quadro.'), 400
        cartoes[chave].update(gx=gx, gy=gy, gw=gw, gh=gh)
        novos[chave] = (gx, gy, gw, gh)
    # Sobrepor é permitido (o administrador aproxima os cartões como quiser).
    # O cartão mexido vai para a frente: z = maior z atual + 1.
    for chave, v in novos.items():
        if chave in LATERAL_LIVRE:
            _lateral_gravar(con, chave, *v)
        else:
            con.execute('UPDATE cartoes_painel SET gx=?,gy=?,gw=?,gh=?,'
                        'z=(SELECT COALESCE(MAX(z),0)+1 FROM cartoes_painel) WHERE chave=?',
                        v + (chave,))
    con.commit()
    return jsonify(ok=True)


@app.route('/admin/mapa', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_mapa():
    """Onde cada cartão fica no painel, arrastando em vez de por seletores.

    Os dois cadastros aparecem juntos — os cartões do painel e os livres —,
    porque a grade é a mesma: mostrar só metade deles faria alguém arrastar um
    cartão para uma coluna que já está ocupada por outro, invisível aqui.
    """
    con = db()
    if request.method == 'POST':
        try:
            posicoes = json.loads(request.form.get('posicoes') or '[]')
        except ValueError:
            flash('Não consegui ler o layout enviado.', 'erro')
            return redirect(url_for('admin_mapa'))
        for p in posicoes if isinstance(posicoes, list) else []:
            ref = str(p.get('ref', ''))
            tabela, _, chave = ref.partition(':')
            if tabela != 'painel' or not chave:
                continue
            regiao = p.get('regiao')
            coluna = _int(p.get('coluna'))
            largura = _int(p.get('largura'), 1)
            altura = _int(p.get('altura'))
            dados = (regiao if regiao in CARTAO_REGIOES else 'baixo',
                     coluna if coluna in CARTAO_COLUNAS else 0,
                     largura if largura in CARTAO_LARGURAS else 1,
                     altura if altura in CARTAO_ALTURAS else 0,
                     _int(p.get('ordem')))
            con.execute('UPDATE cartoes_painel SET regiao=?,coluna=?,'
                        'largura=?,altura=?,ordem=? WHERE chave=?',
                        dados + (chave,))
        con.commit()
        flash('Layout salvo.', 'ok')
        return redirect(url_for('admin_mapa'))

    cartoes = []
    for c in con.execute('SELECT * FROM cartoes_painel ORDER BY ordem, id'):
        quantos = con.execute('SELECT COUNT(*) FROM lateral WHERE cartao=?',
                              (c['chave'],)).fetchone()[0]
        cartoes.append({
            'ref': 'painel:' + c['chave'], 'nome': c['nome'], 'icone': c['icone'],
            'regiao': c['regiao'], 'largura': c['largura'], 'coluna': c['coluna'],
            'altura': c['altura'] or 0,
            'descricao': ('conteúdo próprio' if c['tipo'] != 'itens'
                          else f'{quantos} item(ns)'),
            'oculto': not c['ativo']})

    for c in cartoes:
        if c['regiao'] not in CARTAO_REGIOES:
            c['regiao'] = 'baixo'
    for regiao, colunas in COLUNAS_POR_REGIAO.items():
        distribuir_em_colunas([c for c in cartoes if c['regiao'] == regiao], colunas)
    return render_template('admin_mapa.html', cartoes=cartoes,
                           regioes=CARTAO_REGIOES, colunas=COLUNAS_POR_REGIAO,
                           alturas=CARTAO_ALTURAS)


# Listas do painel que têm a caixa "visível": chave enviada pela tela -> (tabela,
# coluna que dá nome ao item no histórico). Lista fechada: o nome da tabela nunca
# vem do navegador, só a chave.
LISTAS_VISIVEL = {
    'menu':            ('paginas_lateral', 'nome'),
    'links':           ('links', 'titulo'),
    'lateral':         ('lateral', 'titulo'),
    'banners':         ('banners', 'titulo'),
    'ramais':          ('ramais', 'setor'),
    'escalas':         ('escalas', 'turno'),
    'aniversariantes': ('aniversariantes', 'nome'),
    'chamados':        ('chamados', 'titulo'),
}


@app.route('/admin/visivel', methods=['POST'])
@admin_obrigatorio
def admin_visivel():
    """Liga ou desliga "visível" de um item da lista, sem abrir o formulário de
    edição. Responde em JSON; o CSRF e o login já foram conferidos."""
    lista = LISTAS_VISIVEL.get(request.form.get('lista', ''))
    ident = _int(request.form.get('id'))
    if not lista or not ident:
        return jsonify(ok=False, erro='Item inválido.'), 400
    tabela, coluna_nome = lista
    con = db()
    linha = con.execute(f'SELECT {coluna_nome} AS nome FROM {tabela} WHERE id=?',
                        (ident,)).fetchone()
    if not linha:
        return jsonify(ok=False, erro='Este item não existe mais. Atualize a página.'), 404
    valor = 1 if request.form.get('valor') == '1' else 0
    con.execute(f'UPDATE {tabela} SET ativo=? WHERE id=?', (valor, ident))
    con.commit()
    modulos.auditoria.registrar(
        'visibilidade', request.form.get('lista', ''),
        f"id={ident} · {(str(linha['nome'] or '')).strip()[:120]} · "
        + ('visível' if valor else 'oculto'))
    return jsonify(ok=True, ativo=bool(valor))


@app.route('/admin/ramais', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_ramais():
    con = db()
    if request.method == 'POST':
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))

        if acao == 'titulo_cartao':
            salvar_titulo_cartao('ramais')
            return redirect(url_for('admin_ramais'))

        if acao == 'aparencia_cartao':
            salvar_aparencia_cartao('ramais')
            return redirect(url_for('admin_ramais'))

        if acao == 'destaque':
            # Caixa de seleção da lista: grava na hora, sem abrir o ramal.
            con.execute('UPDATE ramais SET destaque=? WHERE id=?',
                        (1 if request.form.get('valor') == '1' else 0, ident))
            con.commit()
            return jsonify(ok=True, total=con.execute(
                'SELECT COUNT(*) FROM ramais WHERE destaque=1 AND ativo=1').fetchone()[0])

        if acao == 'excluir':
            con.execute('DELETE FROM ramais WHERE id=?', (ident,))
            flash('Ramal removido.', 'ok')

        elif acao == 'importar':
            itens = interpretar_ramais(request.form.get('lista', ''))
            if not itens:
                flash('Nenhuma linha reconhecida. Cada linha precisa ter o setor '
                      'e o número, por exemplo: ALMOXARIFADO   245 / 253', 'erro')
            else:
                if request.form.get('substituir'):
                    con.execute('DELETE FROM ramais')
                con.executemany('INSERT INTO ramais (setor,numeros) VALUES (?,?)',
                                itens)
                flash(f'{len(itens)} ramais importados.', 'ok')

        else:
            setor = request.form.get('setor', '').strip()
            numeros = request.form.get('numeros', '').strip()
            ativo = 1 if request.form.get('ativo') else 0
            destaque = 1 if request.form.get('destaque') else 0
            if not setor or not numeros:
                flash('Informe o setor e o número.', 'erro')
            elif ident:
                con.execute('UPDATE ramais SET setor=?,numeros=?,ativo=?,destaque=?'
                            ' WHERE id=?', (setor, numeros, ativo, destaque, ident))
                flash('Ramal atualizado.', 'ok')
            else:
                con.execute('INSERT INTO ramais (setor,numeros,ativo,destaque)'
                            ' VALUES (?,?,?,?)', (setor, numeros, ativo, destaque))
                flash('Ramal adicionado.', 'ok')
        con.commit()
        return redirect(url_for('admin_ramais'))

    editar = None
    if request.args.get('editar'):
        editar = con.execute('SELECT * FROM ramais WHERE id=?',
                             (_int(request.args['editar']),)).fetchone()
    return render_template(
        'admin_ramais.html', editar=editar,
        cartao=dados_titulo_cartao('ramais'),
        nome_atual=nome_do_bloco('ramais', 'Ramais mais utilizados'),
        icones_cartao=dados_icone_cartao('ramais'),
        aparencia=dados_aparencia_cartao('ramais'), fontes=FONTES_TEXTO,
        itens=con.execute('SELECT * FROM ramais ORDER BY setor COLLATE NOCASE, id'
                          ).fetchall())


@app.route('/admin/usuarios', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_usuarios():
    con = db()
    if request.method == 'POST':
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))
        if acao == 'excluir':
            if ident == session['uid']:
                flash('Você não pode excluir o próprio usuário.', 'erro')
            elif con.execute('SELECT COUNT(*) c FROM usuarios WHERE admin=1'
                             ).fetchone()['c'] <= 1 and con.execute(
                    'SELECT admin FROM usuarios WHERE id=?', (ident,)
                    ).fetchone()['admin']:
                flash('Precisa existir ao menos um administrador.', 'erro')
            else:
                con.execute('DELETE FROM usuarios WHERE id=?', (ident,))
                flash('Usuário removido.', 'ok')
        else:
            usuario = (request.form.get('usuario') or '').strip().lower()
            nome    = (request.form.get('nome') or '').strip()
            senha   = request.form.get('senha') or ''
            admin_f = 1 if request.form.get('admin') else 0
            ativo   = 1 if request.form.get('ativo') else 0
            if not re.fullmatch(r'[a-z0-9._-]{3,32}', usuario):
                flash('Usuário: 3 a 32 caracteres (letras, números, . _ -).', 'erro')
            elif not nome:
                flash('Informe o nome.', 'erro')
            elif ident:
                if senha and len(senha) < 6:
                    flash('A senha precisa ter ao menos 6 caracteres.', 'erro')
                else:
                    # Nunca remover o último administrador ativo
                    if not admin_f and con.execute(
                            'SELECT admin FROM usuarios WHERE id=?', (ident,)
                            ).fetchone()['admin'] and con.execute(
                            'SELECT COUNT(*) c FROM usuarios WHERE admin=1'
                            ).fetchone()['c'] <= 1:
                        flash('Precisa existir ao menos um administrador.', 'erro')
                    else:
                        con.execute('UPDATE usuarios SET usuario=?,nome=?,admin=?,'
                                    'ativo=? WHERE id=?',
                                    (usuario, nome, admin_f, ativo, ident))
                        if senha:
                            con.execute('UPDATE usuarios SET senha_hash=? WHERE id=?',
                                        (generate_password_hash(senha), ident))
                        flash('Usuário atualizado.', 'ok')
            elif len(senha) < 6:
                flash('A senha precisa ter ao menos 6 caracteres.', 'erro')
            else:
                try:
                    con.execute('INSERT INTO usuarios (usuario,nome,senha_hash,'
                                'admin,ativo) VALUES (?,?,?,?,?)',
                                (usuario, nome, generate_password_hash(senha),
                                 admin_f, ativo))
                    flash('Usuário criado.', 'ok')
                except sqlite3.IntegrityError:
                    flash('Já existe um usuário com esse login.', 'erro')
        con.commit()
        return redirect(url_for('admin_usuarios'))

    editar = None
    if request.args.get('editar'):
        editar = con.execute('SELECT * FROM usuarios WHERE id=?',
                             (_int(request.args['editar']),)).fetchone()
    return render_template(
        'admin_usuarios.html', editar=editar,
        itens=con.execute('SELECT * FROM usuarios ORDER BY usuario').fetchall())


# ── blocos do painel: escalas, aniversariantes, menu e chamados ───────────────

# Cada bloco é uma tabela simples com os mesmos verbos (incluir, editar,
# excluir). Descrever os campos aqui evita repetir três rotinas quase iguais.
BLOCOS = {
    'escalas': {
        'titulo': 'Escalas de hoje',
        'campos': ['turno', 'equipe', 'horario', 'efetivo', 'ordem'],
        'obrigatorios': ['turno'],
        'ordem': 'ordem, id',
    },
    'aniversariantes': {
        'titulo': 'Aniversariantes',
        'campos': ['nome', 'dia', 'mes', 'cargo'],
        'obrigatorios': ['nome', 'dia', 'mes'],
        'ordem': 'mes, dia',
    },
    'menu': {
        'titulo': 'Menu lateral',
        'tabela': 'paginas_lateral',
        'campos': ['nome', 'icone', 'url', 'ordem'],
        'obrigatorios': ['nome'],
        'ordem': 'ordem, id',
        # O menu não é um cartão do painel: é a barra da esquerda. Fica com
        # "Sistemas e atalhos", que é onde se cuida de para onde as coisas
        # levam. `secao` tira ele da barra de abas de "Blocos do painel".
        'secao': 'links',
    },
    'chamados': {
        'titulo': 'Chamados de TI',
        'campos': ['numero', 'titulo', 'situacao', 'data', 'ordem'],
        'obrigatorios': ['numero', 'titulo'],
        'ordem': 'ordem, id',
    },
    'reservas': {
        'titulo': 'Reservas rápidas',
        'tabela': 'links',
        # `simbolo` é o ícone da reserva no painel. Entra aqui porque esta
        # passou a ser a única tela que edita reservas.
        'campos': ['titulo', 'descricao', 'situacao', 'simbolo', 'url', 'ordem'],
        'obrigatorios': ['titulo'],
        'ordem': 'ordem, id',
        # Reservas dividem a tabela `links` com sistemas e atalhos. Sem o filtro
        # a aba listaria os três juntos; sem os fixos, uma reserva nova nasceria
        # como sistema e apareceria no cartão errado.
        'filtro': ('grupo=?', ('reserva',)),
        'fixos': {'grupo': 'reserva'},
    },
}
NUMERICOS = {'ordem', 'dia', 'mes'}
# Campos que guardam nome de ícone. São dois nomes de coluna para a mesma
# coisa: o menu usa `icone`; as reservas, `simbolo` — em `links`, `icone` é a
# sigla que aparece no botão, não um ícone.
ICONICOS = {'icone', 'simbolo'}


def salvar_aparencia_cartao(chave_cartao):
    """Grava, na tela do próprio cartão, a aparência que só a ele diz respeito.

    As regras de validação são as mesmas de Aparência — tamanho preso à faixa
    do campo, cor só em hexadecimal, fonte só da lista fechada. O que mudou foi
    o lugar onde se edita, não o que é aceito.
    """
    con = db()
    pref = prefixo_aparencia(chave_cartao)
    if not pref:
        return
    for campo, faixa in campos_aparencia(chave_cartao):
        bruto = request.form.get(campo)
        padrao = padrao_aparencia(pref, campo)
        if campo.endswith('_tam'):
            valor = medida(bruto, padrao, *faixa)
        elif campo.endswith('_cor'):
            valor = cor_hexa(bruto, padrao)
        else:
            valor = bruto if bruto in FONTES_TEXTO else padrao
        con.execute('INSERT INTO config (chave,valor) VALUES (?,?) '
                    'ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                    (campo, valor))
    con.commit()
    flash('Aparência salva.', 'ok')


def dados_icone_cartao(chave):
    """(marcado, próprios, prefixo, todos) para o seletor de ícone.

    Vai por parâmetro ao macro porque `campos.html` é importado sem contexto:
    ali dentro nem o catálogo de ícones nem `ic` estariam visíveis."""
    registrado = cartao_por_chave(chave)
    if not registrado:
        return None
    return (nome_icone(registrado['icone']), icones_enviados(), ICONE_ARQ,
            sorted(ICONES))


def dados_titulo_cartao(chave):
    """(chave, nome padrão) para a tela desenhar o campo de nome do cartão.

    Chave sem cartão correspondente — o menu lateral é o caso — devolve None, e
    a tela simplesmente não mostra o campo.
    """
    padroes = dict(TITULOS_CARTAO)
    return (chave, padroes[chave]) if chave in padroes else (None, '')


def cartoes_do_painel(so_ativos=False):
    """Os cartões da página inicial, na ordem em que aparecem."""
    extra = ' WHERE ativo=1' if so_ativos else ''
    return db().execute('SELECT * FROM cartoes_painel' + extra +
                        ' ORDER BY ordem, id').fetchall()


def cartao_por_chave(chave):
    return db().execute('SELECT * FROM cartoes_painel WHERE chave=?',
                        (chave,)).fetchone()


def salvar_nome_cartao_painel(chave):
    """Nome do cartão do painel. Em branco volta ao nome de fábrica."""
    # Os dois conjuntos: os cartões genéricos e os três de conteúdo próprio.
    nomes = dict((c, n) for c, n, *_ in CARTOES_SEMENTE + CARTOES_FIXOS)
    padrao = nomes.get(chave, chave)
    nome = (request.form.get('titulo_cartao') or '').strip() or padrao
    con = db()
    # O ícone vem no mesmo formulário; ausente (tela sem seletor), fica como está.
    if 'icone_cartao' in request.form:
        con.execute('UPDATE cartoes_painel SET nome=?, icone=? WHERE chave=?',
                    (nome, nome_icone(request.form['icone_cartao']), chave))
    else:
        con.execute('UPDATE cartoes_painel SET nome=? WHERE chave=?', (nome, chave))
    con.commit()
    flash('Cartão salvo.', 'ok')


def salvar_titulo_cartao(chave):
    if cartao_por_chave(chave):
        return salvar_nome_cartao_painel(chave)
    """Grava o nome do cartão do bloco, vindo do formulário da própria tela.

    O nome mora em `config`, como antes; o que mudou é onde se edita. Ficava
    tudo junto em Aparência, numa fileira de oito campos — para renomear um
    bloco era preciso sair dele, achar o campo certo e voltar.
    """
    padrao = dict(TITULOS_CARTAO)[chave]
    # Em branco volta ao padrão: cartão sem cabeçalho não ajuda ninguém, e é
    # fácil apagar sem querer.
    valor = (request.form.get('titulo_cartao') or '').strip() or padrao
    con = db()
    con.execute('INSERT INTO config (chave,valor) VALUES (?,?) '
                'ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                (f'titulo_{chave}', valor))
    con.commit()
    flash('Nome do cartão salvo.', 'ok')


def abas_painel(atual):
    """Barra de abas de "Blocos do painel": (rótulo, endereço, ativa).

    Comunicados aparecem aqui, junto dos outros cartões, mas continuam sendo
    editados pela tela própria: só ela desenha urgência, destaque e as cores de
    cada comunicado, que o formulário genérico de blocos não conhece. Um único
    editor, listado no lugar onde se procura o conteúdo dos cartões.
    """
    # Só os cartões genéricos. Sistemas, Atalhos e Ramais estão no mesmo
    # registro por causa da posição, mas o conteúdo deles vem de outro cadastro
    # e cada um tem tela própria — uma aba aqui abriria uma lista que nunca
    # terá item, e duplicaria o que já existe noutra seção.
    return [(c['nome'], url_for('admin_lateral', cartao=c['chave']),
             c['chave'] == atual)
            for c in cartoes_do_painel() if c['tipo'] == 'itens']


def _filtro(info):
    """(cláusula, valores) do bloco — vazia quando ele tem tabela só sua.

    Vale em toda consulta, não só na listagem: sem ela, um id forjado no
    formulário editaria ou apagaria um sistema pela aba de reservas, já que as
    três coisas moram na mesma tabela.
    """
    clausula, valores = info.get('filtro', ('', ()))
    return clausula, list(valores)


@app.route('/admin/painel', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_painel():
    con = db()
    if request.method == 'POST':
        bloco = request.form.get('bloco', '')
        if bloco not in BLOCOS:
            abort(400)
        info = BLOCOS[bloco]
        tabela = info.get('tabela', bloco)
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))

        clausula, filtrados = _filtro(info)
        e_mais = f' AND {clausula}' if clausula else ''

        if acao == 'titulo_cartao' and bloco in dict(TITULOS_CARTAO):
            salvar_titulo_cartao(bloco)
            return redirect(url_for('admin_painel', bloco=bloco))
        if acao == 'aparencia_cartao' and bloco in CARTAO_APARENCIA:
            salvar_aparencia_cartao(bloco)
            return redirect(url_for('admin_painel', bloco=bloco))
        if acao == 'ordenar':
            return reordenar(tabela)
        if acao == 'excluir':
            if tabela == 'paginas_lateral':
                # O conteúdo da página (textos e imagens) sai junto com o item;
                # senão ficaria órfão, ocupando espaço em uploads/.
                morto = con.execute('SELECT chave, capa FROM paginas_lateral WHERE id=?',
                                    (ident,)).fetchone()
                if morto:
                    remove_upload(morto['capa'])    # a foto de capa também
                    for b in con.execute('SELECT arquivo FROM pagina_blocos'
                                         ' WHERE chave=?', (morto['chave'],)):
                        remove_upload(b['arquivo'])
                    con.execute('DELETE FROM pagina_blocos WHERE chave=?',
                                (morto['chave'],))
            con.execute(f'DELETE FROM {tabela} WHERE id=?{e_mais}',
                        [ident] + filtrados)
            flash('Item removido.', 'ok')
        else:
            valores, faltando = [], []
            for campo in info['campos']:
                bruto = (request.form.get(campo) or '').strip()
                if campo in info['obrigatorios'] and not bruto:
                    faltando.append(campo)
                if campo in NUMERICOS:
                    valores.append(_int(bruto))
                elif campo in ICONICOS:
                    # Nome de ícone forjado desenharia nada; `nome_icone` cai no
                    # genérico e ainda traduz o emoji das instalações antigas.
                    valores.append(nome_icone(bruto))
                else:
                    valores.append(bruto)
            if faltando:
                flash('Preencha: ' + ', '.join(faltando) + '.', 'erro')
            else:
                valores.append(1 if request.form.get('ativo') else 0)
                colunas = info['campos'] + ['ativo']
                if ident:
                    atrib = ','.join(f'{c}=?' for c in colunas)
                    con.execute(f'UPDATE {tabela} SET {atrib} WHERE id=?{e_mais}',
                                valores + [ident] + filtrados)
                    flash('Item atualizado.', 'ok')
                else:
                    # Colunas que o bloco impõe a todo item novo — é o que faz
                    # a reserva nascer com grupo='reserva' em vez de 'sistema'.
                    for coluna, valor in info.get('fixos', {}).items():
                        colunas, valores = colunas + [coluna], valores + [valor]
                    if bloco == 'menu':
                        # A chave identifica o item na URL do módulo; sai do
                        # nome e ganha sufixo se já existir.
                        base = re.sub(r'[^a-z0-9]+', '-',
                                      valores[0].lower().strip()).strip('-') or 'item'
                        chave, n = base, 2
                        while con.execute('SELECT 1 FROM paginas_lateral WHERE chave=?',
                                          (chave,)).fetchone():
                            chave, n = f'{base}-{n}', n + 1
                        colunas = colunas + ['chave']
                        valores = valores + [chave]
                    marcas = ','.join('?' * len(colunas))
                    con.execute(f"INSERT INTO {tabela} ({','.join(colunas)})"
                                f' VALUES ({marcas})', valores)
                    flash('Item adicionado.', 'ok')
        con.commit()
        return redirect(url_for('admin_painel', bloco=bloco))

    bloco = request.args.get('bloco', 'escalas')
    if bloco not in BLOCOS:
        bloco = 'escalas'
    info = BLOCOS[bloco]
    tabela = info.get('tabela', bloco)
    clausula, filtrados = _filtro(info)
    editar = None
    if request.args.get('editar'):
        editar = con.execute(
            f"SELECT * FROM {tabela} WHERE id=?{f' AND {clausula}' if clausula else ''}",
            [_int(request.args['editar'])] + filtrados).fetchone()
    da_secao_links = info.get('secao') == 'links'
    return render_template(
        'admin_painel.html', bloco=bloco, info=info, editar=editar,
        abas=abas_links(bloco) if da_secao_links else abas_painel(bloco),
        aba_topo='links' if da_secao_links else 'painel',
        cartao=dados_titulo_cartao(bloco),
        aparencia=dados_aparencia_cartao(bloco), fontes=FONTES_TEXTO,
        nome_bloco=nome_do_bloco(bloco, info['titulo']),
        itens=con.execute(
            f"SELECT * FROM {tabela}{f' WHERE {clausula}' if clausula else ''}"
            f" ORDER BY {info['ordem']}", filtrados).fetchall())


# ── backup e restauração ───────────────────────────────────────────────────────

def _itens_do_backup():
    """(caminho no disco, nome dentro do zip) de tudo que é conteúdo da unidade:
    o banco e as imagens enviadas. A chave de sessão fica de fora — é segredo
    desta instalação e sua ausência só faz os usuários entrarem de novo."""
    itens = [(DB_PATH, 'dados.db')]
    for nome in FUNDO_NOMES + LOGO_NOMES:
        caminho = os.path.join(STATIC_DIR, nome)
        if os.path.isfile(caminho):
            itens.append((caminho, f'static/{nome}'))
    # Marcas d'água: nome fixo, extensão variável — vão pelo prefixo.
    for nome in sorted(os.listdir(STATIC_DIR)):
        if nome.startswith('marca-') and os.path.splitext(nome)[1].lower() in MARCA_EXTS:
            itens.append((os.path.join(STATIC_DIR, nome), f'static/{nome}'))
    for pasta, prefixo in ((UPLOAD_DIR, 'static/uploads'), (ICONES_DIR, 'static/icones')):
        if os.path.isdir(pasta):
            for nome in sorted(os.listdir(pasta)):
                caminho = os.path.join(pasta, nome)
                if os.path.isfile(caminho):
                    itens.append((caminho, f'{prefixo}/{nome}'))
    return itens


def _monta_backup():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for caminho, interno in _itens_do_backup():
            z.write(caminho, interno)
    buf.seek(0)
    return buf


def _destino_seguro(nome):
    """Converte um nome de dentro do zip no caminho real, recusando qualquer
    tentativa de escapar da pasta do portal (../.. ou caminho absoluto)."""
    nome = nome.replace('\\', '/')
    if nome.startswith('/') or '..' in nome.split('/'):
        return None
    if nome == 'dados.db':
        return DB_PATH
    if nome.startswith('static/'):
        relativo = nome[len('static/'):]
        for inicio, destino in (('uploads/', UPLOAD_DIR), ('icones/', ICONES_DIR)):
            if relativo.startswith(inicio):
                arquivo = secure_filename(os.path.basename(relativo))
                return os.path.join(destino, arquivo) if arquivo else None
        if relativo in FUNDO_NOMES + LOGO_NOMES:
            return os.path.join(STATIC_DIR, relativo)
        if (relativo.startswith('marca-') and '/' not in relativo
                and os.path.splitext(relativo)[1].lower() in MARCA_EXTS):
            return os.path.join(STATIC_DIR, relativo)
    return None


@app.route('/admin/backup', methods=['GET'])
@admin_obrigatorio
def admin_backup():
    copias = []
    if os.path.isdir(BACKUP_DIR):
        for nome in sorted(os.listdir(BACKUP_DIR), reverse=True):
            caminho = os.path.join(BACKUP_DIR, nome)
            if os.path.isfile(caminho):
                copias.append({'nome': nome,
                               'kb': round(os.path.getsize(caminho) / 1024),
                               'data': datetime.fromtimestamp(
                                   os.path.getmtime(caminho)).strftime('%d/%m/%Y %H:%M')})
    con = db()
    return render_template('admin_backup.html', copias=copias[:10], conteudo={
        'links':    con.execute('SELECT COUNT(*) c FROM links').fetchone()['c'],
        'banners':  con.execute('SELECT COUNT(*) c FROM banners').fetchone()['c'],
        'lateral':  con.execute('SELECT COUNT(*) c FROM lateral').fetchone()['c'],
        'ramais':   con.execute('SELECT COUNT(*) c FROM ramais').fetchone()['c'],
        'usuarios': con.execute('SELECT COUNT(*) c FROM usuarios').fetchone()['c'],
    })


@app.route('/admin/backup/baixar', methods=['POST'])
@admin_obrigatorio
def backup_baixar():
    nome = f"portal-backup-{datetime.now():%Y-%m-%d-%H%M}.zip"
    return send_file(_monta_backup(), mimetype='application/zip',
                     as_attachment=True, download_name=nome)


@app.route('/admin/backup/restaurar', methods=['POST'])
@admin_obrigatorio
def backup_restaurar():
    arq = request.files.get('arquivo')
    if not arq or not arq.filename:
        flash('Escolha o arquivo de backup.', 'erro')
        return redirect(url_for('admin_backup'))

    try:
        dados = io.BytesIO(arq.read())
        with zipfile.ZipFile(dados) as z:
            nomes = z.namelist()
            if 'dados.db' not in nomes:
                flash('Este arquivo não parece um backup do portal '
                      '(não contém dados.db).', 'erro')
                return redirect(url_for('admin_backup'))

            # Salva o estado atual ANTES de sobrescrever — é o que permite
            # voltar atrás se o backup restaurado não for o esperado.
            os.makedirs(BACKUP_DIR, exist_ok=True)
            anterior = os.path.join(
                BACKUP_DIR, f"antes-de-restaurar-{datetime.now():%Y-%m-%d-%H%M%S}.zip")
            with open(anterior, 'wb') as f:
                f.write(_monta_backup().read())

            restaurados, ignorados = 0, 0
            for interno in nomes:
                if interno.endswith('/'):
                    continue
                destino = _destino_seguro(interno)
                if not destino:
                    ignorados += 1
                    continue
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with z.open(interno) as origem, open(destino, 'wb') as saida:
                    saida.write(origem.read())
                restaurados += 1
    except zipfile.BadZipFile:
        flash('Arquivo inválido: não é um .zip.', 'erro')
        return redirect(url_for('admin_backup'))
    except Exception as e:
        flash(f'Falha ao restaurar: {e}', 'erro')
        return redirect(url_for('admin_backup'))

    # O banco restaurado pode ser de uma versão anterior, sem as tabelas e
    # colunas criadas depois. A migração roda no start do serviço, e restaurar
    # troca o arquivo por baixo do processo — sem isto o portal quebra inteiro
    # (erro 500) até alguém reiniciar o serviço.
    try:
        init_db()
    except Exception as e:
        flash(f'Backup restaurado, mas a atualização do banco falhou: {e}. '
              'Reinicie o serviço (systemctl restart intranet).', 'erro')
        session.clear()
        return redirect(url_for('login'))

    aviso = f'Backup restaurado ({restaurados} itens).'
    if ignorados:
        aviso += f' {ignorados} entrada(s) fora do padrão foram ignoradas.'
    aviso += ' Entre novamente com a senha daquele backup.'
    # A ordem importa: o Flask guarda os avisos na sessão, então limpar depois
    # de avisar apagaria a mensagem. Limpa primeiro (o banco mudou, os usuários
    # podem ser outros) e só então registra o aviso.
    session.clear()
    flash(aviso, 'ok')
    return redirect(url_for('login'))


@app.route('/admin/icones', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_icones():
    """Ícones próprios da unidade — logos de sistemas, brasões, o que for.

    Ficam em static/icones/ como arquivos soltos, do mesmo jeito que o logo e
    a foto de fundo: dá para enviar por aqui ou copiar direto no servidor."""
    os.makedirs(ICONES_DIR, exist_ok=True)
    if request.method == 'POST':
        # O botão de excluir mora dentro do formulário do zoom (aninhar <form>
        # não é HTML válido), então ele se identifica pelo próprio nome.
        if request.form.get('excluir') or request.form.get('acao') == 'excluir':
            nome = secure_filename(request.form.get('excluir')
                                   or request.form.get('nome', ''))
            caminho = os.path.join(ICONES_DIR, nome)
            if nome and os.path.isfile(caminho):
                os.remove(caminho)
                # Leva junto o zoom, senão um ícone novo com o mesmo nome
                # nasceria com o ajuste do que foi apagado.
                con = db()
                con.execute('DELETE FROM config WHERE chave=?',
                            (ICONE_ZOOM + nome,))
                con.commit()
                # Quem usava o ícone volta ao símbolo genérico sozinho, porque
                # icone_de_arquivo() confere a existência antes de desenhar.
                flash(f'Ícone {nome} removido. Os itens que o usavam voltam '
                      'ao símbolo padrão.', 'ok')
            return redirect(url_for('admin_icones'))

        if request.form.get('acao') == 'zoom':
            con = db()
            for nome in icones_enviados():
                bruto = request.form.get(f'zoom_{nome}')
                if bruto is None:
                    continue
                valor = min(ZOOM_MAX, max(ZOOM_MIN, _int(bruto, ZOOM_PADRAO)))
                con.execute('INSERT INTO config (chave,valor) VALUES (?,?) '
                            'ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                            (ICONE_ZOOM + nome, str(valor)))
            con.commit()
            flash('Tamanhos ajustados.', 'ok')
            return redirect(url_for('admin_icones'))

        enviado = request.files.get('icone')
        if not enviado or not enviado.filename:
            flash('Escolha um arquivo.', 'erro')
            return redirect(url_for('admin_icones'))
        ext = os.path.splitext(enviado.filename)[1].lower()
        if ext not in ICONE_EXTS:
            flash('Formato não aceito. Use SVG, PNG, WEBP ou JPG.', 'erro')
            return redirect(url_for('admin_icones'))
        # Nome escolhido pelo administrador, para o seletor ficar legível.
        base = secure_filename(os.path.splitext(
            request.form.get('nome', '').strip() or enviado.filename)[0])
        if not base:
            flash('Dê um nome ao ícone.', 'erro')
            return redirect(url_for('admin_icones'))
        enviado.save(os.path.join(ICONES_DIR, base + ext))
        flash(f'Ícone {base}{ext} enviado.', 'ok')
        return redirect(url_for('admin_icones'))

    return render_template('admin_icones.html', itens=icones_enviados(),
                           zooms=zooms_icones(), zoom_padrao=ZOOM_PADRAO,
                           zoom_min=ZOOM_MIN, zoom_max=ZOOM_MAX)


@app.route('/admin/aparencia', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_aparencia():
    con = db()
    if request.method == 'POST':
        if request.form.get('acao') == 'remover_fundo':
            _apaga_arquivos(FUNDO_NOMES)
            flash('Imagem de fundo removida.', 'ok')
            return redirect(url_for('admin_aparencia'))
            flash("Marca d'água removida.", 'ok')
            return redirect(url_for('admin_aparencia'))

        # Os uploads substituem os arquivos fixos static/fundo.<ext> e
        # static/logo.<ext>; trocar esses arquivos direto no servidor tem
        # exatamente o mesmo efeito.
        for campo, base, nomes, exts in (
                ('fundo', 'fundo', FUNDO_NOMES, {'.jpg', '.jpeg', '.png', '.webp'}),
                ('logo',  'logo',  LOGO_ENVIADO, {'.png', '.jpg', '.jpeg', '.webp', '.svg'}),):
            erro = _troca_imagem_fixa(campo, base, nomes, exts)
            if erro:
                flash(erro, 'erro')
                return redirect(url_for('admin_aparencia'))

        novos = {
            'site_nome':    request.form.get('site_nome', '').strip(),
            'site_sigla':   request.form.get('site_sigla', '').strip(),
            'site_sub':     request.form.get('site_sub', '').strip(),
            'capa_abertura': request.form.get('capa_abertura', '').strip(),
            'capa_titulo':   request.form.get('capa_titulo', '').strip(),
            'capa_texto':    request.form.get('capa_texto', '').strip(),
            'capa_texto2':   request.form.get('capa_texto2', '').strip(),
            'capa_titulo_tam': medida(request.form.get('capa_titulo_tam'),
                                      PADROES['capa_titulo_tam'], 0.8, 4.0),
            'capa_texto_tam':  medida(request.form.get('capa_texto_tam'),
                                      PADROES['capa_texto_tam'], 0.6, 2.0),
            'capa_titulo_cor': cor_hexa(request.form.get('capa_titulo_cor'),
                                        PADROES['capa_titulo_cor']),
            'capa_texto_cor':  cor_hexa(request.form.get('capa_texto_cor'),
                                        PADROES['capa_texto_cor']),
            # O texto dos comunicados e o dos botões saíram daqui: cada um é
            # editado na tela do cartão a que pertence (ver APARENCIA_CARTAO).
            # Regravá-los aqui os devolveria ao padrão a cada salvamento, já
            # que os campos não existem mais neste formulário.
            'fundo_modo':   (request.form.get('fundo_modo')
                             if request.form.get('fundo_modo') in FUNDO_MODOS
                             else PADROES['fundo_modo']),
            'fundo_cor':    cor_hexa(request.form.get('fundo_cor'),
                                     PADROES['fundo_cor']),
            'fundo_veu':    medida(request.form.get('fundo_veu'),
                                   PADROES['fundo_veu'], 0, 100),
            'capa_cor':     cor_hexa(request.form.get('capa_cor'),
                                     PADROES['capa_cor']),
            'lateral_cor1': cor_hexa(request.form.get('lateral_cor1'),
                                     PADROES['lateral_cor1']),
            'lateral_cor2': cor_hexa(request.form.get('lateral_cor2'),
                                     PADROES['lateral_cor2']),
            'cor_primaria': cor_hexa(request.form.get('cor_primaria'),
                                     PADROES['cor_primaria']),
            'cor_destaque': cor_hexa(request.form.get('cor_destaque'),
                                     PADROES['cor_destaque']),
            'banner_seg':   str(max(2, min(60, _int(request.form.get('banner_seg'), 6)))),
        }
        # Os nomes dos cartões saíram daqui: cada um é editado na tela do
        # próprio bloco. Regravá-los neste laço apagaria todos de volta ao
        # padrão a cada vez que alguém salvasse Aparência — os campos não
        # existem mais neste formulário, e `request.form.get` viria vazio.

        for k, v in novos.items():
            con.execute('INSERT INTO config (chave,valor) VALUES (?,?) '
                        'ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                        (k, v))
        con.commit()
        flash('Aparência salva.', 'ok')
        return redirect(url_for('admin_aparencia'))
    return render_template('admin_aparencia.html', fontes=FONTES_TEXTO)


@app.route('/admin/navegacao', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_navegacao():
    """Faixa de links do topo e cartão "Em destaque" da tela inicial."""
    if request.method == 'POST':
        def campo(nome, limite):
            return request.form.get(nome, '').strip()[:limite]

        # Linha sem nome é descartada; o resto é gravado como foi digitado, e
        # o endereço só é validado na hora de desenhar (linhas_faixa).
        linhas = [l.strip() for l in request.form.get('faixa_links', '').splitlines()
                  if l.strip()][:20]
        novos = {
            'faixa_links':     '\n'.join(l[:200] for l in linhas),
            'lista_paginas_ativa': '1' if request.form.get('lista_paginas_ativa') else '0',
            'destaque_ativo':  '1' if request.form.get('destaque_ativo') else '0',
            'destaque_rotulo': campo('destaque_rotulo', 40),
            'destaque_titulo': campo('destaque_titulo', 90),
            'destaque_texto':  campo('destaque_texto', 220),
            'destaque_url':    campo('destaque_url', 300),
            'destaque_cta':    campo('destaque_cta', 40),
        }
        con = db()
        for k, v in novos.items():
            con.execute('INSERT INTO config (chave,valor) VALUES (?,?) '
                        'ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                        (k, v))
        con.commit()
        flash('Navegação salva.', 'ok')
        return redirect(url_for('admin_navegacao'))
    return render_template('admin_navegacao.html')


@app.route('/admin/pagina-rapida', methods=['POST'])
@admin_obrigatorio
def admin_pagina_rapida():
    """Edição da página inteira em uma janela só (cabeçalho, capa e texto livre
    com imagens), pela própria página. Responde JSON."""
    con = db()
    chave = request.form.get('chave', '')
    item = con.execute('SELECT * FROM paginas_lateral WHERE chave=?', (chave,)).fetchone()
    if not item:
        return jsonify(ok=False, erro='Página não encontrada.'), 404

    def campo(nome, limite):
        return request.form.get(nome, '').strip()[:limite]
    capa_atual = item['capa'] or ''
    try:
        capa = salva_upload('capa_arquivo', capa_atual)
        biblio = os.path.basename(request.form.get('capa_biblioteca', '') or '')
        if capa == capa_atual and biblio and modulos.midia.registrada(biblio):
            capa = biblio
    except ValueError as e:
        return jsonify(ok=False, erro=str(e)), 400
    if request.form.get('remover_capa'):
        capa = ''
    resumo = '\n'.join([l.strip()[:200] for l in request.form.get('resumo', '').splitlines()
                        if l.strip()][:6])
    con.execute('UPDATE paginas_lateral SET chapeu=?,linha_fina=?,autor=?,publicada_em=?,capa=?,'
                'capa_legenda=?,capa_credito=?,resumo=?,mostrar_resumo=?,mostrar_leia=?,corpo=?'
                ' WHERE chave=?',
                (campo('chapeu', 40), campo('linha_fina', 220), campo('autor', 60),
                 _dt_banco(request.form.get('publicada_em')), capa,
                 campo('capa_legenda', 200), campo('capa_credito', 80), resumo,
                 1 if request.form.get('mostrar_resumo') else 0,
                 1 if request.form.get('mostrar_leia') else 0,
                 limpa_html(request.form.get('corpo', '')), chave))
    pagina_tocada(con, chave)
    con.commit()
    return jsonify(ok=True)


TIPOS_BLOCO = {'subtitulo': 'Subtítulo', 'texto': 'Texto', 'imagem': 'Imagem',
               'botao': 'Botão de link'}


def destinos_de_links():
    """Páginas do portal para onde um link pode apontar: (nome, endereço)."""
    return [('Início', '/'), ('Ramais', '/ramais'), ('Sistemas', '/sistemas')] + \
        [(r['nome'], r['url'] if (r['url'] or '').startswith('/') else f"/modulo/{r['chave']}") for r in db().execute(
            'SELECT nome,chave,url FROM paginas_lateral ORDER BY ordem, id')] + \
        [('Notícia: ' + r['titulo'], f"/noticias/{r['slug']}") for r in db().execute(
            "SELECT titulo,slug FROM noticias WHERE estado='publicado' ORDER BY id DESC LIMIT 60")]


@app.route('/admin/pagina/<chave>', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_pagina(chave):
    """Editor do conteúdo de uma página do menu: subtítulos, textos formatados e
    imagens, com prévia da página ao lado do formulário."""
    con = db()
    item = con.execute('SELECT * FROM paginas_lateral WHERE chave=?', (chave,)).fetchone()
    if not item:
        abort(404)
    volta = url_for('admin_pagina', chave=chave)
    ajax = bool(request.form.get('ajax'))
    ultimo = {'id': 0}

    def fim(destino):
        """Fim de uma ação: redireciona, ou, na edição direta pela página
        (ajax), responde em JSON com o erro, se houve."""
        if not ajax:
            return redirect(destino)
        erros = [m for c, m in get_flashed_messages(with_categories=True) if c == 'erro']
        return jsonify(ok=not erros, erro=' '.join(erros), id=ultimo['id']), (400 if erros else 200)

    if request.method == 'POST':
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))
        if acao == 'ordenar':
            pagina_tocada(con, chave)
            return reordenar('pagina_blocos')

        if acao == 'cabecalho':
            # Cabeçalho de matéria: chapéu, linha fina, autor, data, capa e resumo.
            def campo(nome, limite):
                return request.form.get(nome, '').strip()[:limite]
            volta_cab = url_for('admin_pagina', chave=chave, cab=1) + '#cabecalho'
            capa_atual = item['capa'] or ''
            try:
                capa = salva_upload('capa_arquivo', capa_atual)
            except ValueError as e:
                flash(str(e), 'erro')
                return redirect(volta_cab)
            if request.form.get('remover_capa') and capa == capa_atual:
                capa = ''
            if capa_atual and capa != capa_atual:
                remove_upload(capa_atual)      # a da biblioteca fica; só sai a avulsa
            resumo = '\n'.join([l.strip()[:200] for l in
                                request.form.get('resumo', '').splitlines() if l.strip()][:6])
            con.execute('UPDATE paginas_lateral SET chapeu=?,linha_fina=?,autor=?,publicada_em=?,'
                        'capa=?,capa_legenda=?,capa_credito=?,resumo=?,mostrar_resumo=?,'
                        'mostrar_leia=? WHERE chave=?',
                        (campo('chapeu', 40), campo('linha_fina', 220), campo('autor', 60),
                         _dt_banco(request.form.get('publicada_em')), capa,
                         campo('capa_legenda', 200), campo('capa_credito', 80), resumo,
                         1 if request.form.get('mostrar_resumo') else 0,
                         1 if request.form.get('mostrar_leia') else 0, chave))
            pagina_tocada(con, chave)
            con.commit()
            flash('Cabeçalho da página salvo.', 'ok')
            return redirect(volta_cab)

        atual = con.execute('SELECT * FROM pagina_blocos WHERE id=? AND chave=?',
                            (ident, chave)).fetchone() if ident else None

        if acao == 'excluir':
            if atual:
                remove_upload(atual['arquivo'])
                con.execute('DELETE FROM pagina_blocos WHERE id=?', (ident,))
                pagina_tocada(con, chave)
                con.commit()
                flash('Bloco removido.', 'ok')
            return fim(volta)

        if acao == 'mover':
            ids = [r['id'] for r in con.execute(
                'SELECT id FROM pagina_blocos WHERE chave=? ORDER BY ordem, id', (chave,))]
            if atual and ident in ids:
                i = ids.index(ident)
                j = i - 1 if request.form.get('direcao') == 'subir' else i + 1
                if 0 <= j < len(ids):
                    ids[i], ids[j] = ids[j], ids[i]
                for pos, bid in enumerate(ids):
                    con.execute('UPDATE pagina_blocos SET ordem=? WHERE id=?', (pos, bid))
                pagina_tocada(con, chave)
                con.commit()
            return fim(f'{volta}#b{ident}')

        tipo = request.form.get('tipo') if request.form.get('tipo') in TIPOS_BLOCO else 'texto'
        if atual:
            tipo = atual['tipo']        # o tipo de um bloco existente não muda
        larg = _int(request.form.get('larg'), 100)
        larg = larg if larg in LARGURAS_IMG else 100
        alinh = request.form.get('alinh') if request.form.get('alinh') in ALINHA_IMG else 'centro'
        estilo = request.form.get('estilo') if request.form.get('estilo') in ESTILOS_TEXTO else 'normal'
        formato, arquivo = 'texto', ''
        # Para onde o clique leva (subtítulo, imagem e botão). Interno (/modulo/x)
        # ou externo; qualquer outra coisa é descartada por `endereco_seguro`.
        url = endereco_seguro(request.form.get('url', '')) if tipo != 'texto' else ''
        if tipo == 'texto':
            # O editor manda HTML; é limpo aqui, e só o resultado é guardado.
            texto, formato = limpa_html(request.form.get('html', '')), 'html'
            vazio = not (so_texto(texto) or '<li' in texto or '<img' in texto)
        elif tipo == 'subtitulo':
            texto = request.form.get('texto', '').strip()[:200]
            vazio = not texto
        elif tipo == 'botao':
            texto = request.form.get('texto', '').strip()[:100]
            vazio = not (texto and url)
        else:
            texto = request.form.get('texto', '').strip()[:300]
            try:
                arquivo = salva_upload('arquivo', atual['arquivo'] if atual else '')
            except ValueError as e:
                flash(str(e), 'erro')
                return fim(volta)
            if atual and atual['arquivo'] and arquivo != atual['arquivo']:
                remove_upload(atual['arquivo'])      # trocou a imagem: a antiga sai
            vazio = not arquivo

        ativo = 1 if request.form.get('ativo') else 0
        if vazio:
            flash('Escolha uma imagem para este bloco.' if tipo == 'imagem'
                  else 'Informe o texto e o endereço do botão.' if tipo == 'botao'
                  else 'Escreva o conteúdo do bloco.', 'erro')
        elif atual:
            con.execute('UPDATE pagina_blocos SET texto=?,arquivo=?,ativo=?,larg=?,'
                        'alinh=?,estilo=?,formato=?,url=? WHERE id=?',
                        (texto, arquivo, ativo, larg, alinh, estilo, formato, url, ident))
            pagina_tocada(con, chave)
            con.commit()
            flash('Bloco atualizado.', 'ok')
            ultimo['id'] = ident
            return fim(url_for('admin_pagina', chave=chave, editar=ident) + f'#b{ident}')
        else:
            proxima = con.execute('SELECT COALESCE(MAX(ordem),-1)+1 FROM pagina_blocos'
                                  ' WHERE chave=?', (chave,)).fetchone()[0]
            novo = con.execute(
                'INSERT INTO pagina_blocos (chave,tipo,texto,arquivo,ordem,ativo,larg,'
                'alinh,estilo,formato,url) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (chave, tipo, texto, arquivo, proxima, ativo, larg, alinh, estilo, formato, url))
            pagina_tocada(con, chave)
            con.commit()
            ultimo['id'] = novo.lastrowid
            # "Adicionar aqui" (edição direta): entra logo depois do bloco indicado.
            depois = request.form.get('depois', '')
            if depois != '':
                ids = [r['id'] for r in con.execute(
                    'SELECT id FROM pagina_blocos WHERE chave=? AND id<>? ORDER BY ordem, id',
                    (chave, novo.lastrowid))]
                pos = ids.index(_int(depois)) + 1 if _int(depois) in ids else (0 if depois == '0' else len(ids))
                ids.insert(pos, novo.lastrowid)
                for n, bid in enumerate(ids):
                    con.execute('UPDATE pagina_blocos SET ordem=? WHERE id=?', (n, bid))
                con.commit()
            flash('Bloco adicionado.', 'ok')
            return fim(f'{volta}#b{novo.lastrowid}')
        return fim(volta)

    editar = None
    if request.args.get('editar'):
        editar = con.execute('SELECT * FROM pagina_blocos WHERE id=? AND chave=?',
                             (_int(request.args['editar']), chave)).fetchone()
    html_editar = ''
    if editar and editar['tipo'] == 'texto':
        html_editar = Markup(limpa_html(editar['texto']) if editar['formato'] == 'html'
                             else texto_para_html(editar['texto']))
    linhas = con.execute('SELECT * FROM pagina_blocos WHERE chave=?'
                         ' ORDER BY ordem, id', (chave,)).fetchall()
    cab = cabecalho_pagina(item)
    return render_template(
        'admin_pagina.html', item=item, editar=editar, tipos=TIPOS_BLOCO,
        html_editar=html_editar, larguras=LARGURAS_IMG, alinhamentos=ROTULO_ALINHA,
        estilos=ESTILOS_TEXTO, blocos=agrupar_blocos(linhas), total=len(linhas),
        destinos=destinos_de_links(), cab=cab,
        leia=leia_tambem() if cab['leia'] else [],
        cab_aberto=bool(request.args.get('cab')),
        publicada_campo=_dt_campo(item['publicada_em']),
        categorias=modulos.noticias.categorias(),
        biblioteca=modulos.midia.itens(limite=100))


# Recursos em módulos (ver modulos/__init__.py). Rodando como `python app.py`, o
# módulo se chama __main__; o alias evita que os módulos importem uma segunda
# cópia do núcleo.
sys.modules.setdefault('app', sys.modules[__name__])
import modulos                                  # noqa: E402  (registra as rotas)
SCHEMA += modulos.SCHEMA

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORTA', 8000)), debug=False)
