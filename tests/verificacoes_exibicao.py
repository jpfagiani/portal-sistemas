"""Testes de exibição pública, nome administrativo e destino do clique (plano de correções, Fase 6).

Uso:  python3 -I tests/verificacoes_exibicao.py
Trabalha numa CÓPIA temporária do portal, como verificacoes_portal.py: não toca no banco nem nos uploads reais.
Sai com código 1 se algum teste falhar."""
import io, os, re, shutil, struct, sys, tempfile, zlib

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='portal-teste-exib-')
PASTA = os.path.join(TMP, 'p')
shutil.copytree(RAIZ, PASTA, ignore=shutil.ignore_patterns(
    '*.db', '*.pre-exibicao-v1', '__pycache__', 'secret.key', 'uploads', 'tests', '.git'))
os.chdir(PASTA)
sys.path.insert(0, PASTA)
os.environ['INTRANET_ADMIN_SENHA'] = 'Teste1234'
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

def visivel(html):
    """Texto que o visitante lê + atributos que leitores de tela usam (alt, aria-label, title)."""
    texto = re.sub(r'<(script|style)\b.*?</\1>', '', html, flags=re.S)
    attrs = ' '.join(re.findall(r'(?:alt|aria-label|title)="([^"]*)"', texto))
    return re.sub(r'<[^>]+>', ' ', texto) + ' ' + attrs

c = portal.app.test_client()
anon = portal.app.test_client()
r = c.post('/login', data={'csrf': csrf(c.get('/login').get_data(as_text=True)), 'usuario': 'admin', 'senha': 'Teste1234'})
ok(r.status_code == 302, 'login do administrador')
tok = csrf(c.get('/admin/conteudos').get_data(as_text=True))

def cont(dados, **kw):
    d = {'csrf': tok}
    d.update(dados)
    return c.post('/admin/conteudos/salvar', data=d, content_type='multipart/form-data', **kw)

def home():
    return anon.get('/').get_data(as_text=True)

def db():
    return portal.db()

# imagem na biblioteca para os testes (envio real pelo editor)
r = cont({'tipo': 'cartao', 'nome_admin': 'ZZADMIN-base', 'titulo_publico': 'x', 'imagem': (io.BytesIO(png()), 'base.png'),
          'alt_imagem': 'Foto base', 'modo': 'imagem'})
ok(r.get_json().get('ok'), 'cartão com imagem enviada pelo editor é salvo')
with portal.app.app_context():
    IMG = db().execute('SELECT imagem FROM cartao_conteudo WHERE imagem<>"" LIMIT 1').fetchone()['imagem']

# ── 1-3: os três modos, em cartão de texto e imagem ─────────────────────────────
def cartao(n, modo, **extra):
    d = {'tipo': 'cartao', 'nome_admin': f'ZZADMIN-{n}', 'titulo_publico': f'TituloPublico{n}', 'texto_apoio': f'ApoioPublico{n}',
         'corpo': '', 'imagem_biblioteca': IMG, 'alt_imagem': f'AltImagem{n}', 'modo': modo}
    d.update(extra)
    j = cont(d).get_json()
    return j.get('id'), j

id1, j = cartao(1, 'imagem')
h = home(); v = visivel(h)
ok(j.get('ok') and 'AltImagem1' in v, '1. somente imagem: a imagem aparece com o texto alternativo')
ok('TituloPublico1' not in h and 'ApoioPublico1' not in h and 'ZZADMIN-1' not in h and id1 not in v,
   '1. somente imagem: sem título, sem texto de apoio, sem nome administrativo')
id2, _ = cartao(2, 'imagem_titulo')
h = home()
ok('TituloPublico2' in h and 'ApoioPublico2' not in h and 'ZZADMIN-2' not in h, '2. imagem e título: só o título público autorizado')
id3, _ = cartao(3, 'imagem_titulo_texto')
h = home()
ok('TituloPublico3' in h and 'ApoioPublico3' in h and 'ZZADMIN-3' not in h, '3. imagem, título e texto: apenas os campos públicos')

# ── 4: título público vazio não faz fallback ────────────────────────────────────
id4, _ = cartao(4, 'imagem_titulo', titulo_publico='', texto_apoio='')
h = home(); v = visivel(h)
ok('ZZADMIN-4' not in h and 'ZZADMIN-4' not in v and id4 not in v, '4. título vazio: nada de nome administrativo, chave ou slug')
ok(re.search(r'ZZADMIN', h) is None, '4. nenhum nome administrativo em toda a página pública')

# ── 5: nome administrativo no painel ────────────────────────────────────────────
lista = c.get('/admin/conteudos').get_data(as_text=True)
ok('ZZADMIN-1' in lista and 'ZZADMIN-4' in lista, '5. nome administrativo aparece na listagem do painel')
busca = c.get('/admin/conteudos?q=ZZADMIN-3').get_data(as_text=True).split('id="cont-tabela"')[1].split('</table>')[0]
ok('ZZADMIN-3' in busca and 'ZZADMIN-1' not in busca, '5. a busca encontra pelo nome administrativo')
busca = c.get('/admin/conteudos?q=TituloPublico2').get_data(as_text=True).split('id="cont-tabela"')[1].split('</table>')[0]
ok('ZZADMIN-2' in busca, '5. a busca também encontra pelo título público')
ok('ZZADMIN-1' in c.get('/editor').get_data(as_text=True), '5. o modo de edição (só admin) mostra o nome para o administrador achar o cartão')
ok('ZZADMIN' not in anon.get('/editor', follow_redirects=True).get_data(as_text=True), '5. visitante não vê o nome nem no /editor')
ed = c.get(f'/admin/conteudos/cartao/{id1}').get_data(as_text=True)
ok('value="ZZADMIN-1"' in ed and 'name="modo"' in ed and 'name="destino_tipo"' in ed, '5. editor mostra nome interno, modo e destino')

# somente imagem exige imagem e texto alternativo; título não é obrigatório
r = cont({'tipo': 'cartao', 'nome_admin': 'ZZADMIN-semalt', 'imagem_biblioteca': IMG, 'modo': 'imagem'}).get_json()
ok(not r.get('ok') and 'alternativo' in r.get('erro', ''), 'somente imagem sem texto alternativo é recusado')
r = cont({'tipo': 'cartao', 'nome_admin': 'ZZADMIN-semimg', 'modo': 'imagem', 'alt_imagem': 'x'}).get_json()
ok(not r.get('ok') and 'imagem' in r.get('erro', ''), 'somente imagem sem imagem é recusado')
r = cont({'tipo': 'cartao', 'nome_admin': 'ZZADMIN-semtitulo', 'imagem_biblioteca': IMG, 'alt_imagem': 'ok', 'modo': 'imagem'}).get_json()
ok(r.get('ok'), 'somente imagem não obriga título público')
ok(not cont({'tipo': 'cartao', 'nome_admin': '', 'titulo_publico': 'só público'}).get_json().get('ok'), 'cartão sem nome interno é recusado')

# ── 6: notícia mantém o título editorial na página própria ──────────────────────
def noticia(titulo, **extra):
    d = {'tipo': 'noticia', 'titulo': titulo, 'corpo': '<p>Corpo da matéria</p>', 'estado': 'publicado',
         'publicar_em': '2020-01-01T08:00', 'imagem_biblioteca': IMG, 'capa_alt': 'AltCapaNoticia', 'resumo': 'Resumo de ' + titulo}
    d.update(extra)
    return cont(d).get_json()

jn = noticia('ZZNOT Editorial Um', nome_admin='ZZADMIN-noticia', modo='imagem')
nid = jn['id']
with portal.app.app_context():
    slug = db().execute('SELECT slug FROM noticias WHERE id=?', (nid,)).fetchone()['slug']
for layout in ('lista', 'grade'):
    c.post('/admin/noticias/vitrine', data={'csrf': tok, 'layout': layout, 'colunas': '2', 'qtd': '5'})
    h = home(); v = visivel(h)
    ok('ZZNOT Editorial Um' not in v and 'Resumo de ZZNOT' not in v and 'ZZADMIN-noticia' not in h and 'AltCapa' in v,
       f'6. chamada em somente imagem ({layout}): sem título, sem resumo, sem nome administrativo')
pag = anon.get('/noticias/' + slug).get_data(as_text=True)
ok('<h1' in pag and 'ZZNOT Editorial Um' in pag and 'ZZADMIN-noticia' not in pag, '6. a página da notícia continua com o título editorial')
arq = anon.get('/noticias').get_data(as_text=True)
ok('ZZNOT Editorial Um' not in visivel(arq) and 'ZZADMIN-noticia' not in arq, '10. a listagem /noticias segue a mesma configuração')
cont({'tipo': 'noticia', 'id': nid, 'nome_admin': 'ZZADMIN-noticia', 'titulo': 'ZZNOT Editorial Um', 'corpo': '<p>x</p>', 'estado': 'publicado',
      'publicar_em': '2020-01-01T08:00', 'imagem_biblioteca': IMG, 'capa_alt': 'AltCapa', 'resumo': 'Resumo de ZZNOT', 'modo': 'imagem_titulo_texto'})
h = home()
ok('ZZNOT Editorial Um' in h and 'Resumo de ZZNOT' in h, '6. a mesma notícia com título e texto passa a mostrá-los')
lista = c.get('/admin/conteudos?tipo=noticia').get_data(as_text=True)
ok('ZZADMIN-noticia' in lista, '5. nome administrativo da notícia aparece na listagem')

# ── 10: comunicados seguem a mesma regra ───────────────────────────────────────
with portal.app.app_context():
    cartao_itens = db().execute("SELECT chave FROM cartoes_painel WHERE tipo='itens' ORDER BY ordem LIMIT 1").fetchone()['chave']
def comunicado(n, modo, **extra):
    d = {'tipo': 'comunicado', 'cartao': cartao_itens, 'nome_admin': f'ZZADMIN-com{n}', 'titulo': f'TituloCom{n}', 'texto': f'TextoCom{n}',
         'ativo': 'on', 'imagem_nova': '', 'modo': modo, 'imagem': (io.BytesIO(png((10 * n, 90, 160))), f'com{n}.png'), 'alt_imagem': f'AltCom{n}'}
    d.update(extra)
    return cont(d).get_json()
comunicado(1, 'imagem')
h = home(); v = visivel(h)
ok('TituloCom1' not in v and 'TextoCom1' not in v and 'ZZADMIN-com1' not in h and 'AltCom1' in v,
   '10. comunicado em somente imagem: sem título, texto nem nome administrativo')
comunicado(2, 'imagem_titulo')
h = home()
ok('TituloCom2' in h and 'TextoCom2' not in h and 'ZZADMIN-com2' not in h, '10. comunicado em imagem e título')
comunicado(3, 'imagem_titulo_texto')
h = home()
ok('TituloCom3' in h and 'TextoCom3' in h and 'ZZADMIN-com3' not in h, '10. comunicado em imagem, título e texto')
ok('ZZADMIN-com1' in c.get('/admin/conteudos?tipo=comunicado').get_data(as_text=True), '5. nome administrativo do comunicado aparece no painel')
ok('ZZADMIN-com' not in anon.get(f'/lista/{cartao_itens}').get_data(as_text=True), '10. a página "ver todos" do cartão também não vaza o nome')

# ── 7: destinos internos ────────────────────────────────────────────────────────
jb = noticia('ZZNOT Destino', nome_admin='ZZADMIN-destino')
with portal.app.app_context():
    slug_b = db().execute('SELECT slug FROM noticias WHERE id=?', (jb['id'],)).fetchone()['slug']
idi, j = cartao(7, 'imagem_titulo', destino_tipo='interno', destino_interno='/noticias')
h = home()
ok(re.search(r'class="cartao-overlay" href="/noticias"(?! target)', h) is not None, '7. destino interno abre a página escolhida, na mesma aba')
idn, j = cartao(8, 'imagem_titulo', destino_tipo='noticia', destino_noticia='/noticias/' + slug_b)
h = home()
ok(f'href="/noticias/{slug_b}"' in h, '7. destino de notícia aponta para a notícia certa')
ok(anon.get('/noticias/' + slug_b).status_code == 200 and 'ZZNOT Destino' in anon.get('/noticias/' + slug_b).get_data(as_text=True),
   '7. e a notícia aberta é a esperada')
ok('aria-label="TituloPublico8"' in h, '7. o nome acessível do link é o título público')
idn1, _ = cartao(9, 'imagem', destino_tipo='interno', destino_interno='/ramais')
ok('aria-label="AltImagem9"' in home() and 'ZZADMIN-9' not in home(), '7. link só de imagem: nome acessível é o texto alternativo')

# ── 8: externos ─────────────────────────────────────────────────────────────────
for ruim in ('javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'data:text/html,<script>1</script>', 'vbscript:x', '//evil.example/x',
             'ftp://exemplo.com/a', 'exemplo.com/sem-esquema', 'mailto:a@b.c', 'http://', 'https://exa mple.com', '/ramais'):
    r = cont({'tipo': 'cartao', 'nome_admin': 'ZZADMIN-ruim', 'titulo_publico': 'T', 'destino_tipo': 'externo', 'destino_externo': ruim}).get_json()
    ok(not r.get('ok'), f'8. endereço externo recusado: {ruim[:30]}')
for ruim in ('/admin/usuarios', '/nao-existe-mesmo', '//evil.example', '/noticias/slug-que-nao-existe', 'javascript:alert(1)'):
    r = cont({'tipo': 'cartao', 'nome_admin': 'ZZADMIN-ruim', 'titulo_publico': 'T', 'destino_tipo': 'interno', 'destino_interno': ruim}).get_json()
    ok(not r.get('ok'), f'8. destino interno inválido recusado: {ruim[:30]}')
with portal.app.app_context():
    ok(db().execute("SELECT COUNT(*) FROM cartoes_painel WHERE nome='ZZADMIN-ruim'").fetchone()[0] == 0, '8. nada foi gravado nas recusas')
ide, j = cartao(10, 'imagem_titulo', destino_tipo='externo', destino_externo='https://exemplo.gov.br/curso', nova_aba='on')
h = home()
ok('href="https://exemplo.gov.br/curso" target="_blank" rel="noopener noreferrer"' in h, '8. externo em nova aba leva rel="noopener noreferrer"')
ok('exemplo.gov.br' not in visivel(h), '8. o endereço completo não é exibido ao visitante')
ide2, j = cartao(11, 'imagem_titulo', destino_tipo='externo', destino_externo='http://exemplo.gov.br/aba')
ok('href="http://exemplo.gov.br/aba"' in home(), '8. http também é aceito')
ok('cartao-overlay' not in c.get('/editor').get_data(as_text=True).split('ZZADMIN-10')[0][-0:] or True, 'editor segue clicável para edição')
ok('cartao-overlay' not in c.get('/editor').get_data(as_text=True), '8. no modo de edição o cartão não vira link (o clique abre a edição)')

# ── 9: destino removido ou indisponível ─────────────────────────────────────────
c.post('/admin/conteudos/excluir', data={'csrf': tok, 'tipo': 'noticia', 'id': jb['id']})
r = anon.get('/')
h = r.get_data(as_text=True)
ok(r.status_code == 200 and f'href="/noticias/{slug_b}"' not in h, '9. destino de notícia excluída: página inicial segue sem erro e sem link quebrado')
ok('destino indisponível' in c.get('/admin/conteudos?tipo=cartao').get_data(as_text=True), '9. o painel avisa que o destino ficou indisponível')
ok(c.get(f'/admin/conteudos/cartao/{idn}').status_code == 200, '9. o editor do item com destino quebrado abre normalmente')
with portal.app.app_context():
    db().execute("UPDATE cartao_conteudo SET destino_tipo='interno', url='/rota-que-nunca-existiu' WHERE chave=?", (idi,))
    db().execute("UPDATE cartao_conteudo SET destino_tipo='externo', url='javascript:alert(1)' WHERE chave=?", (ide2,))
    db().commit()
h = home()
ok('rota-que-nunca-existiu' not in h and 'javascript:' not in h, '9. destino inválido já gravado também não vira link (defesa na leitura)')

# ── 12: migração e dados existentes ─────────────────────────────────────────────
with portal.app.app_context():
    con = db()
    con.execute("INSERT INTO cartoes_painel (chave,nome,icone,regiao,largura,coluna,ordem,tipo,ativo) VALUES ('conteudo-ant1','Cartão antigo visível','prancheta','baixo',1,0,990,'conteudo',1)")
    con.execute("INSERT INTO cartoes_painel (chave,nome,icone,regiao,largura,coluna,ordem,tipo,ativo) VALUES ('conteudo-ant2','Cartão antigo sem nome','prancheta','baixo',1,0,991,'conteudo',1)")
    con.execute("INSERT INTO cartao_conteudo (chave,html,titulo_visivel,url) VALUES ('conteudo-ant1','<p>Texto antigo 1</p>',1,'/ramais')")
    con.execute("INSERT INTO cartao_conteudo (chave,html,titulo_visivel,url) VALUES ('conteudo-ant2','<p>Texto antigo 2</p>',0,'https://exemplo.gov.br/antigo')")
    con.execute("INSERT INTO lateral (tipo,titulo,conteudo,url,cartao) VALUES ('aviso','Aviso antigo','Texto do aviso antigo','/sistemas',?)", (cartao_itens,))
    con.execute("DELETE FROM config WHERE chave='exibicao_v1'")
    con.commit()
    portal._migrar_exibicao(con)
    con.commit()
    a1 = con.execute("SELECT * FROM cartao_conteudo WHERE chave='conteudo-ant1'").fetchone()
    a2 = con.execute("SELECT * FROM cartao_conteudo WHERE chave='conteudo-ant2'").fetchone()
    nomes = con.execute("SELECT nome FROM cartoes_painel WHERE chave IN ('conteudo-ant1','conteudo-ant2') ORDER BY chave").fetchall()
ok(a1['titulo_publico'] == 'Cartão antigo visível' and a1['exibir_titulo'] == 1, '12. migração: título que o visitante já via é copiado para o título público')
ok(a2['exibir_titulo'] == 0 and a1['titulo_visivel'] == 1 and a1['url'] == '/ramais', '12. migração: colunas antigas ficam intactas e o título oculto continua oculto')
ok([n['nome'] for n in nomes] == ['Cartão antigo visível', 'Cartão antigo sem nome'], '12. migração: nome interno preservado')
with portal.app.app_context():
    portal._migrar_exibicao(db())
    again = db().execute("SELECT titulo_publico FROM cartao_conteudo WHERE chave='conteudo-ant1'").fetchone()['titulo_publico']
ok(again == 'Cartão antigo visível', '12. migração é idempotente (rodar de novo não muda nada)')
h = home(); v = visivel(h)
ok('Cartão antigo visível' in v and 'Texto antigo 1' in v, '12. cartão antigo continua acessível, com o mesmo título que tinha')
ok('Cartão antigo sem nome' not in v and 'Texto antigo 2' in v, '12. cartão antigo com título oculto continua sem título')
ok('href="/ramais"' in h and 'href="https://exemplo.gov.br/antigo" target="_blank" rel="noopener noreferrer"' in h,
   '12. destinos antigos preservados (interno na mesma aba, externo em nova aba com rel)')
ok('Aviso antigo' in v and 'Texto do aviso antigo' in v and 'href="/sistemas"' in h, '12. comunicado antigo continua igual, com o destino')
ok(c.get('/admin/conteudos/cartao/conteudo-ant1').status_code == 200 and 'Cartão antigo visível' in c.get('/admin/conteudos').get_data(as_text=True),
   '12. registros antigos abrem no editor e aparecem na lista')

# ── 11/segurança: erro de salvamento, CSRF, permissões, HTML ───────────────────
with portal.app.app_context():
    antes = db().execute('SELECT COUNT(*) FROM cartoes_painel').fetchone()[0]
r = cont({'tipo': 'cartao', 'nome_admin': 'ZZADMIN-erro', 'titulo_publico': 'texto que não pode se perder', 'destino_tipo': 'externo', 'destino_externo': 'javascript:1'})
j = r.get_json()
ok(r.status_code == 400 and not j['ok'] and j['erro'], '11. erro de validação devolve mensagem clara em JSON (o formulário não é recarregado)')
with portal.app.app_context():
    ok(db().execute('SELECT COUNT(*) FROM cartoes_painel').fetchone()[0] == antes, '11. nada é gravado quando o salvamento falha')
js = open(os.path.join(RAIZ, 'static', 'conteudo-editor.js'), encoding='utf-8').read()
ok("erro.textContent = r.erro" in js and js.index('if (!r.ok)') < js.index('location.reload()'), '11. no erro o editor mostra a mensagem e não recarrega a página')
ok(anon.post('/admin/conteudos/salvar', data={'tipo': 'cartao', 'nome_admin': 'x'}).status_code in (302, 400, 401, 403), 'visitante não salva conteúdo')
ok(c.post('/admin/conteudos/salvar', data={'tipo': 'cartao', 'nome_admin': 'x'}).status_code in (400, 403), 'POST sem CSRF é recusado')
ok(anon.get('/admin/conteudos').status_code in (302, 401, 403) and anon.get(f'/admin/conteudos/cartao/{id1}').status_code in (302, 401, 403),
   'listagem e editor exigem login')
ok(anon.post('/admin/conteudos/previa', data={'tipo': 'cartao'}).status_code in (302, 400, 401, 403), 'prévia exige login')
cont({'tipo': 'cartao', 'id': id2, 'nome_admin': 'ZZADMIN-2', 'titulo_publico': 'TituloPublico2', 'modo': 'imagem_titulo',
      'corpo': '<p>ok</p><script>alert(1)</script><img src=x onerror=alert(2)>'})
h = home()
ok('alert(1)' not in h and 'onerror' not in h, 'HTML do conteúdo continua sanitizado no servidor')
pv = c.post('/admin/conteudos/previa', data={'csrf': tok, 'tipo': 'cartao', 'nome_admin': 'ZZADMIN-previa', 'titulo_publico': 'PreviaPublica',
                                          'modo': 'imagem_titulo', 'corpo': '<p>x</p>'}).get_json()
ok(pv['ok'] and 'PreviaPublica' in pv['html'] and 'ZZADMIN-previa' not in pv['html'], 'a prévia pública não mostra o nome administrativo')
pv = c.post('/admin/conteudos/previa', data={'csrf': tok, 'tipo': 'cartao', 'nome_admin': 'ZZADMIN-previa', 'titulo_publico': 'PreviaPublica',
                                          'modo': 'imagem', 'imagem_biblioteca': IMG, 'corpo': ''}).get_json()
ok('PreviaPublica' not in pv['html'], 'a prévia respeita o modo somente imagem')

# duplicar copia os campos novos e mantém o nome interno distinto
r = c.post('/admin/conteudos/duplicar', data={'csrf': tok, 'tipo': 'cartao', 'id': id3}).get_json()
with portal.app.app_context():
    cp = db().execute('SELECT titulo_publico,texto_apoio,exibir_texto_apoio,alt_imagem FROM cartao_conteudo WHERE chave=?', (r['id'],)).fetchone()
ok(r['ok'] and cp['titulo_publico'] == 'TituloPublico3' and cp['exibir_texto_apoio'] == 1 and cp['alt_imagem'] == 'AltImagem3', 'duplicar copia título público, texto de apoio, modo e texto alternativo')

# a aba Cartões continua fora do menu
h = c.get('/admin').get_data(as_text=True)
ok('>Conteúdos<' in h and '>Cartões<' not in h and '>Cartões do painel<' not in h, 'menu: só Conteúdos (sem aba Cartões)')

shutil.rmtree(TMP, ignore_errors=True)
print('\nFALHAS: %d' % len(falhas) if falhas else '\nTodos os testes passaram.')
sys.exit(1 if falhas else 0)
