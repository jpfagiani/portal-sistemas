"""Segurança: tentativas de login, cabeçalhos, páginas de erro e arquivos."""
import os
import time

from flask import jsonify, render_template, request

import app as nucleo

app = nucleo.app

SCHEMA = """
CREATE TABLE IF NOT EXISTS tentativas_login (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ip      TEXT NOT NULL DEFAULT '',
    usuario TEXT NOT NULL DEFAULT '',
    em      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tentativas_em ON tentativas_login (em);
"""

# Quantas falhas, em quanto tempo, antes de pedir que espere. Os valores são
# folgados para quem erra a senha uma ou duas vezes e apertados para quem tenta
# adivinhá-la. O contador fica no banco porque o gunicorn roda vários
# processos — um contador em memória seria diferente em cada um.
LIMITE_FALHAS = int(os.environ.get('PORTAL_LOGIN_LIMITE', '8'))
JANELA_SEG = int(os.environ.get('PORTAL_LOGIN_JANELA', '600'))


def _ip():
    return request.remote_addr or ''


def espera_login(usuario=''):
    """Segundos que ainda faltam para poder tentar de novo (0 = liberado)."""
    con = nucleo.db()
    desde = time.time() - JANELA_SEG
    con.execute('DELETE FROM tentativas_login WHERE em < ?', (desde,))
    for campo, valor in (('ip', _ip()), ('usuario', (usuario or '').lower())):
        if not valor:
            continue
        linhas = [r['em'] for r in con.execute(
            f'SELECT em FROM tentativas_login WHERE {campo}=? AND em>=? ORDER BY em',
            (valor, desde))]
        if len(linhas) >= LIMITE_FALHAS:
            return max(1, int(linhas[-LIMITE_FALHAS] + JANELA_SEG - time.time()))
    return 0


def registra_falha(usuario=''):
    con = nucleo.db()
    con.execute('INSERT INTO tentativas_login (ip,usuario,em) VALUES (?,?,?)',
                (_ip(), (usuario or '').lower()[:80], time.time()))
    con.commit()


def limpa_falhas(usuario=''):
    con = nucleo.db()
    con.execute('DELETE FROM tentativas_login WHERE ip=? OR usuario=?',
                (_ip(), (usuario or '').lower()))
    con.commit()


# ── conteúdo real dos arquivos ─────────────────────────────────────────────────
# A extensão é o que o remetente diz; o começo do arquivo é o que ele é. Um
# arquivo chamado foto.png que não começa como PNG não é uma imagem.

def _confere(cabecalho, ext):
    c = cabecalho
    if ext == '.png':
        return c.startswith(b'\x89PNG\r\n\x1a\n')
    if ext in ('.jpg', '.jpeg'):
        return c.startswith(b'\xff\xd8\xff')
    if ext == '.gif':
        return c.startswith((b'GIF87a', b'GIF89a'))
    if ext == '.webp':
        return c[:4] == b'RIFF' and c[8:12] == b'WEBP'
    if ext == '.mp4':
        return c[4:8] == b'ftyp'
    if ext in ('.webm',):
        return c.startswith(b'\x1aE\xdf\xa3')
    if ext in ('.ogg', '.ogv'):
        return c.startswith(b'OggS')
    return False


def conteudo_confere(arquivo, ext):
    """True se o começo do arquivo enviado corresponde à extensão. O ponteiro do
    arquivo volta ao início, pronto para ser salvo."""
    cab = arquivo.stream.read(16)
    arquivo.stream.seek(0)
    return _confere(cab, ext.lower())


# ── cabeçalhos ─────────────────────────────────────────────────────────────────

@app.after_request
def _cabecalhos(resp):
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    resp.headers.setdefault('Referrer-Policy', 'same-origin')
    resp.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    return resp


# ── páginas de erro ────────────────────────────────────────────────────────────

_TITULOS = {
    400: 'Não foi possível concluir',
    403: 'Acesso negado',
    404: 'Página não encontrada',
    405: 'Ação não permitida',
    413: 'Arquivo grande demais',
    500: 'Algo deu errado',
}
_MENSAGENS = {
    403: 'Você não tem permissão para abrir esta página.',
    404: 'O endereço pode ter mudado ou a página ainda não foi publicada.',
    413: 'O arquivo enviado passa do limite aceito pelo portal.',
    500: 'O erro foi registrado. Tente de novo em instantes.',
}


def _erro(e):
    codigo = getattr(e, 'code', 500) or 500
    mensagem = getattr(e, 'description', '') or ''
    if codigo in _MENSAGENS and (codigo != 400):
        mensagem = _MENSAGENS[codigo]
    # Edição direta (fetch): devolve JSON em vez de uma página inteira.
    if request.method == 'POST' and request.form.get('ajax'):
        return jsonify(ok=False, erro=mensagem or _TITULOS.get(codigo, 'Erro')), codigo
    try:
        html = render_template('erro.html', codigo=codigo,
                               titulo=_TITULOS.get(codigo, 'Erro'), mensagem=mensagem)
    except Exception:
        return f'{codigo} — {_TITULOS.get(codigo, "Erro")}', codigo
    return html, codigo


for _codigo in (400, 403, 404, 405, 413, 500):
    app.register_error_handler(_codigo, _erro)
