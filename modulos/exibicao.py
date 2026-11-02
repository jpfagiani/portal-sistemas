"""Exibição pública e destino do clique: uma regra só para cartões, chamadas de
notícias e comunicados.

Dois mundos que não se misturam:

  administrativo  `nome_admin` (ou, nos cartões, `cartoes_painel.nome`). Só existe
                  no painel: listagem, busca, modo de edição. NUNCA vai ao HTML
                  público — nem como título, nem como texto alternativo, nem como
                  nome acessível de link.
  público         título, texto de apoio, imagem e texto alternativo, mostrados
                  conforme o modo escolhido (somente imagem / imagem e título /
                  imagem, título e texto de apoio).

Regra inegociável: título público vazio ou desligado = nenhum título. Não há
substituto (nome administrativo, chave, slug, nome de arquivo).

O destino do clique também tem uma regra só: interno (página do portal),
notícia interna ou endereço externo. Externo aceita apenas http e https; interno
é conferido contra as rotas reais; destino quebrado vira "sem link", nunca 404.
"""
import re
from urllib.parse import urlsplit

from markupsafe import Markup
from werkzeug.exceptions import NotFound
from werkzeug.routing import RequestRedirect

import app as nucleo
from . import noticias as mn

app = nucleo.app

# ── modos de apresentação ─────────────────────────────────────────────────────

MODOS = {
    'imagem': 'Somente imagem',
    'imagem_titulo': 'Imagem e título',
    'imagem_titulo_texto': 'Imagem, título e texto de apoio',
}
_FLAGS = {'imagem': (0, 0), 'imagem_titulo': (1, 0), 'imagem_titulo_texto': (1, 1)}


def flags_do_modo(modo):
    """(exibir_titulo, exibir_texto_apoio) de um modo; modo desconhecido = imagem e título."""
    return _FLAGS.get(modo, _FLAGS['imagem_titulo'])


def modo_das_flags(exibir_titulo, exibir_texto):
    if exibir_titulo and exibir_texto:
        return 'imagem_titulo_texto'
    return 'imagem_titulo' if exibir_titulo else 'imagem'


def modo_do_form(f, padrao):
    m = (f.get('modo') or '').strip()
    return m if m in MODOS else padrao


# ── destino do clique ─────────────────────────────────────────────────────────

TIPOS_DESTINO = {
    'padrao': 'Padrão do componente',
    'nenhum': 'Sem link',
    'interno': 'Página ou conteúdo do portal',
    'noticia': 'Notícia ou publicação do portal',
    'externo': 'Endereço externo (http ou https)',
}
_ESQUEMAS_LEGADO = ('http', 'https', 'mailto', 'tel')


class DestinoInvalido(ValueError):
    pass


def _esquema(url):
    m = re.match(r'^([a-z][a-z0-9+.\-]*):', url or '', re.I)
    return m.group(1).lower() if m else ''


def externo_valido(url):
    """http(s) com endereço de verdade. Rejeita javascript:, data:, vbscript:, //host e o resto."""
    url = (url or '').strip()
    if not url or _esquema(url) not in ('http', 'https'):
        return False
    p = urlsplit(url)
    return bool(p.netloc) and not re.search(r'[\s<>"\\\x00-\x1f]', url)


def interno_existe(caminho):
    """O caminho interno leva a algo que existe agora? Confere rota, notícia visível e página do menu."""
    caminho = (caminho or '').strip()
    if not caminho.startswith('/') or caminho.startswith('//') or '\\' in caminho:
        return False
    p = urlsplit(caminho)
    path = p.path
    if path.startswith('/admin') or path.startswith('/login'):
        return False
    try:
        endpoint, args = app.url_map.bind('localhost').match(path, method='GET')
    except RequestRedirect:
        return True
    except NotFound:
        return False
    except Exception:
        return False
    con = nucleo.db()
    if endpoint == 'noticia':
        return bool(con.execute(f'SELECT 1 FROM noticias WHERE slug=? AND {mn.VISIVEL}',
                                (args.get('slug', ''),)).fetchone())
    if endpoint == 'modulo':
        return bool(con.execute('SELECT 1 FROM paginas_lateral WHERE chave=?', (args.get('chave', ''),)).fetchone()
                    or con.execute('SELECT 1 FROM menu_itens WHERE chave=?', (args.get('chave', ''),)).fetchone())
    if endpoint == 'static':
        return False
    return True


def le_destino(f):
    """Lê o destino do formulário e valida NO SERVIDOR.

    Devolve (tipo, url, nova_aba); levanta DestinoInvalido com mensagem pronta.
    Campos: destino_tipo, destino_interno, destino_noticia, destino_externo, nova_aba.
    """
    tipo = (f.get('destino_tipo') or '').strip()
    if not tipo and (f.get('url') or '').strip():
        # Cliente antigo: só mandava `url`. O tipo sai do endereço e passa pela MESMA validação.
        url = f['url'].strip()
        interno = url.startswith('/') and not url.startswith('//')
        f = {'destino_tipo': 'interno' if interno else 'externo', 'destino_interno': url,
             'destino_externo': url, 'nova_aba': f.get('nova_aba')}
        tipo = f['destino_tipo']
    tipo = tipo or 'padrao'
    if tipo not in TIPOS_DESTINO:
        raise DestinoInvalido('Tipo de destino desconhecido.')
    nova = 1 if f.get('nova_aba') else 0
    if tipo in ('padrao', 'nenhum'):
        return tipo, '', nova
    if tipo == 'externo':
        url = (f.get('destino_externo') or '').strip()
        if not externo_valido(url):
            raise DestinoInvalido('Endereço externo inválido: use um endereço completo começando com http:// ou https://.')
        return tipo, url[:500], nova
    campo = 'destino_interno' if tipo == 'interno' else 'destino_noticia'
    url = (f.get(campo) or '').strip()
    if not url.startswith('/') or url.startswith('//'):
        raise DestinoInvalido('Escolha uma página ou notícia da lista do portal.')
    if tipo == 'noticia' and not url.startswith('/noticias/'):
        raise DestinoInvalido('Escolha uma notícia da lista.')
    if not interno_existe(url):
        raise DestinoInvalido('O destino escolhido não existe ou não está publicado.')
    return tipo, url[:500], nova


def resolve(tipo, url, nova_aba, padrao=''):
    """Destino pronto para o HTML público: dict(href, nova_aba, rel, quebrado).

    `tipo` vazio é registro antigo (anterior à migração): o tipo sai do próprio
    endereço e os esquemas mailto/tel, aceitos antes, continuam valendo.
    `nova_aba` -1 também é antigo: externo abre em nova aba, interno na mesma.
    Destino que não existe mais não vira link (nada de 404 para o visitante).
    """
    tipo, url = (tipo or ''), (url or '').strip()
    legado = tipo == ''
    if legado:
        tipo = 'padrao' if not url else ('interno' if url.startswith('/') else 'externo')
    href, quebrado = '', False
    if tipo == 'padrao':
        href = padrao or ''
    elif tipo == 'nenhum':
        href = ''
    elif tipo in ('interno', 'noticia'):
        if interno_existe(url):
            href = url
        else:
            quebrado = bool(url)
    elif tipo == 'externo':
        if externo_valido(url) or (legado and _esquema(url) in _ESQUEMAS_LEGADO and not url.startswith('//')):
            href = url
        else:
            quebrado = bool(url)
    externo = bool(href) and not href.startswith('/')
    if nova_aba is None or nova_aba == -1:
        nova = externo and _esquema(href) in ('http', 'https')
    else:
        nova = bool(nova_aba) and bool(href)
    return {'href': href, 'nova_aba': nova, 'rel': 'noopener noreferrer' if nova else '', 'quebrado': quebrado,
            'tipo': tipo}


# ── item público ──────────────────────────────────────────────────────────────

def monta(*, exibir_titulo, titulo, exibir_texto, texto, imagem='', alt='', destino=None, html=''):
    """A única regra de exibição. Tudo o que o HTML público usa sai daqui."""
    titulo = (titulo or '').strip()
    texto = (texto or '').strip()
    mostrar_titulo = bool(exibir_titulo) and bool(titulo)
    mostrar_texto = bool(exibir_texto) and bool(texto)
    alt = (alt or '').strip()
    destino = destino or {'href': '', 'nova_aba': False, 'rel': '', 'quebrado': False, 'tipo': 'nenhum'}
    # Nome acessível de um link só de imagem: o texto alternativo — nunca o nome administrativo.
    rotulo = titulo if mostrar_titulo else (alt or 'Abrir')
    return {
        'modo': modo_das_flags(exibir_titulo, exibir_texto),
        'mostrar_titulo': mostrar_titulo, 'titulo': titulo if mostrar_titulo else '',
        'mostrar_texto': mostrar_texto, 'texto': texto if mostrar_texto else '',
        'imagem': imagem or '', 'alt': alt, 'html': html,
        'href': destino['href'], 'nova_aba': destino['nova_aba'], 'rel': destino['rel'],
        'destino_quebrado': destino['quebrado'], 'rotulo': rotulo,
    }


def _ligado(r, campo, padrao):
    try:
        v = r[campo]
    except (KeyError, IndexError):
        return padrao
    return bool(v) if v is not None else padrao


def _campo(r, campo, padrao=''):
    try:
        v = r[campo]
    except (KeyError, IndexError):
        return padrao
    return padrao if v is None else v


def publico_cartao(chave):
    """Cartão de texto e imagem (tipo 'conteudo'). Nunca usa `cartoes_painel.nome`."""
    r = nucleo.db().execute('SELECT * FROM cartao_conteudo WHERE chave=?', (chave,)).fetchone()
    if not r:
        return monta(exibir_titulo=0, titulo='', exibir_texto=0, texto='')
    html = Markup(nucleo.agrupa_figuras(nucleo.limpa_html(r['html'])))
    return monta(exibir_titulo=_ligado(r, 'exibir_titulo', False), titulo=_campo(r, 'titulo_publico'),
                 exibir_texto=_ligado(r, 'exibir_texto_apoio', False), texto=_campo(r, 'texto_apoio'),
                 imagem=_campo(r, 'imagem'), alt=_campo(r, 'alt_imagem'),
                 destino=resolve(_campo(r, 'destino_tipo'), _campo(r, 'url'), _campo(r, 'nova_aba', -1)),
                 html=html)


def publico_noticia(n):
    """Chamada de notícia. O título editorial da notícia é conteúdo público por natureza;
    o `nome_admin` nunca entra."""
    padrao = '/noticias/' + n['slug']
    return monta(exibir_titulo=_ligado(n, 'exibir_titulo', True), titulo=n['titulo'],
                 exibir_texto=_ligado(n, 'exibir_texto_apoio', False), texto=n['resumo'] or n['subtitulo'],
                 imagem=n['capa'], alt=n['capa_alt'] or '',
                 destino=resolve(_campo(n, 'destino_tipo'), n['destino_url'], _campo(n, 'nova_aba', -1), padrao=padrao))


def publico_comunicado(c):
    """Item de comunicado: título e texto são os públicos; `nome_admin` nunca entra."""
    return monta(exibir_titulo=_ligado(c, 'exibir_titulo', True), titulo=_campo(c, 'titulo'),
                 exibir_texto=_ligado(c, 'exibir_texto_apoio', True), texto=_campo(c, 'conteudo'),
                 imagem=_campo(c, 'imagem'), alt=_campo(c, 'alt_imagem'),
                 destino=resolve(_campo(c, 'destino_tipo'), _campo(c, 'url'), _campo(c, 'nova_aba', -1)))


def destino_comunicado(c):
    return resolve(_campo(c, 'destino_tipo'), _campo(c, 'url'), _campo(c, 'nova_aba', -1))


app.jinja_env.globals['cartao_publico'] = publico_cartao
app.jinja_env.globals['noticia_publico'] = publico_noticia
app.jinja_env.globals['comunicado_publico'] = publico_comunicado
app.jinja_env.globals['destino_comunicado'] = destino_comunicado
app.jinja_env.globals['MODOS_EXIBICAO'] = MODOS
app.jinja_env.globals['TIPOS_DESTINO'] = TIPOS_DESTINO


# ── validação comum de salvamento ─────────────────────────────────────────────

def confere_modo(modo, tem_imagem, alt):
    """Regras do modo no servidor. Somente imagem exige imagem e texto alternativo."""
    if modo == 'imagem':
        if not tem_imagem:
            raise DestinoInvalido('“Somente imagem” precisa de uma imagem: escolha uma ou mude a apresentação.')
        if not (alt or '').strip():
            raise DestinoInvalido('Informe o texto alternativo da imagem (descreve a imagem para quem não a vê).')


def destinos_noticias(limite=60):
    """Notícias visíveis, para a lista de destino (nome, caminho)."""
    return [(r['titulo'], f"/noticias/{r['slug']}") for r in nucleo.db().execute(
        f'SELECT titulo,slug FROM noticias WHERE {mn.VISIVEL} ORDER BY id DESC LIMIT ?', (limite,))]


def destinos_paginas():
    """Páginas do portal (sem as notícias, que têm lista própria)."""
    return [(n, e) for n, e in nucleo.destinos_de_links() if not e.startswith('/noticias/')]
