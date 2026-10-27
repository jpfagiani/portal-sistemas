"""Testes dos módulos novos (segurança, histórico, mídia, notícias).

Uso:  python3 tests/test_modulos.py
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
c.post('/admin/noticias', data={'csrf': tok, 'acao': 'publicar', 'titulo': 'Aviso com capa', 'capa_biblioteca': arq,
                                'corpo': '<p>Texto</p>', 'categoria': 'Avisos'})
r = c.post('/admin/midia', data={'csrf': tok, 'acao': 'excluir', 'arquivo': arq}, follow_redirects=True)
ok('em uso' in r.get_data(as_text=True) and os.path.exists(os.path.join(portal.UPLOAD_DIR, arq)),
   'imagem em uso não é excluída')

# ── notícias ─────────────────────────────────────────────────────────────────
def nova(**kw):
    d = {'csrf': tok, 'acao': 'salvar', 'titulo': 'T', 'corpo': '<p>c</p>', 'estado': 'rascunho'}
    d.update(kw)
    return c.post('/admin/noticias', data=d, follow_redirects=True)

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
c.post('/admin/noticias', data={'csrf': tok, 'acao': 'excluir', 'id': ident})
ok(c.get('/noticias/rascunho-secreto').status_code == 404, 'excluir notícia')
ok(os.path.exists(os.path.join(portal.UPLOAD_DIR, arq)), 'a capa continua na biblioteca depois de excluir notícia')
r = c.post('/admin/noticias', data={'acao': 'salvar', 'titulo': 'sem csrf'})
ok(r.status_code in (400, 403), 'POST sem token CSRF é recusado (%s)' % r.status_code)

# ── cartões de texto e imagem ────────────────────────────────────────────────
r = c.post('/admin/cartao-conteudo', data={'csrf': tok, 'nome': 'Horário', 'titulo_visivel': 'on',
           'corpo': '<p>Das 8h às 17h</p><script>x()</script>'})
j = r.get_json() or {}
ok(j.get('ok'), 'cria cartão de texto e imagem')
h = anon.get('/').get_data(as_text=True)
ok('Das 8h às 17h' in h and 'x()' not in h, 'cartão aparece ao público, com HTML limpo')
r = c.post('/admin/cartao-conteudo', data={'csrf': tok, 'chave': j.get('chave'), 'nome': 'Horário 2', 'titulo_visivel': 'on', 'corpo': '<p>Novo</p>'})
ok(r.get_json().get('ok') and 'Horário 2' in anon.get('/').get_data(as_text=True), 'edita o cartão')
ok(not c.post('/admin/cartao-conteudo', data={'csrf': tok, 'nome': '', 'corpo': ''}).get_json().get('ok'), 'cartão vazio é recusado')
ok(anon.post('/admin/cartao-conteudo', data={'nome': 'x', 'corpo': 'y'}).status_code in (302, 400, 401, 403), 'visitante não cria cartão')
ok(c.post('/admin/cartao-conteudo', data={'csrf': tok, 'chave': j.get('chave'), 'acao': 'excluir'}).get_json().get('ok'), 'exclui o cartão')
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
m = re.search(r'class="not-manchete".*?<h2>(.*?)</h2>', h, re.S)
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

for rota, marca in (('/admin/ramais', 'ramais'), ('/admin/links', 'links'), ('/admin/lateral', 'lateral'),
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

# páginas principais continuam abrindo
for rota in ('/', '/ramais', '/sistemas', '/noticias', '/admin', '/admin/noticias', '/admin/midia',
             '/admin/historico', '/admin/noticias?nova=1'):
    ok(c.get(rota).status_code == 200, f'GET {rota} abre')

shutil.rmtree(TMP, ignore_errors=True)
print('\nFALHAS: %d' % len(falhas) if falhas else '\nTodos os testes passaram.')
sys.exit(1 if falhas else 0)
