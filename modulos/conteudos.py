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
import re
import secrets
from datetime import datetime

from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
from markupsafe import Markup, escape

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
                          atualizado='', ordem=r['ordem'], onde=nomes.get(r['cartao'], r['cartao']),
                          cartao=r['cartao']))
    for n in con.execute(f'SELECT * FROM noticias ORDER BY {mn.ORDEM}'):
        s = mn.situacao(n)
        chave = {'Publicada': 'publicado', 'Agendada': 'agendado', 'Rascunho': 'rascunho',
                 'Arquivado': 'arquivado'}.get(s, n['estado'])
        saida.append(dict(tipo='noticia', id=n['id'], titulo=n['titulo'], extra=n['categoria'] or '',
                          situacao=chave, atualizado=(n['atualizado_em'] or '')[:16], ordem=n['ordem'],
                          onde='Últimas notícias', destaque=bool(n['destaque']), slug=n['slug']))
    return saida


def _acao_cartao():
    """Ações sobre os cartões da página inicial, feitas na própria tela de Conteúdos."""
    con = nucleo.db()
    acao = request.form.get('acao')
    chave = request.form.get('cartao') or ''
    if acao == 'novo_cartao':
        nova = nucleo._proxima_chave_cartao(con)
        ordem = con.execute('SELECT COALESCE(MAX(ordem),0)+1 FROM cartoes_painel').fetchone()[0]
        con.execute("INSERT INTO cartoes_painel (chave,nome,icone,regiao,largura,coluna,ordem,tipo,ativo)"
                    " VALUES (?,?,'prancheta','baixo',1,0,?,'itens',1)",
                    (nova, 'Cartão ' + nova.replace('cartao', ''), ordem))
        nucleo._semear_aparencia(con, nova)
        con.commit()
        flash('Cartão criado. Arraste-o no Mapa do painel para posicioná-lo.', 'ok')
        return redirect(url_for('conteudos', tipo='comunicado', cartao=nova))
    if acao == 'aparencia_cartao':
        nucleo.salvar_aparencia_cartao(chave or 'noticias')
        return redirect(_volta(url_for('conteudos')) + ('#c-' + chave if chave else ''))
    if not nucleo.cartao_por_chave(chave):
        abort(400)
    if acao == 'titulo_cartao':
        if request.form.get('tem_mostrar_nome'):
            mostrar = 1 if request.form.get('mostrar_nome') else 0
            if con.execute("SELECT 1 FROM cartoes_painel WHERE chave=? AND tipo='conteudo'", (chave,)).fetchone():
                con.execute('UPDATE cartao_conteudo SET titulo_visivel=? WHERE chave=?', (mostrar, chave))
            else:
                con.execute('INSERT OR REPLACE INTO config (chave,valor) VALUES (?,?)',
                            (chave + '_titulo_visivel', str(mostrar)))
            con.commit()
        if (request.form.get('titulo_cartao') or '').strip():
            nucleo.salvar_nome_cartao_painel(chave)
        else:
            flash('O nome do cartão não pode ficar em branco.', 'erro')
    elif acao == 'excluir_cartao':
        itens = con.execute("SELECT COUNT(*) FROM cartoes_painel WHERE tipo='itens'").fetchone()[0]
        if not con.execute("SELECT 1 FROM cartoes_painel WHERE chave=? AND tipo='itens'", (chave,)).fetchone():
            flash('Só cartões de comunicados podem ser excluídos aqui.', 'erro')
        elif itens <= 1:
            flash('Este é o último cartão de comunicados — crie outro antes de excluí-lo.', 'erro')
        else:
            for linha in con.execute('SELECT imagem, video FROM lateral WHERE cartao=?', (chave,)):
                nucleo.remove_upload(linha['imagem'])
                nucleo.remove_upload(linha['video'])
            con.execute('DELETE FROM lateral WHERE cartao=?', (chave,))
            con.execute("DELETE FROM cartoes_painel WHERE chave=? AND tipo='itens'", (chave,))
            con.commit()
            flash('Cartão e itens removidos.', 'ok')
        return redirect(url_for('conteudos') + '#cartoes')
    return redirect(url_for('conteudos') + '#c-' + chave)


@app.route('/admin/conteudos', methods=['GET', 'POST'])
@nucleo.admin_obrigatorio
def conteudos():
    if request.method == 'POST':
        return _acao_cartao()
    q = (request.args.get('q') or '').strip()
    tipo = request.args.get('tipo') if request.args.get('tipo') in TIPOS else ''
    sit = request.args.get('situacao') if request.args.get('situacao') in SITUACOES else ''
    cartao = request.args.get('cartao') or ''
    cartao = cartao if (tipo == 'comunicado' and nucleo.cartao_por_chave(cartao)) else ''
    linhas = [l for l in _linhas()
              if (not tipo or l['tipo'] == tipo) and (not sit or l['situacao'] == sit)
              and (not cartao or l.get('cartao') == cartao)
              and (not q or _casa(l['titulo'], q) or _casa(l['extra'], q))]
    for l in linhas:
        l['rotulo_tipo'] = TIPOS[l['tipo']]
        l['rotulo_situacao'] = SITUACOES.get(l['situacao'], l['situacao'])
    cartoes_itens = [c for c in nucleo.cartoes_do_painel() if c['tipo'] == 'itens']
    return render_template('admin_conteudos.html', linhas=linhas, tipos=TIPOS, situacoes=SITUACOES,
                           filtro_tipo=tipo, filtro_sit=sit, q=q, cartoes_itens=cartoes_itens,
                           ordenavel=((tipo == 'noticia' or (tipo == 'comunicado' and cartao)) and not sit and not q),
                           url_ordenar=url_for('conteudos_ordenar', tipo=tipo, cartao=cartao or None),
                           filtro_cartao=cartao, cartoes=nucleo.cartoes_para_gerenciar(),
                           fontes=nucleo.FONTES_TEXTO, noticias_vitrine=mn.vitrine())


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
        m = con.execute('SELECT materia_titulo,materia_html FROM cartao_conteudo WHERE chave=?', (ident,)).fetchone()
        return dict(id=r['chave'], titulo=r['nome'], corpo=nucleo.limpa_html(r['html']),
                    titulo_visivel=bool(r['titulo_visivel']), url=r['url'] or '',
                    materia_titulo=m['materia_titulo'], materia=nucleo.limpa_html(m['materia_html']))
    if tipo == 'noticia':
        r = con.execute('SELECT * FROM noticias WHERE id=?', (nucleo._int(ident),)).fetchone()
        if not r:
            return None
        d = dict(r)
        d['corpo'] = nucleo.limpa_html(d['corpo'])
        d['url'] = d['destino_url']
        d['publicar_em_campo'] = mn._para_campo(d['publicar_em'])
        d['situacao'] = mn.situacao(r)
        d['ordem_pos'] = [x[0] for x in con.execute(f'SELECT id FROM noticias ORDER BY {mn.ORDEM}')].index(r['id']) + 1
        return d
    if tipo == 'comunicado':
        r = con.execute('SELECT * FROM lateral WHERE id=?', (nucleo._int(ident),)).fetchone()
        if not r:
            return None
        d = dict(r)
        d['corpo'] = nucleo.limpa_html(d['corpo_html']) if d.get('corpo_html') else _corpo_legado(d)
        d['materia'] = nucleo.limpa_html(d.get('materia_html') or '')
        return d
    return None


def _corpo_legado(d):
    """Item antigo (título, texto simples, imagem) vira o corpo do editor rico, para ser editado como os demais."""
    from markupsafe import escape
    partes = []
    if d.get('imagem'):
        partes.append('<p><img src="/static/uploads/%s" alt=""></p>' % escape(d['imagem']))
    if (d.get('titulo') or '').strip():
        partes.append('<p><strong>%s</strong></p>' % escape(d['titulo'].strip()))
    for linha in (d.get('conteudo') or '').splitlines():
        partes.append('<p>%s</p>' % escape(linha) if linha.strip() else '')
    return nucleo.limpa_html(''.join(partes))


def _valores_novos(tipo):
    if tipo == 'cartao':
        return dict(id='', titulo='', corpo='', titulo_visivel=False, url='', materia_titulo='', materia='')
    if tipo == 'noticia':
        return dict(id='', titulo='', subtitulo='', resumo='', corpo='', capa='', capa_alt='', legenda='',
                    categoria='', so_pagina=0, estado='rascunho', publicar_em_campo='', destaque=0, url='', meta='',
                    slug='', titulo_fonte='', titulo_cor='', titulo_tam='', situacao='Rascunho',
                    chamada_titulo='', chamada_resumo='', chamada_imagem='', chamada_legenda='', chamada_alt='',
                    chamada_formato='', chamada_visivel=1, chamada_credito='', chamada_posicao='', capa_credito='', ordem_pos=1)
    return dict(id='', titulo='', conteudo='', corpo='', corpo_html='', materia_titulo='', materia='', url='', url_rot='', imagem='', video='', img_pos='topo',
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
        estados=mn.ESTADOS, formatos=mn.FORMATOS, posicoes=mn.POSICOES, total_noticias=nucleo.db().execute('SELECT COUNT(*) FROM noticias').fetchone()[0], categorias=mn.categorias(), fontes=nucleo.FONTES_TEXTO,
        destinos_links=nucleo.destinos_de_links(), destaques=nucleo.DESTAQUES_COMUNICADO,
        img_pos=nucleo.CARTAO_IMG_POS, paleta=nucleo.PALETA,
        cartoes_itens=[c for c in nucleo.cartoes_do_painel() if c['tipo'] == 'itens'])


# ── salvamento (um serviço por tipo) ──────────────────────────────────────────

class Invalido(Exception):
    pass


def _salva_cartao(f, ident):
    con = nucleo.db()
    nome = f.get('titulo', '').strip()[:80]
    atual = con.execute('SELECT * FROM cartao_conteudo WHERE chave=?', (ident,)).fetchone() if ident else None
    if atual and 'corpo' not in f:                   # salvamento parcial (só a matéria): a chamada fica como está
        html, visivel, url = atual['html'], atual['titulo_visivel'], atual['url']
    else:
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
    # Matéria completa: só grava o que veio no formulário (a chamada e a matéria são independentes).
    if 'materia' in f:
        con.execute('UPDATE cartao_conteudo SET materia_html=? WHERE chave=?', (nucleo.limpa_html(f['materia']), chave))
    if 'materia_titulo' in f:
        con.execute('UPDATE cartao_conteudo SET materia_titulo=? WHERE chave=?', (f.get('materia_titulo', '').strip()[:200], chave))
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


def _imagem_chamada(f, atual):
    """Imagem exclusiva da chamada: enviada, escolhida na biblioteca ou removida. Sem pedido, fica como está."""
    arq = request.files.get('chamada_arquivo')
    try:
        if arq and arq.filename:
            img = midia._salva_imagem(arq)
            midia.registrar_arquivo(img, arq.filename, os.path.getsize(midia._caminho(img)))
            return img
        escolhida = os.path.basename(f.get('chamada_biblioteca', '') or '')
        if escolhida and midia.registrada(escolhida):
            return escolhida
    except ValueError as e:
        raise Invalido(str(e))
    return '' if f.get('remover_chamada_imagem') else atual


def _salva_noticia(f, ident):
    """Grava a notícia. A chamada (página principal) e a matéria completa são independentes: um campo que não
    veio no formulário NÃO é alterado, e as caixas de marcar só valem quando o bloco que as contém foi enviado."""
    con = nucleo.db()
    atual = con.execute('SELECT * FROM noticias WHERE id=?', (ident,)).fetchone() if ident else None
    if ident and not atual:
        raise Invalido('Notícia não encontrada.')
    old = dict(atual) if atual else {}

    def texto(nome, limite, padrao=''):
        if nome in f:
            return f.get(nome, '').strip()[:limite]
        return old.get(nome, padrao)

    acao = f.get('acao', 'salvar')
    titulo = texto('titulo', 200)
    if not titulo:
        raise Invalido('Informe o título da matéria.')
    # Salvar nunca publica sozinho: só o botão Publicar (ou a situação escolhida).
    estado = f.get('estado') if f.get('estado') in mn.ESTADOS else old.get('estado', 'rascunho')
    if acao == 'rascunho':
        estado = 'rascunho'
    elif acao == 'publicar':
        estado = 'publicado'
    publicar_em = mn._para_banco(f.get('publicar_em')) if 'publicar_em' in f else old.get('publicar_em', '')
    if estado == 'publicado' and not publicar_em:
        publicar_em = _agora()
    d = dict(
        titulo=titulo, subtitulo=texto('subtitulo', 300), resumo=texto('resumo', 600),
        corpo=nucleo.limpa_html(f['corpo']) if 'corpo' in f else old.get('corpo', ''),
        capa=_capa_noticia(f, old.get('capa', '')), capa_alt=texto('capa_alt', 300), legenda=texto('legenda', 300),
        categoria=texto('categoria', 60), estado=estado, publicar_em=publicar_em,
        destino_url=nucleo.endereco_seguro(f['url']) if 'url' in f else old.get('destino_url', ''),
        meta=texto('meta', 300),
        chamada_titulo=texto('chamada_titulo', 200), chamada_resumo=texto('chamada_resumo', 300),
        chamada_legenda=texto('chamada_legenda', 300), chamada_alt=texto('chamada_alt', 300),
        chamada_credito=texto('chamada_credito', 200), capa_credito=texto('capa_credito', 200),
        chamada_imagem=_imagem_chamada(f, old.get('chamada_imagem', '')))
    fmt = f.get('chamada_formato') if 'chamada_formato' in f else old.get('chamada_formato', '')
    d['chamada_formato'] = fmt if fmt in mn.FORMATOS else ''
    pos = f.get('chamada_posicao') if 'chamada_posicao' in f else old.get('chamada_posicao', '')
    d['chamada_posicao'] = pos if pos in mn.POSICOES else ''
    if any(k in f for k in ('titulo_fonte', 'titulo_cor', 'titulo_tam')):
        d['titulo_fonte'], d['titulo_cor'], d['titulo_tam'] = mn._titulo_do_form(f)
    if f.get('tem_organizacao'):                    # caixas de marcar: só valem se o bloco foi enviado
        d['destaque'] = 1 if f.get('em_destaque') else 0
        d['so_pagina'] = 1 if f.get('so_pagina') else 0
        d['chamada_visivel'] = 1 if f.get('chamada_visivel') else 0
    d['slug'] = mn._slug_livre(con, mn.slugify(f.get('slug') or old.get('slug') or titulo), ident or 0)
    if atual:
        if d.get('destaque') and not old.get('destaque'):
            con.execute('UPDATE noticias SET ordem=? WHERE id=?', (mn._topo(con), ident))
        con.execute('UPDATE noticias SET ' + ','.join(k + '=?' for k in d)
                    + ",atualizado_em=datetime('now','localtime') WHERE id=?", list(d.values()) + [ident])
        novo = ident
    else:
        d.setdefault('chamada_visivel', 1)
        d['autor'] = session.get('nome') or session.get('user', '')
        d['ordem'] = mn._topo(con)
        novo = con.execute('INSERT INTO noticias (' + ','.join(d) + ') VALUES (' + ','.join('?' * len(d)) + ')',
                           list(d.values())).lastrowid
    # Ordem escolhida (1 = primeira): só se o campo veio e mudou; as demais notícias apenas se deslocam.
    if f.get('ordem_pos', '').strip().isdigit() and f.get('ordem_pos') != f.get('ordem_pos_orig', ''):
        ids = [r[0] for r in con.execute(f'SELECT id FROM noticias WHERE id<>? ORDER BY {mn.ORDEM}', (novo,))]
        ids.insert(max(0, min(len(ids), int(f['ordem_pos']) - 1)), novo)
        for posicao, ident_n in enumerate(ids):
            con.execute('UPDATE noticias SET ordem=? WHERE id=?', (posicao, ident_n))
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
    atu = dict(atuais) if atuais else {}
    corpo = nucleo.limpa_html(f.get('corpo', ''))
    urg = f.get('urgencia', 'informacao')
    dest = f.get('destaque', 'nenhum')
    url = nucleo.endereco_seguro(f.get('url', ''))
    titulo = f.get('titulo', '').strip()[:200]
    if not (nucleo.so_texto(corpo) or '<img' in corpo or url):
        raise Invalido('Escreva o texto, coloque uma imagem ou informe o endereço do link.')
    # O texto simples acompanha o corpo: listas, busca e impressão ainda o usam.
    texto = '\n'.join(l for l in nucleo.so_texto(re.sub(r'</(p|div|h\d|li)>', '\n', corpo)).splitlines() if l.strip())
    dados = (atu.get('tipo', 'aviso'), titulo, texto, url, 1 if f.get('ativo') else 0,
             urg if urg in ('urgente', 'comunicado', 'informacao') else 'informacao',
             dest if dest in nucleo.DESTAQUES_COMUNICADO else 'nenhum',
             atu.get('titulo_tam', ''), atu.get('titulo_cor', ''), atu.get('texto_tam', ''), atu.get('texto_cor', ''),
             atu.get('fundo_cor', ''), atu.get('data', ''), atu.get('imagem', ''), atu.get('video', ''),
             atu.get('url_rot', ''), atu.get('img_pos', 'topo'), corpo)
    campos = ('tipo,titulo,conteudo,url,ativo,urgencia,destaque,titulo_tam,titulo_cor,texto_tam,texto_cor,'
              'fundo_cor,data,imagem,video,url_rot,img_pos,corpo_html').split(',')
    if atuais:
        con.execute('UPDATE lateral SET ' + ','.join(k + '=?' for k in campos) + ' WHERE id=?', dados + (ident,))
        novo = ident
    else:
        ordem = con.execute('SELECT COALESCE(MAX(ordem),-1)+1 FROM lateral WHERE cartao=?', (chave,)).fetchone()[0]
        novo = con.execute('INSERT INTO lateral (' + ','.join(campos) + ',ordem,cartao) VALUES ('
                           + ','.join('?' * (len(campos) + 2)) + ')', dados + (ordem, chave)).lastrowid
    if 'materia' in f:
        con.execute('UPDATE lateral SET materia_html=? WHERE id=?', (nucleo.limpa_html(f['materia']), novo))
    if 'materia_titulo' in f:
        con.execute('UPDATE lateral SET materia_titulo=? WHERE id=?', (f.get('materia_titulo', '').strip()[:200], novo))
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
    contexto = dict(tipo=tipo, titulo=f.get('titulo', '').strip(), corpo=Markup(nucleo.agrupa_figuras(nucleo.limpa_html(f.get('corpo', '')))),
                    materia_titulo=f.get('materia_titulo', '').strip(),
                    materia_corpo=Markup(nucleo.agrupa_figuras(nucleo.limpa_html(f.get('materia', '')))))
    if tipo == 'cartao':
        contexto.update(titulo_visivel=bool(f.get('titulo_visivel')))
    elif tipo == 'noticia':
        capa, r = '', None
        if ident:
            r = nucleo.db().execute('SELECT capa,chamada_imagem FROM noticias WHERE id=?', (nucleo._int(ident),)).fetchone()
            capa = r['capa'] if r else ''
        escolhida = os.path.basename(f.get('imagem_biblioteca', '') or '')
        if escolhida and midia.registrada(escolhida):
            capa = escolhida
        if f.get('remover_imagem'):
            capa = ''
        if f.get('imagem_nova') and not capa:
            capa = 'pendente'
        cham = r['chamada_imagem'] if r else ''
        escolhida_c = os.path.basename(f.get('chamada_biblioteca', '') or '')
        if escolhida_c and midia.registrada(escolhida_c):
            cham = escolhida_c
        if f.get('remover_chamada_imagem'):
            cham = ''
        arq_c = request.files.get('chamada_arquivo')
        if arq_c and arq_c.filename and not cham:
            cham = 'pendente'
        titulo_est = dict(zip(('titulo_fonte', 'titulo_cor', 'titulo_tam'), mn._titulo_do_form(f)))
        fmt = f.get('chamada_formato') if f.get('chamada_formato') in mn.FORMATOS else ''
        contexto['n'] = dict(
            titulo=f.get('titulo', '').strip(), resumo=f.get('resumo', ''), capa=capa or '', categoria=f.get('categoria', ''),
            chamada_titulo=f.get('chamada_titulo', '').strip(), chamada_resumo=f.get('chamada_resumo', '').strip(),
            chamada_imagem=cham or '', chamada_legenda=f.get('chamada_legenda', '').strip(),
            chamada_alt=f.get('chamada_alt', '').strip(), chamada_formato=fmt, slug='previa', destino_url='',
            chamada_credito=f.get('chamada_credito', '').strip(), **titulo_est)
        contexto['outras'] = nucleo.db().execute(
            f'SELECT * FROM noticias WHERE {mn.VISIVEL_LISTA} AND chamada_visivel=1 AND id<>? ORDER BY {mn.ORDEM} LIMIT 2',
            (nucleo._int(ident),)).fetchall()
        contexto['credito'] = f.get('capa_credito', '').strip()
        contexto['capa_pendente'] = bool(f.get('imagem_nova'))
        contexto['modelo'] = mn.vitrine()[0]
        contexto['formatos'] = mn.FORMATOS
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
        item['corpo_html'] = nucleo.limpa_html(f.get('corpo', ''))
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


@app.route('/admin/conteudos/ordenar', methods=['POST'])
@nucleo.admin_obrigatorio
def conteudos_ordenar():
    """Grava a ordem escolhida arrastando as linhas da lista (notícias ou comunicados)."""
    tipo = request.args.get('tipo', '')
    if tipo == 'noticia':
        ids = [int(x) for x in request.form.get('ids', '').split(',') if x.strip().isdigit()]
        if not ids:
            return ('', 400)
        mn._reordenar(nucleo.db(), ids)
        nucleo.db().commit()
        return ('', 204)
    if tipo == 'comunicado':
        return nucleo.reordenar('lateral')
    return ('', 400)


# ── página interna de um cartão ───────────────────────────────────────────────

# ── matéria completa de um cartão ou comunicado (página pública) ─────────────

@app.route('/materia/<tipo>/<ident>')
def materia(tipo, ident):
    """Página aberta pelo clique num cartão ou comunicado que tem matéria completa."""
    con = nucleo.db()
    if tipo == 'cartao':
        r = con.execute("SELECT p.nome AS nome,p.ativo AS ativo,k.materia_titulo AS mt,k.materia_html AS mh"
                        " FROM cartoes_painel p JOIN cartao_conteudo k ON k.chave=p.chave"
                        " WHERE p.chave=? AND p.tipo='conteudo'", (ident,)).fetchone()
    elif tipo == 'comunicado':
        r = con.execute('SELECT titulo AS nome,ativo,materia_titulo AS mt,materia_html AS mh FROM lateral WHERE id=?',
                        (nucleo._int(ident),)).fetchone()
    else:
        r = None
    if not r:
        abort(404)
    html = nucleo.limpa_html(r['mh'] or '')
    if not (nucleo.so_texto(html) or '<img' in html) or (not r['ativo'] and not session.get('admin')):
        abort(404)
    return render_template('materia.html', titulo=r['mt'] or r['nome'] or 'Matéria',
                           corpo=Markup(nucleo.agrupa_figuras(html)),
                           editar=url_for('conteudos_editor', tipo=tipo, ident=ident))


@app.route('/admin/conteudos/mover-para-materia', methods=['POST'])
@nucleo.admin_obrigatorio
def conteudos_mover_para_materia():
    """Passa o texto que está no cartão para a matéria completa; no cartão ficam as imagens e uma linha de chamada."""
    tipo, ident = request.form.get('tipo', ''), request.form.get('id', '')
    chamada_txt = request.form.get('chamada', '').strip()
    con = nucleo.db()
    if tipo == 'cartao':
        r = con.execute("SELECT p.nome,k.html,k.materia_html FROM cartoes_painel p JOIN cartao_conteudo k ON k.chave=p.chave"
                        " WHERE p.chave=? AND p.tipo='conteudo'", (ident,)).fetchone()
        corpo, mat, nome = (r['html'], r['materia_html'], r['nome']) if r else ('', '', '')
    elif tipo == 'comunicado':
        r = con.execute('SELECT * FROM lateral WHERE id=?', (nucleo._int(ident),)).fetchone()
        corpo = (r['corpo_html'] or _corpo_legado(dict(r))) if r else ''
        mat, nome = (r['materia_html'], r['titulo']) if r else ('', '')
    else:
        return _erro('Tipo de conteúdo desconhecido.')
    if not r:
        return _erro('Conteúdo não encontrado.', 404)
    if nucleo.so_texto(mat) or '<img' in (mat or ''):
        return _erro('Este cartão já tem matéria completa. Edite o bloco 2.')
    chamada = _so_chamada(corpo, chamada_txt or nome)
    if tipo == 'cartao':
        con.execute('UPDATE cartao_conteudo SET html=?,materia_html=?,materia_titulo=? WHERE chave=?',
                    (chamada, nucleo.limpa_html(corpo), nome[:200], ident))
    else:
        con.execute('UPDATE lateral SET corpo_html=?,materia_html=?,materia_titulo=? WHERE id=?',
                    (chamada, nucleo.limpa_html(corpo), (nome or '')[:200], nucleo._int(ident)))
    con.commit()
    return jsonify(ok=True)


def _so_chamada(corpo, texto):
    """Corpo reduzido para o cartão: as imagens e uma linha de chamada."""
    imagens = re.findall(r'<img\b[^>]*>', nucleo.limpa_html(corpo))
    return nucleo.limpa_html(''.join('<p>%s</p>' % i for i in imagens)
                             + '<p><strong>%s</strong></p>' % escape((texto or 'Saiba mais').strip()[:200]))


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
