"""Biblioteca de imagens.

Todas as imagens enviadas ao portal (blocos de página, banners, cartões,
capas de notícia) ficam em static/uploads e são catalogadas aqui, com título,
texto alternativo, legenda e descrição. A biblioteca mostra onde cada imagem
está em uso, impede apagar a que está em uso e deixa reaproveitar uma imagem
em outro lugar sem enviá-la de novo."""
import os
import re
import secrets
from collections import defaultdict

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

import app as nucleo
from . import seguranca

app = nucleo.app

SCHEMA = """
CREATE TABLE IF NOT EXISTS midia (
    arquivo   TEXT PRIMARY KEY,
    titulo    TEXT NOT NULL DEFAULT '',
    alt       TEXT NOT NULL DEFAULT '',
    legenda   TEXT NOT NULL DEFAULT '',
    descricao TEXT NOT NULL DEFAULT '',
    original  TEXT NOT NULL DEFAULT '',
    tamanho   INTEGER NOT NULL DEFAULT 0,
    enviado_por TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

LIMITE_IMAGEM = 10 * 1024 * 1024        # 10 MB por imagem
EXTENSOES = nucleo.EXT_OK


def _pasta():
    return nucleo.UPLOAD_DIR


def _caminho(arquivo):
    return os.path.join(_pasta(), secure_filename(arquivo))


def registrar_arquivo(arquivo, original='', tamanho=0):
    """Cataloga um arquivo já salvo em uploads/ (se ainda não estiver)."""
    if os.path.splitext(arquivo)[1].lower() not in EXTENSOES:
        return
    con = nucleo.db()
    con.execute('INSERT OR IGNORE INTO midia (arquivo,original,tamanho,enviado_por)'
                ' VALUES (?,?,?,?)',
                (arquivo, (original or arquivo)[:200], tamanho,
                 session.get('user', '') if session else ''))
    con.commit()


def registrada(arquivo):
    if not arquivo:
        return False
    return nucleo.db().execute('SELECT 1 FROM midia WHERE arquivo=?', (arquivo,)).fetchone() is not None


def sincroniza():
    """Cataloga o que já estava em uploads/ antes da biblioteca existir e tira do
    catálogo o que foi apagado do disco."""
    con = nucleo.db()
    if os.path.isdir(_pasta()):
        for f in os.listdir(_pasta()):
            caminho = os.path.join(_pasta(), f)
            if os.path.isfile(caminho) and os.path.splitext(f)[1].lower() in EXTENSOES:
                con.execute('INSERT OR IGNORE INTO midia (arquivo,original,tamanho) VALUES (?,?,?)',
                            (f, f, os.path.getsize(caminho)))
    for (arquivo,) in con.execute('SELECT arquivo FROM midia').fetchall():
        if not os.path.isfile(_caminho(arquivo)):
            con.execute('DELETE FROM midia WHERE arquivo=?', (arquivo,))
    con.commit()


def usos_todos():
    """{arquivo: [(descrição, endereço de edição)]} — onde cada imagem aparece."""
    con = nucleo.db()
    usos = defaultdict(list)

    for r in con.execute("SELECT b.arquivo, b.chave, COALESCE(p.nome, b.chave) nome"
                         " FROM pagina_blocos b LEFT JOIN paginas_lateral p ON p.chave=b.chave"
                         " WHERE b.arquivo<>''"):
        usos[r['arquivo']].append((f"Página “{r['nome']}”",
                                   url_for('admin_pagina', chave=r['chave'])))
    for r in con.execute("SELECT chave, nome, capa FROM paginas_lateral WHERE capa<>''"):
        usos[r['capa']].append((f"Capa da página “{r['nome']}”",
                                url_for('admin_pagina', chave=r['chave'], cab=1) + '#cabecalho'))
    for r in con.execute("SELECT arquivo FROM banners WHERE arquivo<>''"):
        usos[r['arquivo']].append(('Banner da página inicial', url_for('admin_banners')))
    for r in con.execute("SELECT imagem, titulo FROM lateral WHERE imagem<>''"):
        usos[r['imagem']].append((f"Cartão “{r['titulo']}”", url_for('admin_lateral')))
    for r in con.execute("SELECT imagem, titulo FROM cartoes WHERE imagem<>''"):
        usos[r['imagem']].append((f"Cartão “{r['titulo']}”", url_for('admin_lateral')))
    # Cartões de texto e imagem: a imagem está dentro do texto formatado. Edita-se
    # no próprio portal (Editar portal → clicar no nome do cartão).
    for r in con.execute("SELECT p.nome, k.html FROM cartao_conteudo k"
                         " JOIN cartoes_painel p ON p.chave=k.chave"):
        for arq in set(re.findall(r'uploads/([\w.\-]+)', r['html'] or '')):
            usos[arq].append((f"Cartão de texto e imagem “{r['nome']}” (Editar portal → clique no nome do cartão)",
                              url_for('editor')))
    for r in con.execute("SELECT id, titulo, capa, corpo FROM noticias"):
        achados = set(re.findall(r'uploads/([\w.\-]+)', r['corpo'] or ''))
        if r['capa']:
            achados.add(r['capa'])
        for arq in achados:
            usos[arq].append((f"Notícia “{r['titulo']}”",
                              url_for('admin_noticias', editar=r['id'])))
    return usos


def itens(busca='', filtro='', limite=None):
    sincroniza()
    usos = usos_todos()
    con = nucleo.db()
    onde, args = '', []
    if busca:
        onde = ' WHERE titulo LIKE ? OR original LIKE ? OR alt LIKE ? OR legenda LIKE ? OR descricao LIKE ?'
        args = [f'%{busca}%'] * 5
    saida = []
    for r in con.execute('SELECT * FROM midia' + onde + ' ORDER BY criado_em DESC, arquivo', args):
        u = usos.get(r['arquivo'], [])
        if filtro == 'uso' and not u:
            continue
        if filtro == 'livre' and u:
            continue
        saida.append({**dict(r), 'usos': u,
                      'url': url_for('static', filename='uploads/' + r['arquivo']),
                      'nome': r['titulo'] or r['original']})
        if limite and len(saida) >= limite:
            break
    return saida


def alt_de(arquivo, padrao=''):
    """Texto alternativo para a imagem: o da biblioteca, se houver; senão o padrão."""
    if not arquivo:
        return padrao
    r = nucleo.db().execute('SELECT alt, titulo FROM midia WHERE arquivo=?', (arquivo,)).fetchone()
    if r and (r['alt'] or ''):
        return r['alt']
    return padrao or (r['titulo'] if r else '') or ''


app.jinja_env.globals['midia_alt'] = alt_de


def _salva_imagem(arq):
    """Valida e grava um arquivo enviado; devolve o nome salvo. ValueError com
    mensagem pronta para o administrador se algo estiver errado."""
    ext = os.path.splitext(arq.filename or '')[1].lower()
    if ext not in EXTENSOES:
        raise ValueError(f'“{arq.filename}”: formato não aceito. Use PNG, JPG, WEBP ou GIF.')
    if not seguranca.conteudo_confere(arq, ext):
        raise ValueError(f'“{arq.filename}” não é uma imagem válida (o conteúdo não corresponde ao formato).')
    nome = f'{secrets.token_hex(8)}{ext}'
    os.makedirs(_pasta(), exist_ok=True)
    destino = os.path.join(_pasta(), nome)
    arq.save(destino)
    if os.path.getsize(destino) > LIMITE_IMAGEM:
        os.remove(destino)
        raise ValueError(f'“{arq.filename}” passa de {LIMITE_IMAGEM // 1048576} MB.')
    return nome


@app.route('/admin/midia', methods=['GET', 'POST'])
@nucleo.admin_obrigatorio
def admin_midia():
    con = nucleo.db()
    if request.method == 'POST':
        acao = request.form.get('acao')
        arquivo = request.form.get('arquivo', '')
        if acao == 'enviar':
            enviados = 0
            for arq in request.files.getlist('arquivos'):
                if not arq or not arq.filename:
                    continue
                try:
                    nome = _salva_imagem(arq)
                except ValueError as e:
                    flash(str(e), 'erro')
                    continue
                registrar_arquivo(nome, arq.filename, os.path.getsize(_caminho(nome)))
                enviados += 1
            if enviados:
                flash(f'{enviados} imagem(ns) enviada(s).', 'ok')
            elif not get_erros():
                flash('Escolha ao menos uma imagem.', 'erro')
        elif acao == 'salvar' and registrada(arquivo):
            con.execute('UPDATE midia SET titulo=?, alt=?, legenda=?, descricao=? WHERE arquivo=?',
                        (request.form.get('titulo', '').strip()[:200],
                         request.form.get('alt', '').strip()[:300],
                         request.form.get('legenda', '').strip()[:300],
                         request.form.get('descricao', '').strip()[:1000], arquivo))
            con.commit()
            flash('Dados da imagem salvos.', 'ok')
        elif acao == 'excluir' and registrada(arquivo):
            onde = usos_todos().get(arquivo, [])
            if onde:
                flash('Esta imagem está em uso e não pode ser excluída: ' +
                      '; '.join(d for d, _ in onde[:3]) + '.', 'erro')
            else:
                con.execute('DELETE FROM midia WHERE arquivo=?', (arquivo,))
                con.commit()
                try:
                    os.remove(_caminho(arquivo))
                except OSError:
                    pass
                flash('Imagem excluída.', 'ok')
        elif acao == 'limpar':
            usos = usos_todos()
            n = 0
            for (arq,) in con.execute('SELECT arquivo FROM midia').fetchall():
                if arq not in usos:
                    con.execute('DELETE FROM midia WHERE arquivo=?', (arq,))
                    try:
                        os.remove(_caminho(arq))
                    except OSError:
                        pass
                    n += 1
            con.commit()
            flash(f'{n} imagem(ns) sem uso excluída(s).', 'ok')
        elif acao == 'substituir' and registrada(arquivo):
            novo = request.files.get('novo')
            ext = os.path.splitext(arquivo)[1].lower()
            onde = usos_todos().get(arquivo, [])
            if not novo or not novo.filename:
                flash('Escolha o arquivo que vai substituir a imagem.', 'erro')
            elif os.path.splitext(novo.filename)[1].lower() != ext:
                flash(f'O novo arquivo precisa ser {ext.upper().lstrip(".")}, o mesmo formato da imagem atual.', 'erro')
            elif onde and not request.form.get('confirmo'):
                flash('Confirme que a troca vale para todos os lugares onde a imagem aparece.', 'erro')
            elif not seguranca.conteudo_confere(novo, ext):
                flash('O arquivo não é uma imagem válida.', 'erro')
            else:
                tmp = _caminho(arquivo) + '.novo'
                novo.save(tmp)
                if os.path.getsize(tmp) > LIMITE_IMAGEM:
                    os.remove(tmp)
                    flash('A imagem passa de 10 MB.', 'erro')
                else:
                    os.replace(tmp, _caminho(arquivo))
                    con.execute('UPDATE midia SET tamanho=? WHERE arquivo=?',
                                (os.path.getsize(_caminho(arquivo)), arquivo))
                    con.commit()
                    flash('Imagem substituída em todos os lugares onde é usada.', 'ok')
        return redirect(url_for('admin_midia', q=request.args.get('q', ''), f=request.args.get('f', '')))

    busca = (request.args.get('q') or '').strip()
    filtro = request.args.get('f') if request.args.get('f') in ('uso', 'livre') else ''
    lista = itens(busca, filtro)
    total_livres = sum(1 for i in itens() if not i['usos'])
    return render_template('admin_midia.html', itens=lista, busca=busca, filtro=filtro,
                           livres=total_livres)


def get_erros():
    return [m for c, m in session.get('_flashes', []) if c == 'erro']


@app.route('/admin/midia/lista')
@nucleo.admin_obrigatorio
def admin_midia_lista():
    """Imagens para o seletor do editor de páginas."""
    busca = (request.args.get('q') or '').strip()
    return jsonify(itens=[{'arquivo': i['arquivo'], 'url': i['url'], 'nome': i['nome'],
                           'alt': i['alt'], 'usos': len(i['usos'])}
                          for i in itens(busca, limite=80)])


@app.route('/admin/midia/enviar', methods=['POST'])
@nucleo.admin_obrigatorio
def admin_midia_enviar():
    """Envio de uma imagem pelo seletor (sem sair da página de edição)."""
    arq = request.files.get('arquivo')
    if not arq or not arq.filename:
        return jsonify(ok=False, erro='Escolha uma imagem.'), 400
    try:
        nome = _salva_imagem(arq)
    except ValueError as e:
        return jsonify(ok=False, erro=str(e)), 400
    registrar_arquivo(nome, arq.filename, os.path.getsize(_caminho(nome)))
    return jsonify(ok=True, item={'arquivo': nome, 'nome': arq.filename, 'alt': '',
                                  'url': url_for('static', filename='uploads/' + nome), 'usos': 0})
