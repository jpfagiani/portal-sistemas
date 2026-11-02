"""Cartões livres de texto e imagem.

Qualquer pessoa com acesso de administrador cria, na própria página inicial
(modo "Editar portal"), um cartão com texto formatado e imagens da biblioteca,
e o edita depois com um clique no nome dele. No layout livre o cartão novo cai
no primeiro espaço vazio do quadro; no layout em colunas, na fileira de baixo.
"""
import secrets

from flask import jsonify, request
from markupsafe import Markup

import app as nucleo

app = nucleo.app

SCHEMA = """
CREATE TABLE IF NOT EXISTS cartao_conteudo (
    chave          TEXT PRIMARY KEY,
    html           TEXT NOT NULL DEFAULT '',
    titulo_visivel INTEGER NOT NULL DEFAULT 0,
    url            TEXT NOT NULL DEFAULT ''     -- se preenchido, o cartão inteiro é um link
);
"""

LARGURA_NOVO, ALTURA_NOVO = 3, 12       # em células do quadro livre (12 colunas)


def conteudo(chave):
    """HTML já limpo do cartão (guardado limpo, e limpo de novo ao ler)."""
    r = nucleo.db().execute('SELECT html FROM cartao_conteudo WHERE chave=?', (chave,)).fetchone()
    return Markup(nucleo.agrupa_figuras(nucleo.limpa_html(r['html']))) if r else Markup('')


def titulo_visivel(chave):
    """O nome do cartão aparece no portal? Por padrão não: o nome é para o administrador gerenciar."""
    con = nucleo.db()
    r = con.execute('SELECT titulo_visivel FROM cartao_conteudo WHERE chave=?', (chave,)).fetchone()
    if r:
        return bool(r['titulo_visivel'])
    r = con.execute('SELECT valor FROM config WHERE chave=?', (chave + '_titulo_visivel',)).fetchone()
    return bool(r and r['valor'] == '1')


def url_cartao(chave):
    """Endereço do cartão inteiro (título, texto e imagem): o escolhido, ou a matéria completa do cartão, ou vazio."""
    r = nucleo.db().execute('SELECT url,materia_html FROM cartao_conteudo WHERE chave=?', (chave,)).fetchone()
    if not r:
        return ''
    return nucleo.endereco_seguro(r['url']) or (('/materia/cartao/' + chave) if nucleo.so_texto(r['materia_html']) or '<img' in (r['materia_html'] or '') else '')


def dados_edicao():
    """Mapa chave -> dados, para o editor abrir o cartão já preenchido."""
    saida = {}
    for c in nucleo.db().execute(
            "SELECT p.chave,p.nome,k.html,k.titulo_visivel,k.url FROM cartoes_painel p"
            " JOIN cartao_conteudo k ON k.chave=p.chave WHERE p.tipo='conteudo'"):
        saida[c['chave']] = {'nome': c['nome'], 'html': nucleo.limpa_html(c['html']),
                             'titulo_visivel': bool(c['titulo_visivel']), 'url': c['url'] or ''}
    return saida


app.jinja_env.globals['cartao_conteudo'] = conteudo
app.jinja_env.filters['rico'] = lambda h: Markup(nucleo.agrupa_figuras(nucleo.limpa_html(h or '')))
app.jinja_env.globals['cartao_titulo_visivel'] = titulo_visivel
app.jinja_env.globals['cartao_url'] = url_cartao


def vaga_livre(con, gw=LARGURA_NOVO, gh=ALTURA_NOVO):
    """Primeiro espaço do quadro onde um cartão gw × gh não cobre nenhum outro."""
    ocupados = [dict(r) for r in con.execute(
        'SELECT gx,gy,gw,gh FROM cartoes_painel WHERE ativo=1 AND gw>0')]
    for chave, p in nucleo._lateral_posicoes(con).items():
        if nucleo.lateral_desenhada(chave):
            ocupados.append(p)
    for gy in range(0, 600):
        for gx in range(0, nucleo.LIVRE_COLUNAS - gw + 1):
            cand = {'gx': gx, 'gy': gy, 'gw': gw, 'gh': gh}
            if not any(nucleo._livre_sobrepoe(cand, o) for o in ocupados):
                return cand
    return {'gx': 0, 'gy': 600, 'gw': gw, 'gh': gh}


# ── excluir, copiar, ocultar e mostrar (editor de layout) ──────────────────────

FIXOS = ('sistemas', 'atalhos', 'ramais', 'noticias')     # um só de cada; só se ocultam


def _copia_arquivo(nome):
    """Cópia física de um upload, para o cartão copiado não depender do arquivo
    do original (excluir um apagaria a imagem do outro). Imagem da biblioteca é
    compartilhada de propósito e fica como está."""
    import os, shutil
    from werkzeug.utils import secure_filename
    if not nome or nucleo.modulos.midia.registrada(nome):
        return nome
    origem = os.path.join(nucleo.UPLOAD_DIR, secure_filename(nome))
    if not os.path.isfile(origem):
        return nome
    base, ext = os.path.splitext(secure_filename(nome))
    novo = f'{secrets.token_hex(6)}{ext}'
    shutil.copyfile(origem, os.path.join(nucleo.UPLOAD_DIR, novo))
    return novo


def _duplica(con, chave):
    c = con.execute('SELECT * FROM cartoes_painel WHERE chave=?', (chave,)).fetchone()
    if not c or c['tipo'] not in ('itens', 'conteudo'):
        return None
    c = dict(c)
    ordem = con.execute('SELECT COALESCE(MAX(ordem),0)+1 FROM cartoes_painel').fetchone()[0]
    if c['tipo'] == 'itens':
        nova = nucleo._proxima_chave_cartao(con)
    else:
        nova = 'conteudo-' + secrets.token_hex(4)
    c.update(chave=nova, ordem=ordem, nome=(c['nome'] + ' (cópia)')[:80])
    if c['gw'] > 0:                      # um pouco deslocado, para ver que é outro
        c['gx'] = min(c['gx'] + 1, max(0, nucleo.LIVRE_COLUNAS - c['gw']))
        c['gy'] = c['gy'] + 1
    c.pop('id', None)
    cols = list(c)
    con.execute(f"INSERT INTO cartoes_painel ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                [c[k] for k in cols])
    con.execute('UPDATE cartoes_painel SET z=(SELECT COALESCE(MAX(z),0)+1 FROM cartoes_painel) WHERE chave=?', (nova,))
    if c['tipo'] == 'conteudo':
        con.execute('INSERT INTO cartao_conteudo (chave,html,titulo_visivel,url,materia_titulo,materia_html) '
                    'SELECT ?,html,titulo_visivel,url,materia_titulo,materia_html FROM cartao_conteudo WHERE chave=?', (nova, chave))
    else:
        nucleo._semear_aparencia(con, nova)
        for r in con.execute("SELECT chave,valor FROM config WHERE substr(chave,1,?)=?",
                             (len(chave) + 1, chave + '_')).fetchall():
            con.execute('INSERT OR REPLACE INTO config (chave,valor) VALUES (?,?)',
                        (nova + r['chave'][len(chave):], r['valor']))
        colunas = [x[1] for x in con.execute('PRAGMA table_info(lateral)') if x[1] != 'id']
        for it in con.execute('SELECT * FROM lateral WHERE cartao=?', (chave,)).fetchall():
            d = dict(it)
            d['cartao'] = nova
            for campo in ('imagem', 'video'):
                if campo in d:
                    d[campo] = _copia_arquivo(d[campo])
            con.execute(f"INSERT INTO lateral ({','.join(colunas)}) VALUES ({','.join('?' * len(colunas))})",
                        [d[k] for k in colunas])
    return nova


@app.route('/admin/cartao-acao', methods=['POST'])
@nucleo.admin_obrigatorio
def admin_cartao_acao():
    """excluir | duplicar | mostrar, sobre um cartão do quadro. Responde JSON."""
    con = nucleo.db()
    acao = request.form.get('acao', '')
    chave = request.form.get('chave', '')
    c = con.execute('SELECT * FROM cartoes_painel WHERE chave=?', (chave,)).fetchone()
    if not c:
        return jsonify(ok=False, erro='Cartão não encontrado.'), 404

    if acao == 'duplicar':
        nova = _duplica(con, chave)
        if not nova:
            return jsonify(ok=False, erro='Este cartão é único e não pode ser copiado.'), 400
        con.commit()
        return jsonify(ok=True, chave=nova)

    if acao == 'mostrar':
        pos = vaga_livre(con, max(1, c['gw'] or LARGURA_NOVO), max(4, c['gh'] or ALTURA_NOVO))
        con.execute('UPDATE cartoes_painel SET ativo=1,gx=?,gy=?,gw=?,gh=? WHERE chave=?',
                    (pos['gx'], pos['gy'], pos['gw'], pos['gh'], chave))
        con.commit()
        return jsonify(ok=True)

    if acao == 'excluir':
        if c['tipo'] in FIXOS:
            con.execute('UPDATE cartoes_painel SET ativo=0 WHERE chave=?', (chave,))
            con.commit()
            return jsonify(ok=True, oculto=True)
        if c['tipo'] == 'conteudo':
            con.execute('DELETE FROM cartao_conteudo WHERE chave=?', (chave,))
        elif c['tipo'] == 'itens':
            if con.execute("SELECT COUNT(*) FROM cartoes_painel WHERE tipo='itens'").fetchone()[0] <= 1:
                return jsonify(ok=False, erro='Este é o último cartão de itens; crie outro antes de excluí-lo.'), 400
            for l in con.execute('SELECT imagem, video FROM lateral WHERE cartao=?', (chave,)).fetchall():
                nucleo.remove_upload(l['imagem'])
                nucleo.remove_upload(l['video'])
            con.execute('DELETE FROM lateral WHERE cartao=?', (chave,))
        con.execute('DELETE FROM cartoes_painel WHERE chave=?', (chave,))
        con.commit()
        return jsonify(ok=True)

    return jsonify(ok=False, erro='Ação desconhecida.'), 400


def ocultos():
    """Cartões desligados, para o editor oferecer "mostrar de novo"."""
    return [dict(chave=r['chave'], nome=r['nome']) for r in nucleo.db().execute(
        "SELECT chave,nome FROM cartoes_painel WHERE ativo=0 ORDER BY ordem")]
