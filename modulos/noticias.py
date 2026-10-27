"""Notícias e publicações.

Um único modelo de conteúdo (título, resumo, corpo, capa, categoria, estado e
data de publicação) serve para notícias, comunicados e matérias. O estado diz
em que pé está: rascunho, publicado ou arquivado; uma data de publicação no
futuro deixa o conteúdo "agendado" — ele aparece sozinho quando a hora chega,
sem tarefa agendada no servidor (a data é conferida a cada visita)."""
import os
import re
import unicodedata
from datetime import datetime

from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
from markupsafe import Markup

import app as nucleo
from . import midia

app = nucleo.app

SCHEMA = """
CREATE TABLE IF NOT EXISTS noticias (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT UNIQUE NOT NULL,
    titulo        TEXT NOT NULL,
    subtitulo     TEXT NOT NULL DEFAULT '',
    resumo        TEXT NOT NULL DEFAULT '',
    corpo         TEXT NOT NULL DEFAULT '',     -- HTML já limpo pelo servidor
    capa          TEXT NOT NULL DEFAULT '',     -- arquivo em static/uploads
    capa_alt      TEXT NOT NULL DEFAULT '',
    legenda       TEXT NOT NULL DEFAULT '',
    categoria     TEXT NOT NULL DEFAULT '',
    autor         TEXT NOT NULL DEFAULT '',
    estado        TEXT NOT NULL DEFAULT 'rascunho',   -- rascunho | publicado | arquivado
    publicar_em   TEXT NOT NULL DEFAULT '',     -- AAAA-MM-DD HH:MM:SS, hora local
    destaque      INTEGER NOT NULL DEFAULT 0,
    destino_url   TEXT NOT NULL DEFAULT '',     -- se preenchido, o cartão leva para lá
    meta          TEXT NOT NULL DEFAULT '',     -- descrição para buscadores
    criado_em     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_noticias_pub ON noticias (estado, publicar_em);
"""

ESTADOS = {'rascunho': 'Rascunho', 'publicado': 'Publicado', 'arquivado': 'Arquivado'}
# Só aparece para o público o que está publicado E já chegou a hora.
VISIVEL = "estado='publicado' AND publicar_em<>'' AND publicar_em <= datetime('now','localtime')"
POR_PAGINA = 10


def slugify(texto):
    s = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:80] or 'noticia'


def _slug_livre(con, base, ignorar_id=0):
    slug, n = base, 2
    while con.execute('SELECT 1 FROM noticias WHERE slug=? AND id<>?', (slug, ignorar_id)).fetchone():
        slug, n = f'{base}-{n}', n + 1
    return slug


def situacao(n):
    """Rótulo de estado para o administrador: distingue publicado de agendado."""
    if n['estado'] == 'publicado':
        if n['publicar_em'] and n['publicar_em'] > datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
            return 'Agendada'
        return 'Publicada'
    return ESTADOS.get(n['estado'], n['estado'])


def _data_br(valor):
    try:
        return datetime.strptime(valor[:16], '%Y-%m-%d %H:%M').strftime('%d/%m/%Y')
    except ValueError:
        return ''


app.jinja_env.filters['data_br'] = _data_br
app.jinja_env.globals['situacao_noticia'] = situacao


def recentes(limite=4):
    """Últimas publicações visíveis (destaques primeiro) para a página inicial."""
    return nucleo.db().execute(
        f'SELECT * FROM noticias WHERE {VISIVEL} ORDER BY destaque DESC, publicar_em DESC, id DESC LIMIT ?',
        (limite,)).fetchall()


def categorias():
    return [r[0] for r in nucleo.db().execute(
        "SELECT DISTINCT categoria FROM noticias WHERE categoria<>'' ORDER BY categoria COLLATE NOCASE")]


# ── páginas públicas ───────────────────────────────────────────────────────────

@app.route('/noticias')
def noticias():
    con = nucleo.db()
    cat = (request.args.get('c') or '').strip()
    pagina = max(1, nucleo._int(request.args.get('p'), 1))
    onde, args = VISIVEL, []
    if cat:
        onde += ' AND categoria=?'
        args.append(cat)
    total = con.execute(f'SELECT COUNT(*) FROM noticias WHERE {onde}', args).fetchone()[0]
    linhas = con.execute(
        f'SELECT * FROM noticias WHERE {onde} ORDER BY destaque DESC, publicar_em DESC, id DESC LIMIT ? OFFSET ?',
        args + [POR_PAGINA, (pagina - 1) * POR_PAGINA]).fetchall()
    cats = [r[0] for r in con.execute(
        f"SELECT DISTINCT categoria FROM noticias WHERE {VISIVEL} AND categoria<>'' ORDER BY categoria COLLATE NOCASE")]
    # `pg` e não `pagina`: o template já usa `pagina` para dizer ao menu qual item
    # está ativo, e a colisão derrubava a lista assim que passava de uma página.
    return render_template('noticias.html', itens=linhas, categorias=cats, categoria=cat,
                           pg=pagina, paginas=max(1, -(-total // POR_PAGINA)))


@app.route('/noticias/<slug>')
def noticia(slug):
    con = nucleo.db()
    n = con.execute('SELECT * FROM noticias WHERE slug=?', (slug,)).fetchone()
    if not n:
        abort(404)
    previa = False
    visivel = con.execute(f'SELECT 1 FROM noticias WHERE id=? AND {VISIVEL}', (n['id'],)).fetchone()
    if not visivel:
        # Rascunho, agendada ou arquivada: só o administrador vê, como pré-visualização.
        if not session.get('admin'):
            abort(404)
        previa = True
    admin = bool(session.get('admin'))
    return render_template('noticia.html', n=n, corpo=Markup(nucleo.limpa_html(n['corpo'])), previa=previa,
                           situacao=situacao(n), estados_noticia=ESTADOS,
                           destinos_links=nucleo.destinos_de_links() if admin else [])


# ── administração ──────────────────────────────────────────────────────────────

def _para_banco(valor):
    """'2026-10-18T14:30' (campo datetime-local) -> '2026-10-18 14:30:00'."""
    valor = (valor or '').strip().replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(valor, fmt).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
    return ''


def _para_campo(valor):
    return (valor or '')[:16].replace(' ', 'T')


@app.route('/admin/noticias', methods=['GET', 'POST'])
@nucleo.admin_obrigatorio
def admin_noticias():
    con = nucleo.db()
    if request.method == 'POST':
        acao = request.form.get('acao')
        ident = nucleo._int(request.form.get('id'))
        atual = con.execute('SELECT * FROM noticias WHERE id=?', (ident,)).fetchone() if ident else None

        if acao == 'excluir':
            if atual:
                con.execute('DELETE FROM noticias WHERE id=?', (ident,))
                con.commit()
                flash('Notícia excluída. A imagem de capa continua na biblioteca.', 'ok')
            return redirect(url_for('admin_noticias'))

        titulo = request.form.get('titulo', '').strip()[:200]
        if not titulo:
            flash('Informe o título.', 'erro')
            return redirect(url_for('admin_noticias', editar=ident) if ident else url_for('admin_noticias', nova=1))

        estado = request.form.get('estado') if request.form.get('estado') in ESTADOS else 'rascunho'
        if acao == 'publicar':
            estado = 'publicado'
        publicar_em = _para_banco(request.form.get('publicar_em'))
        if estado == 'publicado' and (not publicar_em or acao == 'publicar' and not request.form.get('publicar_em')):
            publicar_em = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        corpo = nucleo.limpa_html(request.form.get('corpo', ''))
        capa = atual['capa'] if atual else ''
        try:
            arq = request.files.get('capa_arquivo')
            if arq and arq.filename:
                capa = midia._salva_imagem(arq)
                midia.registrar_arquivo(capa, arq.filename, os.path.getsize(midia._caminho(capa)))
            elif request.form.get('capa_biblioteca') and midia.registrada(request.form['capa_biblioteca']):
                capa = request.form['capa_biblioteca']
            elif request.form.get('remover_capa'):
                capa = ''
        except ValueError as e:
            flash(str(e), 'erro')
            return redirect(url_for('admin_noticias', editar=ident) if ident else url_for('admin_noticias', nova=1))

        destino = nucleo.endereco_seguro(request.form.get('destino_url', ''))
        slug = _slug_livre(con, slugify(request.form.get('slug') or titulo), ident)
        dados = (slug, titulo, request.form.get('subtitulo', '').strip()[:300],
                 request.form.get('resumo', '').strip()[:600], corpo, capa,
                 request.form.get('capa_alt', '').strip()[:300], request.form.get('legenda', '').strip()[:300],
                 request.form.get('categoria', '').strip()[:60], estado, publicar_em,
                 1 if request.form.get('destaque') else 0, destino,
                 request.form.get('meta', '').strip()[:300])
        if atual:
            con.execute("UPDATE noticias SET slug=?,titulo=?,subtitulo=?,resumo=?,corpo=?,capa=?,capa_alt=?,"
                        "legenda=?,categoria=?,estado=?,publicar_em=?,destaque=?,destino_url=?,meta=?,"
                        "atualizado_em=datetime('now','localtime') WHERE id=?", dados + (ident,))
            novo_id = ident
        else:
            novo_id = con.execute(
                "INSERT INTO noticias (slug,titulo,subtitulo,resumo,corpo,capa,capa_alt,legenda,categoria,"
                "estado,publicar_em,destaque,destino_url,meta,autor) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                dados + (session.get('nome') or session.get('user', ''),)).lastrowid
        con.commit()
        flash('Publicada.' if acao == 'publicar' else 'Notícia salva.', 'ok')
        return redirect(url_for('admin_noticias', editar=novo_id))

    editar, nova = None, bool(request.args.get('nova'))
    if request.args.get('editar'):
        editar = con.execute('SELECT * FROM noticias WHERE id=?', (nucleo._int(request.args['editar']),)).fetchone()
    filtro = request.args.get('estado') if request.args.get('estado') in ESTADOS else ''
    lista = con.execute('SELECT * FROM noticias' + (' WHERE estado=?' if filtro else '') +
                        ' ORDER BY id DESC', ([filtro] if filtro else [])).fetchall()
    return render_template('admin_noticias.html', itens=lista, editar=editar, nova=nova, filtro=filtro,
                           estados=ESTADOS, categorias=categorias(), biblioteca=midia.itens(limite=100), destinos_links=nucleo.destinos_de_links(),
                           campo_data=_para_campo, corpo_editar=Markup(nucleo.limpa_html(editar['corpo'])) if editar else '')


@app.route('/admin/noticia-rapida', methods=['POST'])
@nucleo.admin_obrigatorio
def admin_noticia_rapida():
    """Edição completa pela própria página da notícia, em uma janela só: título,
    texto com imagens, capa e situação. Responde JSON."""
    con = nucleo.db()
    n = con.execute('SELECT * FROM noticias WHERE id=?', (nucleo._int(request.form.get('id')),)).fetchone()
    if not n:
        return jsonify(ok=False, erro='Notícia não encontrada.'), 404
    titulo = request.form.get('titulo', '').strip()[:200]
    if not titulo:
        return jsonify(ok=False, erro='Informe o título.'), 400
    capa = n['capa']
    try:
        arq = request.files.get('capa_arquivo')
        if arq and arq.filename:
            capa = midia._salva_imagem(arq)
            midia.registrar_arquivo(capa, arq.filename, os.path.getsize(midia._caminho(capa)))
        elif request.form.get('capa_biblioteca') and midia.registrada(request.form['capa_biblioteca']):
            capa = request.form['capa_biblioteca']
        elif request.form.get('remover_capa'):
            capa = ''
    except ValueError as e:
        return jsonify(ok=False, erro=str(e)), 400
    estado = request.form.get('estado') if request.form.get('estado') in ESTADOS else n['estado']
    publicar_em = n['publicar_em']
    if estado == 'publicado' and not publicar_em:
        publicar_em = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    con.execute("UPDATE noticias SET titulo=?,subtitulo=?,resumo=?,corpo=?,capa=?,capa_alt=?,legenda=?,"
                "categoria=?,estado=?,publicar_em=?,destaque=?,atualizado_em=datetime('now','localtime') WHERE id=?",
                (titulo, request.form.get('subtitulo', '').strip()[:300],
                 request.form.get('resumo', '').strip()[:600],
                 nucleo.limpa_html(request.form.get('corpo', '')), capa,
                 request.form.get('capa_alt', '').strip()[:300], request.form.get('legenda', '').strip()[:300],
                 request.form.get('categoria', '').strip()[:60], estado, publicar_em,
                 1 if request.form.get('destaque') else 0, n['id']))
    con.commit()
    return jsonify(ok=True)
