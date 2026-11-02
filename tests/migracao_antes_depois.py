"""Migração real: abre um banco criado pela VERSÃO ANTERIOR do portal com a versão nova e confere os dados.

Uso:  python3 -I tests/migracao_antes_depois.py /caminho/da/versao-anterior
1. Cria, com o código anterior, um banco com dados reais de teste (cartões, comunicados, notícias, imagens).
2. Tira uma "foto" (contagens e conteúdo) de todas as tabelas.
3. Sobe o código novo sobre o MESMO banco e uploads.
4. Confere: nenhuma linha perdida, nenhum valor antigo alterado, cópia pré-migração criada, e o público igual."""
import hashlib, json, os, re, shutil, sqlite3, subprocess, sys, tempfile

NOVA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANTIGA = os.path.abspath(sys.argv[1])
TMP = tempfile.mkdtemp(prefix='portal-migracao-')
falhas = []
def ok(c, m):
    print(('OK    ' if c else 'FALHA ') + m)
    if not c: falhas.append(m)

def copia(origem, destino):
    shutil.copytree(origem, destino, ignore=shutil.ignore_patterns('*.db', '*.pre-exibicao-v1', '__pycache__', 'secret.key',
                                                                   'uploads', 'tests', '.git'))

ANT, NOV = os.path.join(TMP, 'antiga'), os.path.join(TMP, 'nova')
copia(ANTIGA, ANT)
env = dict(os.environ, INTRANET_ADMIN_SENHA='Teste1234')

semear = r'''
import os, sys, re
sys.path.insert(0, os.getcwd())
import app as portal
c = portal.app.test_client()
t = re.search(r'name="csrf" value="([^"]+)"', c.get('/login').get_data(as_text=True)).group(1)
c.post('/login', data={'csrf': t, 'usuario': 'admin', 'senha': 'Teste1234'})
t = re.search(r'name="csrf" value="([^"]+)"', c.get('/admin/conteudos').get_data(as_text=True)).group(1)
c.post('/admin/cartao-conteudo', data={'csrf': t, 'nome': 'Horário de atendimento', 'titulo_visivel': 'on', 'corpo': '<p>Das 8h às 17h</p>', 'url': '/ramais'})
c.post('/admin/cartao-conteudo', data={'csrf': t, 'nome': 'Banner sem título', 'corpo': '<p>Só texto</p>', 'url': 'https://exemplo.gov.br/x'})
with portal.app.app_context():
    con = portal.db()
    ch = con.execute("SELECT chave FROM cartoes_painel WHERE tipo='itens' LIMIT 1").fetchone()[0]
    con.execute("INSERT INTO lateral (tipo,titulo,conteudo,url,cartao) VALUES ('aviso','Aviso antigo','Texto antigo','https://exemplo.gov.br/a',?)", (ch,))
    con.execute("INSERT INTO noticias (slug,titulo,resumo,corpo,estado,publicar_em,destino_url) VALUES ('antiga','Notícia antiga','Resumo antigo','<p>x</p>','publicado','2020-01-01 08:00:00','')")
    con.commit()
'''
rs = subprocess.run([sys.executable, '-c', semear], cwd=ANT, env=env, capture_output=True, text=True)
if rs.returncode:
    print(rs.stderr[-1500:]); sys.exit(2)

def foto(db):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    saida = {}
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        saida[t] = [dict(r) for r in con.execute(f'SELECT * FROM {t} ORDER BY 1')]
    return saida

antes = foto(os.path.join(ANT, 'dados.db'))
ups_antes = sorted(os.listdir(os.path.join(ANT, 'static', 'uploads'))) if os.path.isdir(os.path.join(ANT, 'static', 'uploads')) else []
copia(NOVA, NOV)
shutil.copy(os.path.join(ANT, 'dados.db'), os.path.join(NOV, 'dados.db'))
shutil.copy(os.path.join(ANT, 'secret.key'), os.path.join(NOV, 'secret.key')) if os.path.exists(os.path.join(ANT, 'secret.key')) else None
if os.path.isdir(os.path.join(ANT, 'static', 'uploads')):
    shutil.copytree(os.path.join(ANT, 'static', 'uploads'), os.path.join(NOV, 'static', 'uploads'), dirs_exist_ok=True)

abre = r'''
import os, sys
sys.path.insert(0, os.getcwd())
import app as portal
c = portal.app.test_client()
h = c.get('/').get_data(as_text=True)
open('home.html', 'w', encoding='utf-8').write(h)
print(c.get('/').status_code, c.get('/noticias').status_code, c.get('/noticias/antiga').status_code)
'''
r = subprocess.run([sys.executable, '-c', abre], cwd=NOV, env=env, capture_output=True, text=True)
ok(r.stdout.split() == ['200', '200', '200'], 'versão nova abre o banco antigo (início, notícias e matéria respondem 200): ' + r.stdout.strip() + r.stderr[-300:])
depois = foto(os.path.join(NOV, 'dados.db'))
ok(set(antes) <= set(depois), 'nenhuma tabela foi removida')
def chave_de(t, r):
    return r.get('chave') if t == 'config' else tuple(sorted((k, str(v)) for k, v in r.items() if k in ('id', 'chave')))

for t, linhas in antes.items():
    novas_linhas = [r for r in depois.get(t, []) if t == 'config' and r['chave'] == 'exibicao_v1']
    atuais = [r for r in depois.get(t, []) if r not in novas_linhas]
    ok(len(atuais) == len(linhas), f'tabela {t}: mesmo número de linhas ({len(linhas)})')
    por_chave = {chave_de(t, r): r for r in atuais} if t == 'config' else None
    alterou = False
    for i, a in enumerate(linhas):
        d = por_chave.get(a['chave'], {}) if por_chave is not None else (atuais[i] if i < len(atuais) else {})
        for k, v in a.items():
            if d.get(k) != v:
                alterou = True
                print('   alterado:', t, k, repr(v), '->', repr(d.get(k)))
    ok(not alterou, f'tabela {t}: nenhum valor antigo foi alterado')
ok(any(r['chave'] == 'exibicao_v1' for r in depois['config']), 'marcador da migração registrado em config')
novas = {c for c in (depois['cartao_conteudo'][0] if depois['cartao_conteudo'] else {})} - {c for c in (antes['cartao_conteudo'][0] if antes['cartao_conteudo'] else {})}
ok({'titulo_publico', 'exibir_titulo', 'destino_tipo'} <= novas, 'colunas novas acrescentadas em cartao_conteudo: ' + ', '.join(sorted(novas)))
ok(os.path.exists(os.path.join(NOV, 'dados.db.pre-exibicao-v1')), 'cópia pré-migração criada (dados.db.pre-exibicao-v1)')
cp = foto(os.path.join(NOV, 'dados.db.pre-exibicao-v1'))
ok(all(cp[t] == antes[t] for t in antes if t != 'config'), 'a cópia pré-migração é idêntica ao banco antigo (serve de rollback)')
ck = {r['chave']: r for r in depois['cartao_conteudo']}
pub = {r['nome']: r for r in antes['cartoes_painel'] if r['tipo'] == 'conteudo'}
vis = [r for r in depois['cartao_conteudo'] if r['titulo_visivel'] == 1][0]
ok(vis['titulo_publico'] == 'Horário de atendimento' and vis['exibir_titulo'] == 1, 'título que o visitante via foi preservado como título público')
oc = [r for r in depois['cartao_conteudo'] if r['titulo_visivel'] == 0][0]
ok(oc['titulo_publico'] == 'Banner sem título' and oc['exibir_titulo'] == 0, 'título oculto continua oculto (valor copiado, exibição desligada)')
h = open(os.path.join(NOV, 'home.html'), encoding='utf-8').read()
ok('Horário de atendimento' in h and 'Das 8h às 17h' in h and 'Aviso antigo' in h and 'Texto antigo' in h and 'Notícia antiga' in h,
   'a página inicial mostra os mesmos conteúdos de antes')
ok('Banner sem título' not in re.sub(r'<[^>]+>', ' ', h), 'o nome interno do cartão sem título continua fora da página')
ok('href="/ramais"' in h and 'href="https://exemplo.gov.br/x"' in h and 'href="https://exemplo.gov.br/a"' in h, 'destinos antigos preservados')
shutil.rmtree(TMP, ignore_errors=True)
print('\nFALHAS: %d' % len(falhas) if falhas else '\nMigração conferida.')
sys.exit(1 if falhas else 0)
