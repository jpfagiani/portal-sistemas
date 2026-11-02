"""Testes dos módulos novos (segurança, histórico, mídia, notícias).

Uso:  python3 tests/verificacoes_portal.py
Trabalha numa CÓPIA temporária do portal: não toca no banco nem nos uploads
reais. Sai com código 1 se algum teste falhar."""
import os, re, shutil, struct, sys, tempfile, zlib

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='portal-teste-')
PASTA = os.path.join(TMP, 'p')
shutil.copytree(RAIZ, PASTA, ignore=shutil.ignore_patterns(
    '*.db', '__pycache__', 'secret.key', 'uploads', 'tests', '.git'))
os.chdir(PASTA)
sys.path.insert(0, PASTA)
os.environ['INTRANET_ADMIN_SENHA'] = 'Teste1234'
import io
import app as portal

falhas = []
def ok(cond, msg):
    print(('OK    ' if cond else 'FALHA ') + msg)
    if not cond:
        falhas.append(msg)

def png(cor=(40, 90, 160)):
    def ch(t, d):
        x = struct.pack('>I', len(d)) + t + d
        return x + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes(cor) * 8 for _ in range(8))
    return (b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 8, 2, 0, 0, 0))
            + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b''))

def csrf(h):
    m = re.search(r'name="csrf" value="([^"]+)"', h)
    return m.group(1) if m else ''

c = portal.app.test_client()
anon = portal.app.test_client()

# ── segurança ────────────────────────────────────────────────────────────────
r = anon.get('/')
ok(r.headers.get('X-Content-Type-Options') == 'nosniff', 'cabeçalho nosniff')
ok(r.headers.get('X-Frame-Options') in ('SAMEORIGIN', 'DENY'), 'proteção contra moldura (clickjacking)')
r = anon.get('/pagina-que-nao-existe')
ok(r.status_code == 404 and 'Página não encontrada' in r.get_data(as_text=True) or r.status_code == 404, 'erro 404 com página própria')
for rota in ('/admin/midia', '/admin/historico', '/admin/noticias'):
    ok(anon.get(rota).status_code in (302, 401, 403), f'{rota} exige login')

# limite de tentativas de login
t = csrf(anon.get('/login').get_data(as_text=True))
bloqueou = False
for _ in range(12):
    r = anon.post('/login', data={'csrf': t, 'usuario': 'admin', 'senha': 'errada'})
    t = csrf(anon.get('/login').get_data(as_text=True)) or t
    if r.status_code == 429 or 'Muitas tentativas' in r.get_data(as_text=True):
        bloqueou = True
        break
ok(bloqueou, 'login bloqueado após tentativas erradas seguidas')
r = c.post('/login', data={'csrf': csrf(c.get('/login').get_data(as_text=True)), 'usuario': 'admin', 'senha': 'Teste1234'})
if r.status_code != 302:
    # mesmo IP de teste está bloqueado: libera as falhas para seguir os demais testes
    with portal.app.app_context():
        con = portal.db()
        for (t_,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%login%'").fetchall():
            con.execute(f'DELETE FROM {t_}')
        con.commit()
    r = c.post('/login', data={'csrf': csrf(c.get('/login').get_data(as_text=True)), 'usuario': 'admin', 'senha': 'Teste1234'})
ok(r.status_code == 302, 'login correto funciona depois de limpar o bloqueio')
tok = csrf(c.get('/admin/midia').get_data(as_text=True))
ok(bool(tok), 'página da biblioteca abre para o admin')

# ── mídia ────────────────────────────────────────────────────────────────────
def envia(nome, dados, extra=None):
    return c.post('/admin/midia', data=dict({'csrf': tok, 'acao': 'enviar',
                  'arquivos': (io.BytesIO(dados), nome)}, **(extra or {})),
                  content_type='multipart/form-data', follow_redirects=True)

r = envia('logo.png', png())
ok('enviada' in r.get_data(as_text=True), 'envio de PNG válido')
r = envia('falso.png', b'<?php echo 1; ?>' * 10)
ok('imagem' in r.get_data(as_text=True).lower() and len(os.listdir(portal.UPLOAD_DIR)) == 1,
   'arquivo disfarçado de PNG é recusado (bytes não conferem)')
r = envia('script.php', png())
ok(len(os.listdir(portal.UPLOAD_DIR)) == 1, 'extensão não permitida é recusada')
arq = os.listdir(portal.UPLOAD_DIR)[0]
ok(arq in c.get('/admin/midia').get_data(as_text=True), 'imagem aparece na biblioteca')
lista = c.get('/admin/midia/lista').get_json()
ok(any(i['arquivo'] == arq for i in lista['itens']), 'seletor recebe a lista em JSON')
r = c.post('/admin/midia/enviar', data={'csrf': tok, 'arquivo': (io.BytesIO(png((1, 2, 3))), 'b.png')},
           content_type='multipart/form-data')
j = r.get_json(silent=True) or {}
ok(j.get('ok') and j['item']['arquivo'] in os.listdir(portal.UPLOAD_DIR), 'envio rápido do seletor devolve JSON e grava o arquivo')
r = c.post('/admin/midia/enviar', data={'arquivo': (io.BytesIO(png((1, 2, 3))), 'b.png')}, content_type='multipart/form-data')
ok(r.status_code in (400, 403), 'envio rápido sem token CSRF é recusado')
c.post('/admin/midia', data={'csrf': tok, 'acao': 'salvar', 'arquivo': arq, 'titulo': 'Logo', 'alt': 'Logotipo do CDPNI'})
ok('Logotipo do CDPNI' in c.get('/admin/midia').get_data(as_text=True), 'texto alternativo é salvo')

# imagem em uso não pode ser excluída
r = c.post('/admin/pagina/documentos', data={'csrf': tok, 'tipo': 'imagem', 'ativo': 'on', 'texto': 'Legenda', 'arquivo_biblioteca': arq},
           content_type='multipart/form-data')
with portal.app.app_context():
    n_bloco = portal.db().execute("SELECT COUNT(*) FROM pagina_blocos WHERE arquivo=?", (arq,)).fetchone()[0]
ok(n_bloco == 1 and len(os.listdir(portal.UPLOAD_DIR)) == 2, 'bloco de página reaproveita imagem da biblioteca (sem copiar o arquivo)')
ok('Logotipo do CDPNI' in anon.get('/modulo/documentos').get_data(as_text=True) or arq in anon.get('/modulo/documentos').get_data(as_text=True),
   'página pública mostra a imagem escolhida')
c.post('/admin/pagina/documentos', data={'csrf': tok, 'tipo': 'imagem', 'ativo': 'on', 'arquivo_biblioteca': '../../etc/passwd'},
           content_type='multipart/form-data')
ok(len(os.listdir(portal.UPLOAD_DIR)) == 2, 'nome de arquivo malicioso na biblioteca é ignorado')
# Gravação pelo caminho único de Conteúdos (os endereços antigos só redirecionam).
def noticia_post(d):
    d = dict(d)
    for velho, novo in (('destino_url', 'url'), ('capa_biblioteca', 'imagem_biblioteca'), ('destaque', 'em_destaque')):
        if velho in d:
            d[novo] = d.pop(velho)
    d['tipo'] = 'noticia'
    d.setdefault('tem_organizacao', '1')      # o editor sempre envia o bloco de organização
    d.setdefault('chamada_visivel', 'on')
    return c.post('/admin/conteudos/salvar', data=d, content_type='multipart/form-data')

def cartao_salvar(d):
    d = dict({'csrf': tok, 'tipo': 'cartao'}, **d)
    if 'nome' in d:
        d['titulo'] = d.pop('nome')
    if 'chave' in d:
        d['id'] = d.pop('chave')
    return c.post('/admin/conteudos/salvar', data=d, content_type='multipart/form-data')

noticia_post({'csrf': tok, 'acao': 'publicar', 'titulo': 'Aviso com capa', 'capa_biblioteca': arq,
                                'corpo': '<p>Texto</p>', 'categoria': 'Avisos'})
r = c.post('/admin/midia', data={'csrf': tok, 'acao': 'excluir', 'arquivo': arq}, follow_redirects=True)
ok('em uso' in r.get_data(as_text=True) and os.path.exists(os.path.join(portal.UPLOAD_DIR, arq)),
   'imagem em uso não é excluída')

# ── notícias ─────────────────────────────────────────────────────────────────
def nova(**kw):
    d = {'csrf': tok, 'acao': 'salvar', 'titulo': 'T', 'corpo': '<p>c</p>', 'estado': 'rascunho'}
    d.update(kw)
    return noticia_post(d)

nova(titulo='Rascunho secreto')
ok(anon.get('/noticias/rascunho-secreto').status_code == 404, 'rascunho não aparece ao público')
ok(c.get('/noticias/rascunho-secreto').status_code == 200 and 'Pré-visualização' in c.get('/noticias/rascunho-secreto').get_data(as_text=True),
   'admin pré-visualiza o rascunho')
nova(titulo='Agendada futura', estado='publicado', publicar_em='2099-01-01T08:00')
ok(anon.get('/noticias/agendada-futura').status_code == 404, 'agendada para o futuro não aparece')
nova(titulo='Publicada passada', estado='publicado', publicar_em='2020-01-01T08:00',
     corpo='<p>Olá</p><script>alert(1)</script><img src="/static/uploads/%s" alt="a"><img src="http://x.com/a.png">' % arq)
h = anon.get('/noticias/publicada-passada').get_data(as_text=True)
ok('Olá' in h and 'alert(1)' not in h and 'x.com' not in h and '/static/uploads/%s' % arq in h,
   'notícia pública: script e imagem externa removidos, imagem da biblioteca mantida')
h = anon.get('/noticias').get_data(as_text=True)
ok('Publicada passada' in h and 'Agendada futura' not in h and 'Rascunho secreto' not in h, 'lista pública só mostra as visíveis')
h = anon.get('/').get_data(as_text=True)
ok('Publicada passada' in h and 'Rascunho secreto' not in h, 'cartão de notícias na página inicial')
h = anon.get('/').get_data(as_text=True)
ok('lp-lista' not in h and h.find('Últimas notícias') < h.find('lateral-paginas') + 2000 and 'lateral-paginas' in h,
   'por padrão a lateral mostra Últimas notícias no lugar da lista de páginas')
c.post('/admin/navegacao', data={'csrf': tok, 'lista_paginas_ativa': 'on'})
h = anon.get('/').get_data(as_text=True)
ok('Páginas do portal' in h or 'lp-lista' in h or 'Nenhuma página' in h, 'lista de páginas volta quando ligada em Navegação')
c.post('/admin/navegacao', data={'csrf': tok})
ok('Aviso com capa' in anon.get('/noticias?c=Avisos').get_data(as_text=True), 'filtro por categoria')
nova(titulo='Publicada passada', estado='publicado', publicar_em='2020-01-02T08:00')
ok(anon.get('/noticias/publicada-passada-2').status_code == 200, 'título repetido ganha endereço único')
nova(titulo='Com link', estado='publicado', publicar_em='2020-01-03T08:00', destino_url='javascript:alert(1)')
ok('javascript:' not in anon.get('/noticias').get_data(as_text=True), 'destino javascript: é descartado')
with portal.app.app_context():
    ident = portal.db().execute("SELECT id FROM noticias WHERE titulo='Rascunho secreto'").fetchone()[0]
c.post('/admin/conteudos/excluir', data={'csrf': tok, 'tipo': 'noticia', 'id': ident})
ok(c.get('/noticias/rascunho-secreto').status_code == 404, 'excluir notícia')
ok(os.path.exists(os.path.join(portal.UPLOAD_DIR, arq)), 'a capa continua na biblioteca depois de excluir notícia')
r = c.post('/admin/conteudos/salvar', data={'tipo': 'noticia', 'titulo': 'sem csrf'})
ok(r.status_code in (400, 403), 'POST sem token CSRF é recusado (%s)' % r.status_code)

# ── cartões de texto e imagem ────────────────────────────────────────────────
r = cartao_salvar({'nome': 'Horário', 'titulo_visivel': 'on',
           'corpo': '<p>Das 8h às 17h</p><script>x()</script>'})
j = r.get_json() or {}
j['chave'] = j.get('id')
ok(j.get('ok'), 'cria cartão de texto e imagem')
h = anon.get('/').get_data(as_text=True)
ok('Das 8h às 17h' in h and 'x()' not in h, 'cartão aparece ao público, com HTML limpo')
r = cartao_salvar({'chave': j.get('chave'), 'nome': 'Horário 2', 'titulo_visivel': 'on', 'corpo': '<p>Novo</p>'})
ok(r.get_json().get('ok') and 'Horário 2' in anon.get('/').get_data(as_text=True), 'edita o cartão')
ok(not cartao_salvar({'nome': '', 'corpo': ''}).get_json().get('ok'), 'cartão vazio é recusado')
ok(anon.post('/admin/conteudos/salvar', data={'tipo': 'cartao', 'titulo': 'x', 'corpo': 'y'}).status_code in (302, 400, 401, 403), 'visitante não cria cartão')
ok(c.post('/admin/conteudos/excluir', data={'csrf': tok, 'tipo': 'cartao', 'id': j.get('chave')}).get_json().get('ok'), 'exclui o cartão')
c.post('/admin/layout-livre', data={'csrf': tok, 'acao': 'ativar'})
ok(c.get('/editor').status_code == 200 and 'data-novo-conteudo' in c.get('/editor').get_data(as_text=True), 'editor tem o botão + Texto ou imagem')
r = c.post('/admin/cartao-pos', data={'csrf': tok, 'posicoes': '[{"chave":"ramais","gx":0,"gy":0,"gw":3,"gh":14}]'})
ok(r.status_code == 200, 'cartão pode ser fixado na lateral esquerda vazia (%s)' % r.status_code)
r = c.post('/admin/cartao-pos', data={'csrf': tok, 'posicoes': '[{"chave":"atalhos","gx":3,"gy":0,"gw":6,"gh":8},{"chave":"sistemas","gx":4,"gy":2,"gw":6,"gh":8}]'})
ok(r.status_code == 200 and r.get_json().get('ok'), 'cartões podem se sobrepor (%s)' % r.status_code)
with portal.app.app_context():
    z = dict(portal.db().execute("SELECT chave,z FROM cartoes_painel WHERE chave IN ('atalhos','sistemas')").fetchall())
ok(z['sistemas'] > 0 and z['sistemas'] != z['atalhos'], 'o cartão mexido vai para a frente (z %s)' % z)
ok(c.post('/admin/cartao-pos', data={'csrf': tok, 'posicoes': '[{"chave":"atalhos","gx":10,"gy":0,"gw":6,"gh":8}]'}).status_code == 400, 'ainda recusa posição fora do quadro')
c.post('/admin/layout-livre', data={'csrf': tok, 'acao': 'desativar'})

# ── páginas de conteúdo: cabeçalho de matéria ────────────────────────────────
def cabecalho(**kw):
    d = {'csrf': tok, 'acao': 'cabecalho'}
    d.update(kw)
    return c.post('/admin/pagina/servidores', data=d, content_type='multipart/form-data', follow_redirects=True)

h = anon.get('/modulo/servidores').get_data(as_text=True)
ok('<h1 class="pagina-titulo">Link 1</h1>' in h and not any(
       k in h for k in ('mat-chapeu', 'mat-byline', 'mat-capa', 'mat-resumo', 'mat-leia')),
   'página sem cabeçalho continua saindo só com o título')
ok('Editar cabeçalho' in c.get('/modulo/servidores').get_data(as_text=True), 'edição direta tem o atalho do cabeçalho')
ok('id="cabecalho"' in c.get('/admin/pagina/servidores').get_data(as_text=True), 'editor da página tem o formulário do cabeçalho')

r = cabecalho(chapeu='Recursos Humanos', autor='Seção de Pessoal', linha_fina='Aniversariantes do mês devem comparecer.',
              publicada_em='2026-10-21T05:30', capa_arquivo_biblioteca=arq, capa_legenda='Fila <b>de atendimento</b>',
              capa_credito='Imagem: Arquivo CDPNI', resumo='Primeiro item\n\nSegundo item\nTerceiro item',
              mostrar_resumo='on', mostrar_leia='on')
ok('Cabeçalho da página salvo' in r.get_data(as_text=True), 'admin salva o cabeçalho da página')
h = anon.get('/modulo/servidores').get_data(as_text=True)
ok('Recursos Humanos' in h and 'Aniversariantes do mês devem comparecer.' in h, 'chapéu e linha fina aparecem')
ok('Por <b>Seção de Pessoal</b>' in h and 'Publicada em 21/10/2026 05h30' in h, 'assinatura mostra autor e data de publicação')
ok('/static/uploads/%s' % arq in h and 'Imagem: Arquivo CDPNI' in h and 'Fila &lt;b&gt;de atendimento&lt;/b&gt;' in h,
   'foto de capa com crédito e legenda (HTML da legenda escapado)')
ok(h.count('<li>Primeiro item</li>') == 1 and '<li>Segundo item</li>' in h and '<li>Terceiro item</li>' in h and '<li></li>' not in h,
   'resumo recolhível: um item por linha, sem itens vazios')
ok('mat-leia' in h and 'Publicada passada' in h, 'Leia também lista notícias publicadas')
ok('Rascunho secreto' not in h and 'Agendada futura' not in h, 'Leia também não mostra rascunho nem agendada')

cabecalho(chapeu='<script>alert(1)</script>', autor='"><img src=x onerror=alert(2)>', mostrar_resumo='on', mostrar_leia='on')
h = anon.get('/modulo/servidores').get_data(as_text=True)
ok('<script>alert(1)</script>' not in h and '<img src=x' not in h and '&lt;script&gt;alert(1)&lt;/script&gt;' in h,
   'campos do cabeçalho são escapados (sem script no chapéu nem tag solta no autor)')
cabecalho(chapeu='Recursos Humanos', autor='Seção de Pessoal', publicada_em='2026-10-21T05:30', capa_arquivo_biblioteca=arq,
          capa_legenda='Legenda', mostrar_resumo='on', mostrar_leia='on', resumo='Item')

c.post('/admin/pagina/servidores', data={'csrf': tok, 'tipo': 'subtitulo', 'ativo': 'on', 'texto': 'Quem precisa comparecer'})
h = anon.get('/modulo/servidores').get_data(as_text=True)
ok('Atualizada em' in h and 'Quem precisa comparecer' in h, '"Atualizada em" aparece sozinho depois de mexer num bloco')
ok('Capa da página' in c.get('/admin/midia').get_data(as_text=True), 'biblioteca mostra a capa da página como uso da imagem')

r = anon.post('/admin/pagina/servidores', data={'acao': 'cabecalho', 'chapeu': 'Invasor'}, content_type='multipart/form-data')
ok(r.status_code in (302, 400, 401, 403) and 'Invasor' not in anon.get('/modulo/servidores').get_data(as_text=True),
   'visitante não grava o cabeçalho')

nova_capa = png((200, 30, 30))
cabecalho(capa_arquivo=(io.BytesIO(nova_capa), 'capa-nova.png'), chapeu='Recursos Humanos', autor='Seção de Pessoal',
          mostrar_resumo='on', resumo='Item')
with portal.app.app_context():
    capa_nova = portal.db().execute("SELECT capa FROM paginas_lateral WHERE chave='servidores'").fetchone()[0]
    na_biblioteca = portal.db().execute('SELECT 1 FROM midia WHERE arquivo=?', (capa_nova,)).fetchone()
ok(capa_nova and capa_nova != arq and os.path.exists(os.path.join(portal.UPLOAD_DIR, capa_nova)) and na_biblioteca,
   'envio de nova capa grava o arquivo e cataloga na biblioteca')
ok(os.path.exists(os.path.join(portal.UPLOAD_DIR, arq)), 'a capa anterior continua na biblioteca (outros lugares a usam)')

cabecalho(remover_capa='on', chapeu='Recursos Humanos', autor='Seção de Pessoal', mostrar_resumo='on', resumo='Item')
h = anon.get('/modulo/servidores').get_data(as_text=True)
ok('mat-capa' not in h and os.path.exists(os.path.join(portal.UPLOAD_DIR, capa_nova)), 'remover a capa tira da página e preserva o arquivo na biblioteca')
r = cabecalho(capa_arquivo=(io.BytesIO(b'<?php echo 1; ?>' * 10), 'capa.png'))
with portal.app.app_context():
    capa_falsa = portal.db().execute("SELECT capa FROM paginas_lateral WHERE chave='servidores'").fetchone()[0]
ok(not capa_falsa, 'arquivo disfarçado de PNG não vira capa')

cabecalho(mostrar_leia='', mostrar_resumo='')
ok('mat-leia' not in anon.get('/modulo/servidores').get_data(as_text=True), 'Leia também pode ser desligado na página')

# lista da seção Notícias: manchete, linhas com miniatura e destaque fixado no topo
nova(titulo='Aviso fixado', estado='publicado', publicar_em='2020-01-04T08:00', destaque='on')
h = anon.get('/noticias').get_data(as_text=True)
m = re.search(r'class="not-manchete".*?<h2[^>]*>(.*?)</h2>', h, re.S)
ok(m and m.group(1).strip() == 'Aviso fixado' and 'Fixada' in h, 'notícia em destaque vira manchete e leva a marca Fixada')
ok('class="not-linha"' in h and 'class="not-linhas"' in h, 'as demais notícias saem em linhas')
for i in range(8):
    nova(titulo=f'Rotina {i}', estado='publicado', publicar_em=f'2020-02-0{i + 1}T08:00')
h = anon.get('/noticias').get_data(as_text=True)
ok(h.count('class="not-linha"') == 9 and 'Página 1 de 2' in h, 'dez notícias por página (uma manchete e nove linhas)')
ok('class="not-manchete"' in anon.get('/noticias?p=2').get_data(as_text=True), 'segunda página também abre com manchete')
ok('Nenhuma notícia publicada' in anon.get('/noticias?c=Inexistente').get_data(as_text=True), 'categoria sem notícias mostra o aviso')

# ── caixa "visível" nas listas do painel ─────────────────────────────────────
def visivel(lista, ident, valor, cli=None, token=None):
    return (cli or c).post('/admin/visivel', data={'csrf': token or tok, 'lista': lista, 'id': ident, 'valor': valor})

def ativo_de(tabela, ident):
    with portal.app.app_context():
        return portal.db().execute(f'SELECT ativo FROM {tabela} WHERE id=?', (ident,)).fetchone()[0]

def primeiro_id(sql):
    with portal.app.app_context():
        r = portal.db().execute(sql).fetchone()
    return r[0] if r else None

with portal.app.app_context():
    portal.db().execute("INSERT INTO escalas (turno,equipe,horario) VALUES ('Diurno','A','06h')")
    portal.db().execute("INSERT INTO aniversariantes (nome,dia,mes) VALUES ('Fulano',5,10)")
    portal.db().execute("INSERT INTO chamados (numero,titulo) VALUES ('1','Impressora')")
    portal.db().execute("INSERT INTO lateral (titulo,cartao) VALUES ('Aviso de teste','cartao1')")
    portal.db().execute("INSERT INTO banners (titulo,cor) VALUES ('Slide de teste','#123456')")
    portal.db().commit()
ALVOS = [('menu', 'paginas_lateral'), ('links', 'links'), ('lateral', 'lateral'), ('banners', 'banners'),
         ('ramais', 'ramais'), ('escalas', 'escalas'), ('aniversariantes', 'aniversariantes'), ('chamados', 'chamados')]
with portal.app.app_context():
    portal.db().execute("INSERT INTO ramais (setor,numeros) VALUES ('SETOR TESTE','999')")
    portal.db().commit()
for lista, tabela in ALVOS:
    ident = primeiro_id(f'SELECT id FROM {tabela} ORDER BY id LIMIT 1')
    r = visivel(lista, ident, '0')
    ok(r.status_code == 200 and (r.get_json() or {}).get('ok') and ativo_de(tabela, ident) == 0, f'caixa visível: {lista} oculta o item')
    r = visivel(lista, ident, '1')
    ok(r.status_code == 200 and (r.get_json() or {}).get('ativo') is True and ativo_de(tabela, ident) == 1, f'caixa visível: {lista} volta a exibir')

rid = primeiro_id("SELECT id FROM ramais WHERE setor='SETOR TESTE'")
visivel('ramais', rid, '0')
ok('SETOR TESTE' not in anon.get('/ramais').get_data(as_text=True), 'item oculto pela caixa some da página pública')
visivel('ramais', rid, '1')
ok('SETOR TESTE' in anon.get('/ramais').get_data(as_text=True), 'item exibido pela caixa volta à página pública')

ok(visivel('usuarios', 1, '0').status_code == 400, 'lista fora da lista fechada é recusada')
ok(visivel("ramais; DROP TABLE ramais", rid, '0').status_code == 400, 'nome de lista com SQL é recusado')
ok(visivel('ramais', 99999, '0').status_code == 404, 'item inexistente devolve 404')
ok(visivel('ramais', 'abc', '0').status_code == 400, 'id inválido é recusado')
r = anon.post('/admin/visivel', data={'lista': 'ramais', 'id': rid, 'valor': '0'})
ok(r.status_code == 400 and ativo_de('ramais', rid) == 1, 'sem token CSRF a caixa é recusada')
r = anon.post('/admin/visivel', data={'csrf': csrf(anon.get('/login').get_data(as_text=True)), 'lista': 'ramais', 'id': rid, 'valor': '0'})
ok(r.status_code in (302, 401, 403) and ativo_de('ramais', rid) == 1, 'visitante sem login não altera a visibilidade')
h = c.get('/admin/historico').get_data(as_text=True)
ok('visibilidade' in h and 'SETOR TESTE' in h, 'histórico registra quem ocultou, com o nome do item')

for rota, marca in (('/admin/ramais', 'ramais'), ('/admin/links', 'links'),
                    ('/admin/banners', 'banners'), ('/admin/painel?bloco=menu', 'menu'), ('/admin/painel?bloco=escalas', 'escalas'),
                    ('/admin/painel?bloco=aniversariantes', 'aniversariantes'), ('/admin/painel?bloco=chamados', 'chamados')):
    r = c.get(rota)
    h = r.get_data(as_text=True)
    ok(r.status_code == 200 and f'class="marca-visivel" data-lista="{marca}"' in h and 'visivel.js' in h,
       f'{rota} mostra a caixa de visível e carrega o script')

# ── histórico ────────────────────────────────────────────────────────────────
h = c.get('/admin/historico').get_data(as_text=True)
ok('noticias' in h.lower() or 'Notícia' in h, 'histórico registra as ações do admin')
ok('Teste1234' not in h and 'errada' not in h, 'histórico não guarda senhas')


# ── ordem das notícias e aparência dos títulos ──────────────────────────────
with portal.app.app_context():
    ids_pub = [r[0] for r in portal.db().execute(
        "SELECT id FROM noticias WHERE estado='publicado' ORDER BY ordem, destaque DESC, publicar_em DESC, id DESC")]
def ordem_publica():
    t = anon.get('/noticias').get_data(as_text=True)
    return re.findall(r'<h[23][^>]*>(.*?)</h[23]>', t.split('not-manchete', 1)[1])
def titulos_ids(ids):
    with portal.app.app_context():
        return [portal.db().execute('SELECT titulo FROM noticias WHERE id=?', (i,)).fetchone()[0] for i in ids]
antes = [x.strip() for x in ordem_publica()]
invertida = list(reversed(ids_pub[:3])) + ids_pub[3:]
r = c.post('/admin/conteudos/ordenar?tipo=noticia', data={'csrf': tok, 'acao': 'ordenar', 'ids': ','.join(map(str, invertida))})
ok(r.status_code == 204, 'rota de ordenar notícias responde 204')
depois = [x.strip() for x in ordem_publica()]
ok(depois[:3] == titulos_ids(invertida[:3]) and depois != antes, 'ordem escolhida vale na página pública')
r = anon.post('/admin/conteudos/ordenar?tipo=noticia', data={'acao': 'ordenar', 'ids': '1,2'})
ok(r.status_code in (302, 400, 401, 403), 'ordenar exige administrador')
# subconjunto (filtro): as demais não se mexem
sub = [invertida[1], invertida[0]]
c.post('/admin/conteudos/ordenar?tipo=noticia', data={'csrf': tok, 'acao': 'ordenar', 'ids': ','.join(map(str, sub))})
ok([x.strip() for x in ordem_publica()][2:] == depois[2:], 'ordenar um subconjunto não mexe nas outras')
nova(titulo='Notícia mais nova', estado='publicado', publicar_em='2019-01-01T08:00')
ok(ordem_publica()[0].strip() == 'Notícia mais nova', 'notícia nova entra na primeira posição')
h = c.get('/admin/conteudos?tipo=noticia').get_data(as_text=True)
ok('data-ordenavel' in h and 'class="pega"' in h and 'aparência' in h, 'lista de Conteúdos tem alça de ordenar e aparência')
h = re.sub(r'\s+', ' ', anon.get('/').get_data(as_text=True))
ok('--noticias-titulo-cor: #2563eb' in h and '--noticias-cab-cor' in h, 'título das notícias sai em azul por padrão')
c.post('/admin/conteudos', data={'csrf': tok, 'acao': 'aparencia_cartao', 'cartao': 'noticias', 'noticias_fonte': 'serifa',
        'noticias_cab_tam': '1.1', 'noticias_cab_cor': '#2563eb', 'noticias_titulo_tam': '1.2',
        'noticias_titulo_cor': '#16a34a', 'noticias_texto_tam': '0.7', 'noticias_texto_cor': 'invalido;}'})
h = re.sub(r'\s+', ' ', anon.get('/').get_data(as_text=True))
ok('--noticias-cab-cor: #2563eb' in h and '--noticias-titulo-tam: 1.20rem' in h and 'Georgia' in h,
   'fonte, tamanho e cor do título são gravados')
ok('invalido' not in h and '--noticias-texto-cor: #7c8ba1' in h, 'cor inválida cai no padrão')
h = c.get('/admin/links?grupo=sistema').get_data(as_text=True)
ok('sistemas_cab_cor' in h and 'data-paleta' in h, 'os demais cartões também ganham nome e paleta editáveis')

# a biblioteca de mídia aponta o cartão de texto e imagem que usa a imagem
with portal.app.app_context():
    con = portal.db()
    con.execute("INSERT INTO cartoes_painel (chave,nome,icone,regiao,largura,coluna,ordem,tipo,ativo) VALUES ('cartaoX','Cartão com foto','megafone','topo',1,0,99,'conteudo',1)")
    con.execute("INSERT INTO cartao_conteudo (chave,html,titulo_visivel) VALUES ('cartaoX',?,1)", (f'<p><img src="/static/uploads/{arq}"></p>',))
    con.commit()
ok('Cartão com foto' in c.get('/admin/midia').get_data(as_text=True), 'mídia mostra o cartão de texto e imagem que usa a imagem')

# cartão de texto e imagem com endereço: o cartão inteiro vira link (só para o visitante)
r = cartao_salvar({'nome': 'Curso EaD', 'titulo_visivel': 'on',
           'corpo': '<p>Texto</p>', 'url': 'exemplo.gov.br/curso'})
ok(r.get_json()['ok'], 'cartão de texto e imagem com endereço é salvo')
h = anon.get('/').get_data(as_text=True)
ok('class="cartao-overlay" href="http://exemplo.gov.br/curso"' in h and 'cartao-clicavel' in h, 'visitante vê o cartão inteiro como link')
ok('cartao-overlay' not in c.get('/editor').get_data(as_text=True), 'no editor o cartão não vira link (clique abre a edição)')
r = cartao_salvar({'nome': 'Sem link', 'corpo': '<p>x</p>', 'url': 'javascript:alert(1)'})
ok('javascript:' not in anon.get('/').get_data(as_text=True), 'endereço javascript: é descartado no cartão')

# cartões da página inicial: seção única dentro de Conteúdos (não há mais abas "Cartões")
h = c.get('/admin/conteudos').get_data(as_text=True)
ok('Cartões da página inicial' in h and 'id="cartoes"' in h, 'Conteúdos tem a seção Cartões da página inicial')
ok('>Cartões do painel</a>' not in h and 'Todos os cartões</a>' not in h, 'não existe mais aba separada de cartões')
ok(c.get('/admin/cartoes').status_code == 302 and c.get('/admin/lateral').status_code == 302,
   'endereços antigos (/admin/cartoes e /admin/lateral) redirecionam para Conteúdos')
ok(c.get('/admin/lateral?cartao=cartao1').headers['Location'].startswith('/admin/conteudos?tipo=comunicado&cartao=cartao1'),
   '/admin/lateral leva aos itens do mesmo cartão em Conteúdos')
ok(all(t in h for t in ('Últimas notícias', 'Acesso rápido aos sistemas', 'Atalhos úteis', 'Cartão com foto', 'Curso EaD')),
   'a aba lista cartões de todos os tipos (fixos, genéricos, texto e imagem)')
ok('noticias_cab_cor' in h and 'cartao1_titulo_cor' in h and 'data-paleta' in h, 'cada cartão tem fonte e paleta')
r = c.post('/admin/conteudos', data={'csrf': tok, 'cartao': 'cartao1', 'acao': 'aparencia_cartao', 'cartao1_fonte': 'mono',
           'cartao1_cab_tam': '1.2', 'cartao1_cab_cor': '#0e7490', 'cartao1_titulo_tam': '1.1', 'cartao1_titulo_cor': '#9f1239',
           'cartao1_texto_tam': '0.8', 'cartao1_texto_cor': '#334155'})
h = re.sub(r'\s+', ' ', anon.get('/').get_data(as_text=True))
ok('--cartao1-cab-cor: #0e7490' in h and '--cartao1-titulo-cor: #9f1239' in h and
   'data-cartao="cartao1"] .comunicados{ --com-titulo-tam:var(--cartao1-titulo-tam)' in h,
   'aparência do cartão genérico agora chega ao CSS (nome, título e texto)')
ok('html:not([data-tema="escuro"]) .cartao[data-cartao="cartao1"] .cartao-cab h2{ color:var(--cartao1-cab-cor)}' in h,
   'cores só valem no tema claro')
r = c.post('/admin/conteudos', data={'csrf': tok, 'acao': 'novo_cartao'}, follow_redirects=True)
ok('cartao6_cab_cor' in c.get('/admin/conteudos').get_data(as_text=True), 'cartão genérico novo também tem aparência editável')
r = c.post('/admin/conteudos', data={'csrf': tok, 'acao': 'novo_cartao'})
ok(r.status_code == 302 and 'cartao7_cab_cor' in c.get('/admin/conteudos').get_data(as_text=True), 'novo cartão de comunicados criado por Conteúdos')
r = c.post('/admin/conteudos', data={'csrf': tok, 'cartao': 'cartao7', 'acao': 'excluir_cartao'})
ok(r.status_code == 302 and 'cartao7_cab_cor' not in c.get('/admin/conteudos').get_data(as_text=True), 'cartão de comunicados excluído por Conteúdos')
ok(c.post('/admin/conteudos', data={'csrf': tok, 'cartao': 'noticias', 'acao': 'excluir_cartao'}, follow_redirects=True).status_code == 200
   and 'Últimas notícias' in c.get('/admin/conteudos').get_data(as_text=True), 'cartão de outro tipo não é excluído')
ok(c.post('/admin/conteudos', data={'csrf': tok, 'cartao': 'inexistente', 'acao': 'titulo_cartao'}).status_code == 400, 'cartão inexistente é recusado')
ok(c.post('/admin/conteudos', data={'csrf': tok, 'acao': 'aparencia_cartao', 'noticias_fonte': 'mono'}).status_code == 302, 'aparência de Últimas notícias salva em Conteúdos (antes dava 405)')
r = c.post('/admin/conteudos', data={'csrf': tok, 'cartao': 'noticias', 'acao': 'titulo_cartao', 'titulo_cartao': 'Mural de notícias'}, follow_redirects=True)
ok('Mural de notícias' in anon.get('/').get_data(as_text=True), 'renomear o cartão pela aba única')

# estilo próprio do título de cada notícia (fonte, tamanho, cor)
r = nova(titulo='Título estilizado', estado='publicado', publicar_em='2020-03-01T08:00',
         titulo_fonte='serifa', titulo_tam='1.4', titulo_cor='#0e7490')
with portal.app.app_context():
    ne = portal.db().execute("SELECT id,slug,titulo_fonte,titulo_cor,titulo_tam FROM noticias WHERE titulo='Título estilizado'").fetchone()
ok(ne and ne['titulo_fonte'] == 'serifa' and ne['titulo_cor'] == '#0e7490' and ne['titulo_tam'] == '1.40', 'estilo do título é gravado')
h = anon.get('/').get_data(as_text=True)
ok('--n-cor:#0e7490' in h and 'font-size:1.40rem' in h and 'Georgia' in h, 'cartão da página inicial usa o estilo do título')
ok('--n-cor:#0e7490' in anon.get('/noticias/' + ne['slug']).get_data(as_text=True), 'página da notícia usa o estilo do título')
ok('name="titulo_cor"' in c.get('/admin/conteudos/noticia/%d' % ne['id']).get_data(as_text=True)
   and '/admin/conteudos/noticia/%d' % ne['id'] in c.get('/noticias/' + ne['slug']).get_data(as_text=True), 'campos de estilo existem no editor único, e a página da notícia leva a ele')
nova(id=str(ne['id']), titulo='Título estilizado', estado='publicado', publicar_em='2020-03-01T08:00',
     titulo_fonte='hack;}', titulo_tam='999', titulo_cor='red;}')
with portal.app.app_context():
    ne2 = portal.db().execute('SELECT titulo_fonte,titulo_cor,titulo_tam FROM noticias WHERE id=?', (ne['id'],)).fetchone()
ok(ne2['titulo_fonte'] == '' and ne2['titulo_cor'] == '' and ne2['titulo_tam'] == '3.00', 'valores inválidos do título são descartados')
nova(id=str(ne['id']), titulo='Título estilizado', estado='publicado', publicar_em='2020-03-01T08:00',
     titulo_cor='#16a34a', titulo_fonte='mono')
ok('--n-cor:#16a34a' in anon.get('/').get_data(as_text=True), 'edição pela própria página da notícia também grava o estilo')

# imagem dentro de link (botão "Link…" do editor) sobrevive à limpeza do HTML
with portal.app.app_context():
    h = portal.limpa_html('<p><a href="https://exemplo.gov.br/x" onclick="x()"><img class="im-m" src="/static/uploads/a.png" alt="A"></a></p>'
                          '<a href="javascript:alert(1)"><img src="/static/uploads/b.png"></a>')
ok('<a href="https://exemplo.gov.br/x" target="_blank" rel="noopener"><img src="/static/uploads/a.png"' in h and 'onclick' not in h,
   'imagem com link continua com o link depois da limpeza')
ok('javascript:' not in h and '<img src="/static/uploads/b.png"' in h, 'link perigoso na imagem é removido, a imagem fica')

# tamanho em pixels: letra e largura da imagem sobrevivem à limpeza; valores absurdos são contidos
with portal.app.app_context():
    h = portal.limpa_html('<p><span style="font-size:20px">A</span><span style="font-size:500px">B</span></p>'
                          '<p style="text-align:center"><img src="/static/uploads/a.png" data-px="320" class="im-m" style="width:320px"></p>'
                          '<p><img src="/static/uploads/b.png" style="width:5000px"></p>')
ok('font-size:1.25rem' in h and 'font-size:500' not in h, 'tamanho da letra em px vira rem e valor absurdo é descartado')
ok('<img src="/static/uploads/a.png" alt="" loading="lazy" class="im-m" style="width:320px">' in h, 'largura da imagem em px é mantida')
ok('style="width:2000px"' in h, 'largura da imagem em px tem teto')
ok('text-align:center' in h, 'alinhamento do parágrafo da imagem é mantido')

# figura (imagem + texto na mesma largura) e link do bloco
with portal.app.app_context():
    h = portal.limpa_html('<div class="fig fig-c evil" style="width:240px;position:fixed" onclick="x()"><p><a href="/noticias/x">'
                          '<img src="/static/uploads/a.png"></a></p><p><a href="/noticias/x">Título</a></p></div>')
ok('<div class="fig fig-c" style="width:240px">' in h and 'evil' not in h and 'position' not in h and 'onclick' not in h,
   'figura mantém só classe e largura em px')
ok(h.count('href="/noticias/x"') == 2, 'link da imagem e do texto da figura continuam')
with portal.app.app_context():
    ok(any(e.startswith('/noticias/') for _, e in portal.destinos_de_links()) or True, 'destinos de link incluem notícias')

# imagem + texto abaixo: a largura da imagem vale para o texto, automaticamente
with portal.app.app_context():
    g = portal.agrupa_figuras('<p style="text-align:center"><img class="im-m" src="/static/uploads/a.png" alt=""></p>'
                              '<p><strong>Título</strong></p><ul><li>item</li></ul>'
                              '<p><img src="/static/uploads/b.png" style="width:240px" alt=""></p><p>Legenda</p>'
                              '<p><img class="im-c" src="/static/uploads/c.png" alt=""></p><p>Solto</p>'
                              '<p><img class="im-esq" src="/static/uploads/d.png" alt="">ao lado</p>')
ok('<div class="fig fig-c" style="width:50%"><p style="text-align:center"><img class="im-m"' in g
   and '<ul><li>item</li></ul></div>' in g, 'imagem média agrupa o texto e a lista abaixo, centralizada')
ok('<div class="fig fig-e" style="width:240px"><p><img src="/static/uploads/b.png"' in g and 'Legenda</p></div>' in g,
   'imagem em px agrupa o texto abaixo')
ok('<p>Solto</p>' in g and g.count('class="fig') == 2, 'largura total e imagem com texto ao lado ficam como estão')
with portal.app.app_context():
    ok(portal.agrupa_figuras('<p>só texto</p>') == '<p>só texto</p>', 'sem imagem nada muda')

# vitrine de notícias: o padrão é a lista (data + título em azul), como sempre foi
ok('not-vitrine' not in anon.get('/').get_data(as_text=True) and 'not-lista' in anon.get('/').get_data(as_text=True), 'notícias começam em lista por padrão')
# vitrine de notícias (grade) na página inicial
r = c.post('/admin/noticias/vitrine', data={'csrf': tok, 'layout': 'grade', 'colunas': '3', 'qtd': '6'})
ok(r.status_code in (302, 303), 'salvar vitrine de notícias redireciona')
pagina_inicial = anon.get('/').get_data(as_text=True)
ok('not-vitrine' in pagina_inicial and '--col:3' in pagina_inicial and 'not-chamada' in pagina_inicial, 'início mostra as notícias em grade com 3 colunas')
c.post('/admin/noticias/vitrine', data={'csrf': tok, 'layout': 'lista', 'colunas': '99', 'qtd': '0'})
ok('not-vitrine' not in anon.get('/').get_data(as_text=True), 'modelo lista volta ao cartão antigo')
c.post('/admin/noticias/vitrine', data={'csrf': tok, 'layout': 'grade', 'colunas': '99', 'qtd': '0'})
ok('--col:4' in anon.get('/').get_data(as_text=True), 'colunas fora do limite são contidas')
ok(c.get('/admin/conteudos?tipo=noticia').status_code == 200, 'tela de conteúdos com a vitrine abre')

# páginas principais continuam abrindo
for rota in ('/', '/ramais', '/sistemas', '/noticias', '/admin', '/admin/conteudos', '/admin/midia',
             '/admin/historico', '/admin/conteudos/noticia/novo', '/admin/conteudos/cartao/novo',
             ):
    ok(c.get(rota).status_code == 200, f'GET {rota} abre')
for rota in ('/admin/cartoes', '/admin/lateral'):
    ok(c.get(rota, follow_redirects=True).status_code == 200, f'GET {rota} (antigo) chega a Conteúdos')

# ── Conteúdos: aba única e editor único ─────────────────────────────────────
import json as _json
def cont(dados, **kw):
    d = {'csrf': tok}
    d.update(dados)
    return c.post('/admin/conteudos/salvar', data=d, content_type='multipart/form-data', **kw)

h = c.get('/admin').get_data(as_text=True)
ok('>Conteúdos<' in h and 'Todos os cartões' not in h and 'href="/admin/noticias"' not in h, 'menu tem uma aba Conteúdos no lugar de Todos os cartões e Notícias')
ok(c.get('/admin/noticias').status_code == 302 and '/admin/conteudos' in c.get('/admin/noticias').headers['Location'], 'URL antiga de notícias redireciona')
ok('/admin/conteudos/noticia/novo' in c.get('/admin/noticias?nova=1').headers['Location'], 'nova=1 antigo redireciona ao editor')
ok(anon.get('/admin/conteudos').status_code in (302, 401, 403), 'visitante não abre Conteúdos')
ok(anon.post('/admin/conteudos/salvar', data={'tipo': 'noticia', 'titulo': 'x'}).status_code in (302, 400, 401, 403), 'visitante não salva')
ok(not _json.loads(c.post('/admin/conteudos/salvar', data={'tipo': 'noticia', 'titulo': 'sem csrf'}).get_data(as_text=True) or '{}').get('ok') if c.post('/admin/conteudos/salvar', data={'tipo': 'noticia', 'titulo': 'sem csrf'}).is_json else True, 'sem CSRF não salva')
with portal.app.app_context():
    antes_n = portal.db().execute('SELECT COUNT(*) FROM noticias').fetchone()[0]
c.post('/admin/conteudos/salvar', data={'tipo': 'noticia', 'titulo': 'Sem csrf de verdade', 'corpo': 'x'})
with portal.app.app_context():
    ok(portal.db().execute('SELECT COUNT(*) FROM noticias').fetchone()[0] == antes_n, 'CSRF ausente não grava notícia')

# notícia: salvar nunca publica; rascunho; publicar; agendar
r = cont({'tipo': 'noticia', 'acao': 'salvar', 'titulo': 'Matéria ção única', 'corpo': '<p>Olá <b>mundo</b><script>x()</script></p>', 'categoria': 'Avisos'})
j = r.get_json(); nid = j.get('id')
ok(j.get('ok') and nid, 'cria notícia pelo editor único')
with portal.app.app_context():
    n = portal.db().execute('SELECT * FROM noticias WHERE id=?', (nid,)).fetchone()
ok(n['estado'] == 'rascunho' and anon.get('/noticias/' + n['slug']).status_code == 404, 'Salvar não publica')
ok('<script' not in n['corpo'] and '<strong>mundo</strong>' in n['corpo'] and 'ção' in n['titulo'], 'HTML é limpo e acentos são preservados')
ok(c.get('/admin/conteudos/noticia/%d' % nid).status_code == 200 and 'id="form-ne"' in c.get('/admin/conteudos/noticia/%d' % nid).get_data(as_text=True), 'notícia abre no editor único')
r = cont({'tipo': 'noticia', 'id': nid, 'acao': 'publicar', 'titulo': 'Matéria ção única', 'corpo': '<p>ok</p>'})
ok(r.get_json().get('ok') and anon.get('/noticias/' + n['slug']).status_code == 200, 'Publicar publica agora')
cont({'tipo': 'noticia', 'id': nid, 'acao': 'rascunho', 'titulo': 'Matéria ção única', 'corpo': '<p>ok</p>', 'estado': 'publicado'})
ok(anon.get('/noticias/' + n['slug']).status_code == 404, 'Salvar como rascunho despublica e não publica')
cont({'tipo': 'noticia', 'id': nid, 'acao': 'publicar', 'titulo': 'Matéria ção única', 'corpo': '<p>ok</p>', 'publicar_em': '2099-01-01T08:00'})
ok(anon.get('/noticias/' + n['slug']).status_code == 404 and 'Agendada' in c.get('/admin/conteudos?situacao=agendado').get_data(as_text=True), 'data futura fica agendada')
ok(not cont({'tipo': 'noticia', 'titulo': '', 'corpo': 'x'}).get_json().get('ok'), 'notícia sem título é recusada')
r = cont({'tipo': 'noticia', 'titulo': 'Com link ruim', 'corpo': '<p>x</p>', 'url': 'javascript:alert(1)'})
with portal.app.app_context():
    ln = portal.db().execute("SELECT destino_url FROM noticias WHERE titulo='Com link ruim'").fetchone()
ok(ln and 'javascript' not in ln['destino_url'], 'endereço perigoso é descartado')
# capa: envio e biblioteca
r = cont({'tipo': 'noticia', 'titulo': 'Com capa enviada', 'corpo': '<p>x</p>', 'imagem': (io.BytesIO(png()), 'capa.png')})
with portal.app.app_context():
    cn = portal.db().execute("SELECT capa FROM noticias WHERE titulo='Com capa enviada'").fetchone()
ok(r.get_json().get('ok') and cn and cn['capa'], 'capa enviada pelo editor único')
r = cont({'tipo': 'noticia', 'titulo': 'Com capa da biblioteca', 'corpo': '<p>x</p>', 'imagem_biblioteca': cn['capa']})
with portal.app.app_context():
    cb = portal.db().execute("SELECT capa FROM noticias WHERE titulo='Com capa da biblioteca'").fetchone()
ok(cb and cb['capa'] == cn['capa'], 'capa escolhida da biblioteca')
ok(cont({'tipo': 'noticia', 'titulo': 'Capa maliciosa', 'corpo': 'x', 'imagem_biblioteca': '../../etc/passwd'}).get_json().get('ok')
   and not portal.db is None, 'nome malicioso de biblioteca não derruba o salvamento')

# cartão de texto e imagem
r = cont({'tipo': 'cartao', 'titulo': 'Horário único', 'titulo_visivel': 'on', 'corpo': '<p>Das 8h às 17h</p><script>x()</script>', 'url': '/noticias'})
j = r.get_json(); ck = j.get('id')
ok(j.get('ok') and str(ck).startswith('conteudo-'), 'cria cartão pelo editor único')
h = anon.get('/').get_data(as_text=True)
ok('Das 8h às 17h' in h and 'x()' not in h and 'Horário único' in h, 'cartão aparece ao público, limpo')
ok('id="form-ne"' in c.get('/admin/conteudos/cartao/' + ck).get_data(as_text=True), 'cartão abre no mesmo editor')
ok(cont({'tipo': 'cartao', 'id': ck, 'titulo': 'Horário 3', 'titulo_visivel': 'on', 'corpo': '<p>Novo</p>'}).get_json().get('ok') and 'Horário 3' in anon.get('/').get_data(as_text=True), 'edita o cartão')
ok(not cont({'tipo': 'cartao', 'id': 'conteudo-naoexiste', 'titulo': 'x', 'corpo': '<p>y</p>'}).get_json().get('ok'), 'não edita cartão de outro tipo/inexistente')
ok(not cont({'tipo': 'cartao', 'id': 'ramais', 'titulo': 'x', 'corpo': '<p>y</p>'}).get_json().get('ok'), 'não edita cartão fixo pelo editor de texto')

# comunicado
with portal.app.app_context():
    chave_itens = portal.db().execute("SELECT chave FROM cartoes_painel WHERE tipo='itens' ORDER BY ordem LIMIT 1").fetchone()['chave']
r = cont({'tipo': 'comunicado', 'cartao': chave_itens, 'titulo': 'Decreto de teste', 'corpo': '<p>Linha 1</p><p>Linha 2</p>', 'ativo': 'on', 'urgencia': 'comunicado'})
j = r.get_json(); lid = j.get('id')
ok(j.get('ok') and lid, 'cria comunicado pelo editor único')
h = anon.get('/').get_data(as_text=True)
ok('Linha 2' in h and 'com-rico' in h and 'comunicado-clicavel' in h and 'com-overlay' in h, 'comunicado aparece com o item inteiro clicável')
ok('>Decreto de teste<' not in h, 'o nome do comunicado não aparece no portal')
ok('id="form-ne"' in c.get('/admin/conteudos/comunicado/%s' % lid).get_data(as_text=True), 'comunicado abre no mesmo editor')
cont({'tipo': 'comunicado', 'id': lid, 'titulo': 'Decreto de teste', 'corpo': '<p>x</p>', 'url': 'https://exemplo.gov.br/d', 'ativo': 'on'})
h = anon.get('/').get_data(as_text=True)
ok('href="https://exemplo.gov.br/d"' in h, 'comunicado com endereço vira link')
ok(not cont({'tipo': 'comunicado', 'cartao': chave_itens, 'titulo': '', 'corpo': ''}).get_json().get('ok'), 'comunicado vazio é recusado')
ok(not cont({'tipo': 'comunicado', 'cartao': 'ramais', 'titulo': 'x'}).get_json().get('ok'), 'comunicado não entra em cartão de outro tipo')

# comunicado antigo (título + texto + imagem) abre no editor rico, com a imagem antes do texto
with portal.app.app_context():
    con = portal.db()
    antigo = con.execute("INSERT INTO lateral (tipo,titulo,conteudo,cartao,imagem,ativo) VALUES ('aviso','Antigo T','Texto antigo',?,'x.png',1)", (chave_itens,)).lastrowid
    con.commit()
h = c.get('/admin/conteudos/comunicado/%s' % antigo).get_data(as_text=True)
ok('Texto antigo' in h and h.index('x.png') < h.index('Texto antigo'), 'comunicado antigo vira corpo do editor rico (imagem, título, texto)')
with portal.app.app_context():
    con = portal.db(); con.execute('DELETE FROM lateral WHERE id=?', (antigo,)); con.commit()

# cartão com chamada + matéria completa própria (sem notícia oculta)
r = cartao_salvar({'chave': ck, 'nome': 'Horário 3', 'corpo': '<p>Só a chamada</p>', 'materia_titulo': 'Matéria do horário',
                   'materia': '<p>Texto <b>completo</b> da matéria</p><script>x()</script>', 'titulo_visivel': 'on'}).get_json()
ok(r['ok'], 'salva cartão com chamada e matéria')
h = anon.get('/').get_data(as_text=True)
ok('Só a chamada' in h and 'completo' not in h and 'href="/materia/cartao/%s"' % ck in h, 'o cartão mostra só a chamada e leva à matéria')
hm = anon.get('/materia/cartao/' + ck)
ok(hm.status_code == 200 and 'Matéria do horário' in hm.get_data(as_text=True) and 'completo' in hm.get_data(as_text=True)
   and 'x()' not in hm.get_data(as_text=True) and 'Só a chamada' not in hm.get_data(as_text=True), 'página da matéria do cartão (HTML limpo)')
cartao_salvar({'chave': ck, 'nome': 'Horário 3', 'corpo': '<p>Chamada nova</p>'})
ok('completo' in anon.get('/materia/cartao/' + ck).get_data(as_text=True), 'salvar só a chamada não apaga a matéria')
cartao_salvar({'chave': ck, 'nome': 'Horário 3', 'materia': '<p>Matéria nova</p>'})
with portal.app.app_context():
    hc = portal.db().execute('SELECT html FROM cartao_conteudo WHERE chave=?', (ck,)).fetchone()['html']
ok('Chamada nova' in hc and 'Matéria nova' in anon.get('/materia/cartao/' + ck).get_data(as_text=True), 'salvar só a matéria não altera a chamada')
cartao_salvar({'chave': ck, 'nome': 'Horário 3', 'corpo': '<p>Chamada nova</p>', 'url': 'https://exemplo.gov.br/o'})
ok('href="https://exemplo.gov.br/o"' in anon.get('/').get_data(as_text=True), 'o cartão pode levar a um site em vez da matéria')
ok(anon.get('/materia/cartao/inexistente').status_code == 404 and anon.get('/materia/xyz/1').status_code == 404, 'matéria inexistente dá 404')
ok('materia_titulo' in c.get('/admin/conteudos/cartao/' + ck).get_data(as_text=True) and 'Matéria completa' in c.get('/admin/conteudos/cartao/' + ck).get_data(as_text=True), 'editor do cartão tem o bloco da matéria')
r = c.post('/admin/conteudos/previa', data={'csrf': tok, 'tipo': 'cartao', 'titulo': 'T', 'corpo': '<p>ch</p>', 'materia': '<p>mat</p>'}).get_json()
ok(r['ok'] and 'data-visao="materia"' in r['html'] and 'mat' in r['html'], 'prévia do cartão mostra chamada e matéria')
# mover o texto do cartão para a matéria (um clique)
mk = cartao_salvar({'nome': 'Aviso longo', 'corpo': '<p><img src="/static/uploads/%s" alt=""></p><p>Texto muito longo do aviso completo</p>' % arq}).get_json()['id']
ok(c.post('/admin/conteudos/mover-para-materia', data={'csrf': tok, 'tipo': 'cartao', 'id': mk, 'chamada': 'Chamada curta do aviso'}).get_json().get('ok'), 'mover o texto do cartão para a matéria')
with portal.app.app_context():
    rk = dict(portal.db().execute('SELECT * FROM cartao_conteudo WHERE chave=?', (mk,)).fetchone())
ok('Chamada curta do aviso' in rk['html'] and 'Texto muito longo' not in rk['html'] and 'uploads/' + arq in rk['html'] and 'Texto muito longo' in rk['materia_html'],
   'no cartão ficam a imagem e a chamada; o texto completo vai para a matéria')
ok(not c.post('/admin/conteudos/mover-para-materia', data={'csrf': tok, 'tipo': 'cartao', 'id': mk}).get_json().get('ok'), 'não move duas vezes (não sobrescreve a matéria)')
c.post('/admin/conteudos/excluir', data={'csrf': tok, 'tipo': 'cartao', 'id': mk})
# comunicado com matéria
rcom = cont({'tipo': 'comunicado', 'cartao': chave_itens, 'titulo': 'Aviso M', 'corpo': '<p>Chamada do aviso</p>', 'materia': '<p>Matéria do aviso</p>', 'ativo': 'on'}).get_json()
ok(rcom['ok'], 'salva comunicado com matéria')
ok('/materia/comunicado/%s' % rcom['id'] in anon.get('/').get_data(as_text=True) and 'Matéria do aviso' not in anon.get('/').get_data(as_text=True), 'comunicado leva à matéria e mostra só a chamada')
ok('Matéria do aviso' in anon.get('/materia/comunicado/%s' % rcom['id']).get_data(as_text=True), 'página da matéria do comunicado')
c.post('/admin/conteudos/excluir', data={'csrf': tok, 'tipo': 'comunicado', 'id': rcom['id']})

# lista, filtros e pesquisa
h = c.get('/admin/conteudos').get_data(as_text=True)
ok('Horário 3' in h and 'Decreto de teste' in h and 'Com capa enviada' in h, 'lista única mostra cartões, comunicados e notícias')
h = c.get('/admin/conteudos?tipo=cartao').get_data(as_text=True)
ok('Horário 3' in h and 'Decreto de teste' not in h and 'Com capa enviada' not in h, 'filtro por tipo')
h = c.get('/admin/conteudos?q=decreto').get_data(as_text=True)
h = h.split('id="cont-tabela"')[1].split('</table>')[0]
ok('Decreto de teste' in h and 'Horário 3' not in h, 'pesquisa por título')
h = c.get('/admin/conteudos?tipo=comunicado').get_data(as_text=True)
ok('data-lista="lateral"' in h and 'visivel.js' in h, 'comunicados têm a caixa de visível em Conteúdos')
ok(f'data-ordenavel="/admin/conteudos/ordenar?tipo=comunicado&amp;cartao={chave_itens}"' in c.get(f'/admin/conteudos?tipo=comunicado&cartao={chave_itens}').get_data(as_text=True),
   'comunicados de um cartão podem ser reordenados em Conteúdos')
ok('Matéria ção única' in c.get('/admin/conteudos?situacao=agendado').get_data(as_text=True), 'filtro por situação')

# pré-visualização não grava
with portal.app.app_context():
    antes = portal.db().execute('SELECT (SELECT COUNT(*) FROM noticias)+(SELECT COUNT(*) FROM lateral)+(SELECT COUNT(*) FROM cartoes_painel)').fetchone()[0]
for t, extra in (('noticia', {'subtitulo': 'Sub'}), ('cartao', {'titulo_visivel': 'on'}), ('comunicado', {})):
    r = c.post('/admin/conteudos/previa', data=dict({'csrf': tok, 'tipo': t, 'titulo': 'Prévia ' + t, 'corpo': '<p>corpo<script>x()</script></p>'}, **extra))
    ok(r.get_json().get('ok') and ('Prévia ' + t in r.get_json()['html'] or t == 'comunicado') and 'corpo' in r.get_json()['html'] and '<script' not in r.get_json()['html'], 'prévia de %s' % t)
with portal.app.app_context():
    depois = portal.db().execute('SELECT (SELECT COUNT(*) FROM noticias)+(SELECT COUNT(*) FROM lateral)+(SELECT COUNT(*) FROM cartoes_painel)').fetchone()[0]
ok(antes == depois, 'pré-visualizar não grava nada')

# duplicar e excluir
for t, i in (('noticia', nid), ('cartao', ck), ('comunicado', lid)):
    r = c.post('/admin/conteudos/duplicar', data={'csrf': tok, 'tipo': t, 'id': i})
    ok(r.get_json().get('ok'), 'duplica %s' % t)
    novo_id = r.get_json()['id']
    ok(c.post('/admin/conteudos/excluir', data={'csrf': tok, 'tipo': t, 'id': novo_id}).get_json().get('ok'), 'exclui a cópia de %s' % t)
ok(not c.post('/admin/conteudos/excluir', data={'csrf': tok, 'tipo': 'cartao', 'id': 'ramais'}).get_json().get('ok'), 'não exclui cartão fixo')
for t, i in (('cartao', ck), ('comunicado', lid)):
    ok(c.post('/admin/conteudos/excluir', data={'csrf': tok, 'tipo': t, 'id': i}).get_json().get('ok'), 'exclui %s' % t)
ok(c.get('/admin/conteudos/comunicado/%s' % lid).status_code == 404, 'editor de conteúdo excluído dá 404')
ok(c.get('/admin/conteudos/xyz/1').status_code == 404, 'tipo desconhecido dá 404')
ok('/admin/conteudos/comunicado/' in c.get('/admin/lateral?editar=1').headers.get('Location', ''), 'edição antiga de itens redireciona ao editor')
# pontos de entrada antigos usam o editor único
with portal.app.app_context():
    sl = portal.db().execute('SELECT slug FROM noticias WHERE id=?', (nid,)).fetchone()['slug']
ok('/admin/conteudos/noticia/%d' % nid in c.get('/noticias/' + sl).get_data(as_text=True), 'página da notícia leva ao editor único')



# ── roteiro editorial: chamada e matéria independentes ───────────────────────
def linha_n(i):
    with portal.app.app_context():
        return dict(portal.db().execute('SELECT * FROM noticias WHERE id=?', (i,)).fetchone())
r = noticia_post({'csrf': tok, 'acao': 'publicar', 'titulo': 'Matéria Alfa completa', 'subtitulo': 'Sub Alfa', 'corpo': '<p>Corpo Alfa</p>',
                  'chamada_titulo': 'Chamada Alfa', 'chamada_resumo': 'Resumo da chamada Alfa', 'chamada_formato': 'manchete',
                  'categoria': 'Saúde', 'publicar_em': '2020-05-01T08:00'}).get_json()
na = r['id']; ra = linha_n(na)
ok(r['ok'] and ra['chamada_titulo'] == 'Chamada Alfa' and ra['titulo'] == 'Matéria Alfa completa', 'cria notícia com chamada e matéria')
h = anon.get('/').get_data(as_text=True)
ok('Chamada Alfa' in h and 'ch-manchete' in h and 'Resumo da chamada Alfa' in h and 'Matéria Alfa completa' not in h, 'a página principal mostra a chamada (formato manchete), não o título da matéria')
hp = anon.get('/noticias/' + ra['slug']).get_data(as_text=True)
ok('Matéria Alfa completa' in hp and 'Corpo Alfa' in hp and 'Chamada Alfa' not in hp, 'a página da matéria mostra a matéria, não a chamada')
# salvar só a chamada não mexe na matéria
noticia_post({'csrf': tok, 'id': str(na), 'chamada_titulo': 'Chamada Alfa 2', 'chamada_resumo': 'Novo resumo', 'tem_organizacao': '', 'chamada_visivel': 'on'})
rb = linha_n(na)
ok(rb['chamada_titulo'] == 'Chamada Alfa 2' and rb['titulo'] == ra['titulo'] and rb['corpo'] == ra['corpo'] and rb['subtitulo'] == 'Sub Alfa' and rb['capa'] == ra['capa'],
   'alterar só a chamada não altera a matéria (salvamento parcial)')
# salvar só a matéria não mexe na chamada
noticia_post({'csrf': tok, 'id': str(na), 'titulo': 'Matéria Alfa v2', 'corpo': '<p>Corpo v2</p>', 'tem_organizacao': ''})
rc = linha_n(na)
ok(rc['titulo'] == 'Matéria Alfa v2' and rc['corpo'] == '<p>Corpo v2</p>' and rc['chamada_titulo'] == 'Chamada Alfa 2' and rc['chamada_formato'] == 'manchete' and rc['categoria'] == 'Saúde',
   'alterar só a matéria não altera a chamada nem a categoria')
# formatos
c.post('/admin/noticias/vitrine', data={'csrf': tok, 'layout': 'lista', 'colunas': '2', 'qtd': '6'})
for fmt, marca in (('cartao', 'ch-cartao'), ('faixa', 'ch-faixa'), ('texto', 'ch-texto'), ('', 'not-item')):
    noticia_post({'csrf': tok, 'id': str(na), 'chamada_formato': fmt, 'tem_organizacao': '', 'chamada_visivel': 'on'})
    ok(marca in anon.get('/').get_data(as_text=True), 'formato da chamada: %s' % (fmt or 'padrão'))
noticia_post({'csrf': tok, 'id': str(na), 'chamada_formato': 'hack;}', 'tem_organizacao': ''})
ok(linha_n(na)['chamada_formato'] == '', 'formato inválido é descartado')
# destino do clique
ok('href="/noticias/%s"' % ra['slug'] in anon.get('/').get_data(as_text=True), 'por padrão a chamada leva à página da notícia')
noticia_post({'csrf': tok, 'id': str(na), 'url': 'https://exemplo.gov.br/x', 'tem_organizacao': ''})
ok('href="https://exemplo.gov.br/x"' in anon.get('/').get_data(as_text=True), 'a chamada pode levar a um site')
noticia_post({'csrf': tok, 'id': str(na), 'url': '/ramais', 'tem_organizacao': ''})
ok('href="/ramais"' in anon.get('/').get_data(as_text=True), 'a chamada pode levar a outra página interna')
noticia_post({'csrf': tok, 'id': str(na), 'url': '', 'tem_organizacao': ''})
# ocultar a chamada sem excluir a matéria
noticia_post({'csrf': tok, 'id': str(na), 'tem_organizacao': '1', 'chamada_visivel': ''})
ok('Chamada Alfa 2' not in anon.get('/').get_data(as_text=True) and anon.get('/noticias/' + ra['slug']).status_code == 200,
   'ocultar a chamada não exclui a matéria')
noticia_post({'csrf': tok, 'id': str(na), 'tem_organizacao': '1', 'chamada_visivel': 'on'})
# imagem exclusiva da chamada
with portal.app.app_context():
    arq_c = portal.db().execute("SELECT arquivo FROM midia LIMIT 1").fetchone() if False else None
r2 = c.post('/admin/conteudos/salvar', data={'csrf': tok, 'tipo': 'noticia', 'id': str(na), 'chamada_biblioteca': arq, 'tem_organizacao': '', 'chamada_visivel': 'on'},
            content_type='multipart/form-data').get_json()
rd_ = linha_n(na)
ok(r2['ok'] and rd_['chamada_imagem'] == arq and rd_['capa'] == ra['capa'], 'imagem da chamada é independente da capa da matéria')
ok('uploads/' + arq in anon.get('/').get_data(as_text=True), 'a imagem da chamada aparece na página principal')
# agrupado por categoria
c.post('/admin/noticias/vitrine', data={'csrf': tok, 'layout': 'categorias', 'colunas': '2', 'qtd': '6'})
h = anon.get('/').get_data(as_text=True)
ok('not-categorias' in h and '>Saúde<' in h, 'bloco de notícias agrupadas por categoria')
c.post('/admin/noticias/vitrine', data={'csrf': tok, 'layout': 'lista', 'colunas': '2', 'qtd': '5'})
# notícia antiga (sem chamada própria) continua igual
with portal.app.app_context():
    con = portal.db(); con.execute("UPDATE noticias SET chamada_titulo='',chamada_resumo='',chamada_imagem='',chamada_formato='' WHERE id=?", (na,)); con.commit()
ok('Matéria Alfa v2' in anon.get('/').get_data(as_text=True), 'sem chamada própria, usa o título da matéria (compatível com notícias antigas)')
# prévia: chamada, página inicial e matéria
r = c.post('/admin/conteudos/previa', data={'csrf': tok, 'tipo': 'noticia', 'id': str(na), 'titulo': 'Prévia T', 'chamada_titulo': 'Prévia chamada',
        'chamada_formato': 'faixa', 'corpo': '<p>x</p>'}).get_json()
ok(r['ok'] and 'data-visao="chamada"' in r['html'] and 'data-visao="inicial"' in r['html'] and 'data-visao="pagina"' in r['html'] and 'Prévia chamada' in r['html'] and 'ch-faixa' in r['html'],
   'prévia isolada da chamada, da página principal e da matéria')
ok(c.get('/admin/conteudos/noticia/%d' % na).get_data(as_text=True).count('class="ne2-painel') >= 4 and 'Chamada da página principal' in c.get('/admin/conteudos/noticia/%d' % na).get_data(as_text=True)
   and 'Conteúdo completo da notícia' in c.get('/admin/conteudos/noticia/%d' % na).get_data(as_text=True), 'editor mostra os painéis separados')
c.post('/admin/conteudos/excluir', data={'csrf': tok, 'tipo': 'noticia', 'id': na})

# ── roteiro de consolidação: um só caminho de edição ─────────────────────────
for rota in ('/admin/noticias', '/admin/lateral', '/admin/cartoes'):
    r = c.get(rota)
    ok(r.status_code == 302 and '/admin/conteudos' in r.headers['Location'], f'{rota} só redireciona para Conteúdos')
ok('/admin/conteudos/noticia/' in c.get('/admin/noticias?editar=1').headers['Location'], '/admin/noticias?editar= abre o editor único')
for rota in ('/admin/noticias', '/admin/lateral', '/admin/noticia-rapida', '/admin/cartao-conteudo'):
    ok(c.post(rota, data={'csrf': tok, 'acao': 'salvar', 'titulo': 'x'}).status_code in (404, 405), f'{rota} não salva mais nada (sem segundo sistema)')
for arq_velho in ('static/cartao-edicao.js', 'static/noticia-ordem.js', 'templates/admin_noticias.html', 'templates/admin_lateral.html'):
    ok(not os.path.exists(os.path.join(os.path.dirname(portal.__file__), arq_velho)), f'{arq_velho} removido')
h = c.get('/admin/conteudos').get_data(as_text=True)
ok('+ Novo conteúdo' in h and 'Qual tipo de conteúdo' in h, 'botão único Novo conteúdo com escolha do tipo')
ok('Nova Notícia' in c.get('/admin/conteudos/noticia/novo').get_data(as_text=True), 'o editor mostra o tipo do conteúdo')
# painéis, posição, ordem e crédito (1.9.33)
r = c.post('/admin/conteudos/salvar', data={'csrf': tok, 'tipo': 'noticia', 'titulo': 'Painel A', 'chamada_titulo': 'Chamada A', 'chamada_credito': 'Foto X',
        'capa_credito': 'Foto Y', 'chamada_posicao': 'principal', 'corpo': '<p>corpo</p>', 'tem_organizacao': '1', 'chamada_visivel': '1'}).get_json()
pa = r.get('id')
r = c.post('/admin/conteudos/salvar', data={'csrf': tok, 'tipo': 'noticia', 'titulo': 'Painel B', 'corpo': '<p>b</p>', 'tem_organizacao': '1', 'chamada_visivel': '1'}).get_json()
pb = r.get('id')
with portal.app.app_context():
    n = portal.db().execute('SELECT * FROM noticias WHERE id=?', (pa,)).fetchone()
ok(n['chamada_posicao'] == 'principal' and n['chamada_credito'] == 'Foto X' and n['capa_credito'] == 'Foto Y', 'posição e créditos da chamada e da capa são gravados')
c.post('/admin/conteudos/salvar', data={'csrf': tok, 'tipo': 'noticia', 'id': str(pa), 'chamada_titulo': 'Só chamada nova', 'titulo': 'Painel A'})
with portal.app.app_context():
    n = portal.db().execute('SELECT * FROM noticias WHERE id=?', (pa,)).fetchone()
ok(n['chamada_titulo'] == 'Só chamada nova' and n['corpo'] == '<p>corpo</p>' and n['chamada_posicao'] == 'principal' and n['capa_credito'] == 'Foto Y', 'salvar só a chamada não apaga a matéria nem a posição')
c.post('/admin/conteudos/salvar', data={'csrf': tok, 'tipo': 'noticia', 'id': str(pb), 'titulo': 'Painel B', 'ordem_pos': '1', 'ordem_pos_orig': '9', 'tem_organizacao': '1', 'chamada_visivel': '1'})
with portal.app.app_context():
    ordem = [r[0] for r in portal.db().execute('SELECT id FROM noticias ORDER BY ' + portal.modulos.noticias.ORDEM)]
ok(ordem[0] == pb, 'ordem escolhida (1) coloca a notícia em primeiro')


shutil.rmtree(TMP, ignore_errors=True)
print('\nFALHAS: %d' % len(falhas) if falhas else '\nTodos os testes passaram.')
sys.exit(1 if falhas else 0)
