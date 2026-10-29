"""Conteúdos: uma única área para localizar, criar, editar, pré-visualizar e
publicar os textos do portal.

Há três tipos, que continuam guardados nas tabelas de sempre (nada é migrado):

  cartao      cartão de texto e imagem          (cartoes_painel + cartao_conteudo)
  noticia     notícia / matéria                 (noticias)
  comunicado  item de um cartão de comunicados  (lateral)

A interface é uma só — lista com busca e filtros, e um editor compartilhado.
Cada tipo mostra só os campos que lhe dizem respeito, e o salvamento é
encaminhado ao serviço do tipo, que mantém as regras de sempre (limpeza de HTML,
validação de endereço, envio de arquivos, publicação e agendamento).
"""
import os
import secrets
from datetime import datetime

from flask import abort, jsonify, redirect, render_template, request, session, url_for
from markupsafe import Markup

import app as nucleo
from . import auditoria, cartoes as mc, midia, noticias as mn

app = nucleo.app

TIPOS = {'cartao': 'Cartão', 'noticia': 'Notícia', 'comunicado': 'Comunicado'}
SITUACOES = {'visivel': 'Visível', 'oculto': 'Oculto', 'publicado': 'Publicada',
             'agendado': 'Agendada', 'rascunho': 'Rascunho', 'arquivado': 'Arquivado'}

auditoria._IGNORAR.add('conteudos_previa')      # pré-visualizar não altera nada


# ── utilidades ────────────────────────────────────────────────────────────────

def _volta(padrao=None):
    """Endereço de retorno vindo da URL, só se for do próprio portal."""
    v = request.values.get('volta', '')
    if v.startswith('/') and not v.startswith('//') and '\\' not in v:
        return v
    return padrao or url_for('conteudos')


def _erro(msg, codigo=400):
    return jsonify(ok=False, erro=msg), codigo


def _agora():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _texto_curto(html_ou_texto, n=90):
    t = nucleo.so_texto(html_ou_texto) if '<' in (html_ou_texto or '') else (html_ou_texto or '')
    t = ' '.join(t.split())
    return t if len(t) <= n else t[:n - 1] + '…'


def _casa(valor, q):
    return q.lower() in (valor or '').lower()


# ── listagem ──────────────────────────────────────────────────────────────────

def _linhas():
    con = nucleo.db()
    saida = []
    for r in con.execute(
            "SELECT p.chave,p.nome,p.ativo,k.html FROM cartoes_painel p"
            " JOIN cartao_conteudo k ON k.chave=p.chave WHERE p.tipo='conteudo' ORDER BY p.ordem,p.id"):
        saida.append(dict(tipo='cartao', id=r['chave'], titulo=r['nome'], extra=_texto_curto(r['html']),
                          situacao='visivel' if r['ativo'] else 'oculto', atualizado='', ordem=0,
                          onde='Página inicial'))
    nomes = {c['chave']: c['nome'] for c in nucleo.cartoes_do_painel()}
    for r in con.execute('SELECT * FROM lateral WHERE cartao<>\'\' ORDER BY cartao, ordem, id'):
        saida.append(dict(tipo='comunicado', id=r['id'], titulo=r['titulo'] or _texto_curto(r['conteudo'], 60) or '(sem título)',
                          extra=_texto_curto(r['conteudo']), situacao='visivel' if r['ativo'] else 'oculto',
                          atualizado='', ordem=r['ordem'], onde=nomes.get(r['cartao'], r['cartao'])))
    for n in con.execute(f'SELECT * FROM noticias ORDER BY {mn.ORDEM}'):
        s = mn.situacao(n)
        chave = {'Publicada': 'publicado', 'Agendada': 'agendado', 'Rascunho': 'rascunho',
                 'Arquivado': 'arquivado'}.get(s, n['estado'])
        saida.append(dict(tipo='noticia', id=n['id'], titulo=n['titulo'], extra=n['categoria'] or '',
                          situacao=chave, atualizado=(n['atualizado_em'] or '')[:16], ordem=n['ordem'],
                          onde='Últimas notícias', destaque=bool(n['destaque']), slug=n['slug']))
    return saida


@app.route('/admin/conteudos')
@nucleo.admin_obrigatorio
def conteudos():
    q = (request.args.get('q') or '').strip()
    tipo = request.args.get('tipo') if request.args.get('tipo') in TIPOS else ''
    sit = request.args.get('situacao') if request.args.get('situacao') in SITUACOES else ''
    linhas = [l for l in _linhas()
              if (not tipo or l['tipo'] == tipo) and (not sit or l['situacao'] == sit)
              and (not q or _casa(l['titulo'], q) or _casa(l['extra'], q))]
    for l in linhas:
        l['rotulo_tipo'] = TIPOS[l['tipo']]
        l['rotulo_situacao'] = SITUACOES.get(l['situacao'], l['situacao'])
    cartoes_itens = [c for c in nucleo.cartoes_do_painel() if c['tipo'] == 'itens']
    return render_template('admin_conteudos.html', linhas=linhas, tipos=TIPOS, situacoes=SITUACOES,
                           filtro_tipo=tipo, filtro_sit=sit, q=q, cartoes_itens=cartoes_itens,
                           ordenavel=(tipo == 'noticia' and not sit and not q),
                           aparencia=nucleo.dados_aparencia_cartao('noticias'), fontes=nucleo.FONTES_TEXTO,
                           noticias_vitrine=mn.vitrine())


# ── leitura de um conteúdo para o editor ──────────────────────────────────────

def _obter(tipo, ident):
    """Dicionário com os valores do formulário, ou None se não existir."""
    con = nucleo.db()
    if tipo == 'cartao':
        r = con.execute("SELECT p.chave,p.nome,k.html,k.titulo_visivel,k.url FROM cartoes_painel p"
                        " JOIN cartao_conteudo k ON k.chave=p.chave WHERE p.chave=? AND p.tipo='conteudo'",
                        (ident,)).fetchone()
        if not r:
            return None
        return dict(id=r['chave'], titulo=r['nome'], corpo=nucleo.limpa_html(r['html']),
                    titulo_visivel=bool(r['titulo_visivel']), url=r['url'] or '')
    if tipo == 'noticia':
        r = con.execute('SELECT * FROM noticias WHERE id=?', (nucleo._int(ident),)).fetchone()
        if not r:
            return None
        d = dict(r)
        d['corpo'] = nucleo.limpa_html(d['corpo'])
        d['url'] = d['destino_url']
        d['publicar_em_campo'] = mn._para_campo(d['publicar_em'])
        d['situacao'] = mn.situacao(r)
        return d
    if tipo == 'comunicado':
        r = con.execute('SELECT * FROM lateral WHERE id=?', (nucleo._int(ident),)).fetchone()
        return dict(r) if r else None
    return None


def _valores_novos(tipo):
    if tipo == 'cartao':
        return dict(id='', titulo='', corpo='', titulo_visivel=True, url='')
    if tipo == 'noticia':
        return dict(id='', titulo='', subtitulo='', resumo='', corpo='', capa='', capa_alt='', legenda='',
                    categoria='', estado='rascunho', publicar_em_campo='', destaque=0, url='', meta='',
                    slug='', titulo_fonte='', titulo_cor='', titulo_tam='', situacao='Rascunho')
    return dict(id='', titulo='', conteudo='', url='', url_rot='', imagem='', video='', img_pos='topo',
                urgencia='informacao', destaque='nenhum', data='', titulo_cor='', texto_cor='', fundo_cor='',
                titulo_tam='', texto_tam='', tipo='aviso', ativo=1)


@app.route('/admin/conteudos/<tipo>/<ident>')
@nucleo.admin_obrigatorio
def conteudos_editor(tipo, ident):
    if tipo not in TIPOS:
        abort(404)
    novo = ident == 'novo'
    d = _valores_novos(tipo) if novo else _obter(tipo, ident)
    if d is None:
        abort(404)
    cartao_chave = ''
    if tipo == 'comunicado':
        cartao_chave = d.get('cartao') if not novo else (request.args.get('cartao') or '')
        c = nucleo.cartao_por_chave(cartao_chave)
        if not c or c['tipo'] != 'itens':
            c = next((x for x in nucleo.cartoes_do_painel() if x['tipo'] == 'itens'), None)
            if not c:
                abort(404)
            cartao_chave = c['chave']
    return render_template(
        'admin_conteudo_editor.html', tipo=tipo, rotulo=TIPOS[tipo], novo=novo, d=d,
        cartao_chave=cartao_chave, volta=_volta(),
        estados=mn.ESTADOS, categorias=mn.categorias(), fontes=nucleo.FONTES_TEXTO,
        destinos_links=nucleo.destinos_de_links(), destaques=nucleo.DESTAQUES_COMUNICADO,
        img_pos=nucleo.CARTAO_IMG_POS, paleta=nucleo.PALETA,
        cartoes_itens=[c for c in nucleo.cartoes_do_painel() if c['tipo'] == 'itens'])


# ── salvamento (um serviço por tipo) ──────────────────────────────────────────

class Invalido(Exception):
    pass


def _salva_cartao(f, ident):
    con = nucleo.db()
    nome = f.get('titulo', '').strip()[:80]
    html = nucleo.limpa_html(f.get('corpo', ''))
    visivel = 1 if f.get('titulo_visivel') else 0
    url = nucleo.endereco_seguro(f.get('url', ''))
    if not nome and not nucleo.so_texto(html) and '<img' not in html:
        raise Invalido('Escreva um texto, escolha uma imagem ou dê um nome ao cartão.')
    nome = nome or 'Novo cartão'
    if ident:
        if not con.execute("SELECT 1 FROM cartoes_painel WHERE chave=? AND tipo='conteudo'", (ident,)).fetchone():
            raise Invalido('Cartão não encontrado.')
        con.execute('UPDATE cartoes_painel SET nome=? WHERE chave=?', (nome, ident))
        con.execute('INSERT INTO cartao_conteudo (chave,html,titulo_visivel,url) VALUES (?,?,?,?) '
                    'ON CONFLICT(chave) DO UPDATE SET html=excluded.html, titulo_visivel=excluded.titulo_visivel,'
                    ' url=excluded.url', (ident, html, visivel, url))
        chave = ident
    else:
        chave = 'conteudo-' + secrets.token_hex(4)
        ordem = con.execute('SELECT COALESCE(MAX(ordem),0)+1 FROM cartoes_painel').fetchone()[0]
        pos = mc.vaga_livre(con) if nucleo.layout_livre_ativo() else {'gx': 0, 'gy': 0, 'gw': 0, 'gh': 0}
        con.execute("INSERT INTO cartoes_painel (chave,nome,icone,regiao,largura,coluna,ordem,tipo,ativo,gx,gy,gw,gh)"
                    " VALUES (?,?,'prancheta','baixo',1,0,?,'conteudo',1,?,?,?,?)",
                    (chave, nome, ordem, pos['gx'], pos['gy'], pos['gw'], pos['gh']))
        con.execute('INSERT INTO cartao_conteudo (chave,html,titulo_visivel,url) VALUES (?,?,?,?)',
                    (chave, html, visivel, url))
    con.commit()
    return chave


def _capa_noticia(f, atual):
    """Capa enviada, escolhida na biblioteca ou removida (nesta ordem)."""
    arq = request.files.get('imagem')
    try:
        if arq and arq.filename:
            capa = midia._salva_imagem(arq)
            midia.registrar_arquivo(capa, arq.filename, os.path.getsize(midia._caminho(capa)))
            return capa
        escolhida = os.path.basename(f.get('imagem_biblioteca', '') or '')
        if escolhida and midia.registrada(escolhida):
            return escolhida
    except ValueError as e:
        raise Invalido(str(e))
    return '' if f.get('remover_imagem') else atual


def _salva_noticia(f, ident):
    con = nucleo.db()
    atual = con.execute('SELECT * FROM noticias WHERE id=?', (ident,)).fetchone() if ident else None
    if ident and not atual:
        raise Invalido('Notícia não encontrada.')
    acao = f.get('acao', 'salvar')
    titulo = f.get('titulo', '').strip()[:200]
    if not titulo:
        raise Invalido('Informe o título.')
    # Salvar nunca publica sozinho: só o botão Publicar (ou a situação escolhida).
    estado = f.get('estado') if f.get('estado') in mn.ESTADOS else 'rascunho'
    if acao == 'rascunho':
        estado = 'rascunho'
    elif acao == 'publicar':
        estado = 'publicado'
    publicar_em = mn._para_banco(f.get('publicar_em'))
    if estado == 'publicado' and not publicar_em:
        publicar_em = _agora()
    capa = _capa_noticia(f, atual['capa'] if atual else '')
    slug = mn._slug_livre(con, mn.slugify(f.get('slug') or titulo), ident or 0)
    dados = (slug, titulo, f.get('subtitulo', '').strip()[:300], f.get('resumo', '').strip()[:600],
             nucleo.limpa_html(f.get('corpo', '')), capa, f.get('capa_alt', '').strip()[:300],
             f.get('legenda', '').strip()[:300], f.get('categoria', '').strip()[:60], estado, publicar_em,
             1 if f.get('em_destaque') else 0, nucleo.endereco_seguro(f.get('url', '')),
             f.get('meta', '').strip()[:300]) + mn._titulo_do_form(f)
    if atual:
        if dados[11] and not atual['destaque']:
            con.execute('UPDATE noticias SET ordem=? WHERE id=?', (mn._topo(con), ident))
        con.execute("UPDATE noticias SET slug=?,titulo=?,subtitulo=?,resumo=?,corpo=?,capa=?,capa_alt=?,"
                    "legenda=?,categoria=?,estado=?,publicar_em=?,destaque=?,destino_url=?,meta=?,"
                    "titulo_fonte=?,titulo_cor=?,titulo_tam=?,atualizado_em=datetime('now','localtime')"
                    " WHERE id=?", dados + (ident,))
        novo = ident
    else:
        novo = con.execute(
            "INSERT INTO noticias (slug,titulo,subtitulo,resumo,corpo,capa,capa_alt,legenda,categoria,estado,"
            "publicar_em,destaque,destino_url,meta,titulo_fonte,titulo_cor,titulo_tam,autor,ordem)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            dados + (session.get('nome') or session.get('user', ''), mn._topo(con))).lastrowid
    con.commit()
    return novo


def _salva_comunicado(f, ident):
    con = nucleo.db()
    atuais = con.execute('SELECT * FROM lateral WHERE id=?', (ident,)).fetchone() if ident else None
    if ident and not atuais:
        raise Invalido('Comunicado não encontrado.')
    chave = atuais['cartao'] if atuais else f.get('cartao', '')
    c = nucleo.cartao_por_chave(chave)
    if not c or c['tipo'] != 'itens':
        raise Invalido('Escolha o cartão onde o comunicado aparece.')
    ant_img = atuais['imagem'] if atuais else ''
    ant_vid = atuais['video'] if atuais else ''
    try:
        imagem = nucleo.salva_upload('imagem', ant_img)
        video = nucleo.salva_upload('video', ant_vid, nucleo.VIDEO_EXTS)
    except ValueError as e:
        raise Invalido(str(e))
    for novo, ant in ((imagem, ant_img), (video, ant_vid)):
        if novo != ant:
            nucleo.remove_upload(ant)
    if f.get('remover_imagem'):
        nucleo.remove_upload(imagem)
        imagem = ''
    if f.get('remover_video'):
        nucleo.remove_upload(video)
        video = ''
    urg = f.get('urgencia', 'informacao')
    dest = f.get('destaque', 'nenhum')

    def medida(campo):
        return nucleo.medida(f.get(campo), '', 0.6, 2.0) if f.get(campo, '').strip() else ''
    texto = f.get('texto', '').strip('\r\n').rstrip()
    dados = (atuais['tipo'] if atuais else 'aviso', f.get('titulo', '').strip(), texto,
             nucleo.endereco_seguro(f.get('url', '')),
             1 if f.get('ativo') else 0,
             urg if urg in ('urgente', 'comunicado', 'informacao') else 'informacao',
             dest if dest in nucleo.DESTAQUES_COMUNICADO else 'nenhum',
             medida('titulo_tam'), nucleo.cor_hexa(f.get('titulo_cor'), ''),
             medida('texto_tam'), nucleo.cor_hexa(f.get('texto_cor'), ''),
             nucleo.cor_hexa(f.get('fundo_cor'), ''), f.get('data', '').strip(), imagem, video,
             f.get('url_rot', '').strip(),
             f.get('img_pos') if f.get('img_pos') in nucleo.CARTAO_IMG_POS else 'topo')
    if not (dados[1] or dados[2] or dados[3] or imagem or video):
        raise Invalido('Preencha ao menos um destes: título, texto, link, imagem ou vídeo.')
    campos = ('tipo,titulo,conteudo,url,ativo,urgencia,destaque,titulo_tam,titulo_cor,texto_tam,texto_cor,'
              'fundo_cor,data,imagem,video,url_rot,img_pos').split(',')
    if atuais:
        con.execute('UPDATE lateral SET ' + ','.join(k + '=?' for k in campos) + ' WHERE id=?', dados + (ident,))
        novo = ident
    else:
        ordem = con.execute('SELECT COALESCE(MAX(ordem),-1)+1 FROM lateral WHERE cartao=?', (chave,)).fetchone()[0]
        novo = con.execute('INSERT INTO lateral (' + ','.join(campos) + ',ordem,cartao) VALUES ('
                           + ','.join('?' * (len(campos) + 2)) + ')', dados + (ordem, chave)).lastrowid
    con.commit()
    return novo


SALVAR = {'cartao': _salva_cartao, 'noticia': _salva_noticia, 'comunicado': _salva_comunicado}


@app.route('/admin/conteudos/salvar', methods=['POST'])
@nucleo.admin_obrigatorio
def conteudos_salvar():
    tipo = request.form.get('tipo', '')
    if tipo not in SALVAR:
        return _erro('Tipo de conteúdo desconhecido.')
    ident = request.form.get('id', '').strip()
    if tipo != 'cartao':
        ident = nucleo._int(ident)
    try:
        novo = SALVAR[tipo](request.form, ident)
    except Invalido as e:
        return _erro(str(e))
    acao = request.form.get('acao', 'salvar')
    msg = {'publicar': 'Publicada.', 'rascunho': 'Rascunho salvo.'}.get(acao, 'Salvo.')
    return jsonify(ok=True, id=novo, mensagem=msg,
                   editar=url_for('conteudos_editor', tipo=tipo, ident=novo, volta=request.form.get('volta') or None))


# ── pré-visualização (não grava nada) ─────────────────────────────────────────

@app.route('/admin/conteudos/previa', methods=['POST'])
@nucleo.admin_obrigatorio
def conteudos_previa():
    tipo = request.form.get('tipo', '')
    if tipo not in TIPOS:
        return _erro('Tipo de conteúdo desconhecido.')
    f = request.form
    ident = f.get('id', '')
    contexto = dict(tipo=tipo, titulo=f.get('titulo', '').strip(), corpo=Markup(nucleo.limpa_html(f.get('corpo', ''))))
    if tipo == 'cartao':
        contexto.update(titulo_visivel=bool(f.get('titulo_visivel')))
    elif tipo == 'noticia':
        capa = ''
        if ident:
            r = nucleo.db().execute('SELECT capa FROM noticias WHERE id=?', (nucleo._int(ident),)).fetchone()
            capa = r['capa'] if r else ''
        escolhida = os.path.basename(f.get('imagem_biblioteca', '') or '')
        if escolhida and midia.registrada(escolhida):
            capa = escolhida
        if f.get('remover_imagem'):
            capa = ''
        if f.get('imagem_nova') and not capa:
            capa = 'pendente'
        contexto.update(subtitulo=f.get('subtitulo', ''), resumo=f.get('resumo', ''), capa=capa,
                        legenda=f.get('legenda', ''), capa_alt=f.get('capa_alt', ''),
                        categoria=f.get('categoria', ''), estilo=mn.estilo_titulo(
                            dict(zip(('titulo_fonte', 'titulo_cor', 'titulo_tam'), mn._titulo_do_form(f)))))
    else:
        item = dict(titulo=f.get('titulo', '').strip(), conteudo=f.get('texto', ''),
                    url=nucleo.endereco_seguro(f.get('url', '')), url_rot=f.get('url_rot', ''),
                    urgencia=f.get('urgencia', 'informacao'), destaque=f.get('destaque', 'nenhum'),
                    data=f.get('data', ''), img_pos=f.get('img_pos', 'topo'), tipo='aviso', id=0,
                    imagem='', video='', titulo_tam='', titulo_cor=nucleo.cor_hexa(f.get('titulo_cor'), ''),
                    texto_tam='', texto_cor=nucleo.cor_hexa(f.get('texto_cor'), ''),
                    fundo_cor=nucleo.cor_hexa(f.get('fundo_cor'), ''), img_larg=0, img_x=0)
        if ident:
            r = nucleo.db().execute('SELECT imagem,video FROM lateral WHERE id=?', (nucleo._int(ident),)).fetchone()
            if r:
                item['imagem'], item['video'] = r['imagem'], r['video']
        escolhida = os.path.basename(f.get('imagem_biblioteca', '') or '')
        if escolhida and midia.registrada(escolhida):
            item['imagem'] = escolhida
        if f.get('remover_imagem'):
            item['imagem'] = ''
        if f.get('imagem_nova') and not item['imagem']:
            item['imagem'] = 'pendente'
        if f.get('remover_video'):
            item['video'] = ''
        contexto['item'] = item
    return jsonify(ok=True, html=render_template('admin_conteudo_previa.html', **contexto))


# ── excluir e duplicar ────────────────────────────────────────────────────────

@app.route('/admin/conteudos/excluir', methods=['POST'])
@nucleo.admin_obrigatorio
def conteudos_excluir():
    tipo, ident = request.form.get('tipo', ''), request.form.get('id', '')
    con = nucleo.db()
    if tipo == 'cartao':
        if not con.execute("SELECT 1 FROM cartoes_painel WHERE chave=? AND tipo='conteudo'", (ident,)).fetchone():
            return _erro('Conteúdo não encontrado.', 404)
        con.execute('DELETE FROM cartao_conteudo WHERE chave=?', (ident,))
        con.execute('DELETE FROM cartoes_painel WHERE chave=?', (ident,))
    elif tipo == 'noticia':
        # A capa continua na biblioteca: outra publicação pode usá-la.
        con.execute('DELETE FROM noticias WHERE id=?', (nucleo._int(ident),))
    elif tipo == 'comunicado':
        r = con.execute('SELECT imagem,video FROM lateral WHERE id=?', (nucleo._int(ident),)).fetchone()
        if not r:
            return _erro('Conteúdo não encontrado.', 404)
        nucleo.remove_upload(r['imagem'])
        nucleo.remove_upload(r['video'])
        con.execute('DELETE FROM lateral WHERE id=?', (nucleo._int(ident),))
    else:
        return _erro('Tipo de conteúdo desconhecido.')
    con.commit()
    return jsonify(ok=True)


@app.route('/admin/conteudos/duplicar', methods=['POST'])
@nucleo.admin_obrigatorio
def conteudos_duplicar():
    tipo, ident = request.form.get('tipo', ''), request.form.get('id', '')
    con = nucleo.db()
    if tipo == 'cartao':
        nova = mc._duplica(con, ident)
        if not nova:
            return _erro('Este conteúdo não pode ser copiado.')
        con.commit()
        return jsonify(ok=True, id=nova)
    if tipo == 'noticia':
        r = con.execute('SELECT * FROM noticias WHERE id=?', (nucleo._int(ident),)).fetchone()
        if not r:
            return _erro('Conteúdo não encontrado.', 404)
        d = dict(r)
        d.pop('id')
        d.update(titulo=(d['titulo'] + ' (cópia)')[:200], estado='rascunho', publicar_em='', destaque=0,
                 slug=mn._slug_livre(con, mn.slugify(d['titulo'] + ' copia'), 0), ordem=mn._topo(con))
        cols = list(d)
        novo = con.execute(f"INSERT INTO noticias ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                           [d[k] for k in cols]).lastrowid
        con.commit()
        return jsonify(ok=True, id=novo)
    if tipo == 'comunicado':
        r = con.execute('SELECT * FROM lateral WHERE id=?', (nucleo._int(ident),)).fetchone()
        if not r:
            return _erro('Conteúdo não encontrado.', 404)
        d = dict(r)
        d.pop('id')
        d['titulo'] = ((d['titulo'] or 'Sem título') + ' (cópia)')[:200]
        d['ordem'] = con.execute('SELECT COALESCE(MAX(ordem),-1)+1 FROM lateral WHERE cartao=?',
                                 (d['cartao'],)).fetchone()[0]
        d['imagem'] = mc._copia_arquivo(d['imagem'])
        d['video'] = mc._copia_arquivo(d['video'])
        cols = list(d)
        novo = con.execute(f"INSERT INTO lateral ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                           [d[k] for k in cols]).lastrowid
        con.commit()
        return jsonify(ok=True, id=novo)
    return _erro('Tipo de conteúdo desconhecido.')
