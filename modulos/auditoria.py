"""Histórico das alterações feitas na administração.

Cada alteração bem-sucedida em /admin/* entra aqui com quem fez, o que foi e
quando. Senhas e chaves nunca são gravadas."""
from flask import render_template, request, session

import app as nucleo

app = nucleo.app

SCHEMA = """
CREATE TABLE IF NOT EXISTS auditoria (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    quando  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    usuario TEXT NOT NULL DEFAULT '',
    ip      TEXT NOT NULL DEFAULT '',
    acao    TEXT NOT NULL,
    objeto  TEXT NOT NULL DEFAULT '',
    detalhe TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_auditoria_quando ON auditoria (quando);
"""

# Rotas cujos POST são ruído (arrastar cartões, reordenar listas): não entram.
_IGNORAR = {'admin_cartao_pos', 'admin_imagem_tamanho', 'admin_layout_livre',
            'admin_visivel'}     # esta última se registra sozinha, com o nome do item
_SEGREDOS = ('senha', 'csrf', 'token', 'chave_secreta')
# Campos que dizem "sobre o que foi a alteração", em ordem de preferência.
_NOMES = ('nome', 'titulo', 'setor', 'usuario', 'texto')


def registrar(acao, objeto='', detalhe='', usuario=None):
    con = nucleo.db()
    con.execute('INSERT INTO auditoria (usuario,ip,acao,objeto,detalhe) VALUES (?,?,?,?,?)',
                (usuario if usuario is not None else session.get('user', ''),
                 request.remote_addr or '', acao[:80], (objeto or '')[:200], (detalhe or '')[:500]))
    con.commit()


def _houve_erro():
    return any(cat == 'erro' for cat, _ in session.get('_flashes', []))


@app.after_request
def _registra_post_admin(resp):
    try:
        if (request.method != 'POST' or not request.path.startswith('/admin')
                or not session.get('admin') or request.endpoint in _IGNORAR
                or resp.status_code >= 400):
            return resp
        form = request.form
        acao = form.get('acao') or 'salvar'
        if acao == 'ordenar' or form.get('ajax') and acao == 'mover':
            return resp
        if _houve_erro():
            return resp
        # JSON de erro da edição direta
        if resp.is_json and not (resp.get_json(silent=True) or {}).get('ok', True):
            return resp
        objeto = (form.get('bloco') or (request.view_args or {}).get('chave') or
                  (request.endpoint or '').replace('admin_', ''))
        nome = next((form.get(k) for k in _NOMES if form.get(k)), '')
        partes = []
        if form.get('id'):
            partes.append(f"id={form.get('id')}")
        if form.get('tipo'):
            partes.append(f"tipo={form.get('tipo')}")
        if nome:
            partes.append(nome.strip()[:120])
        registrar(acao, objeto, ' · '.join(partes))
    except Exception:
        pass        # o histórico nunca pode derrubar a ação do administrador
    return resp


@app.route('/admin/historico')
@nucleo.admin_obrigatorio
def admin_historico():
    con = nucleo.db()
    busca = (request.args.get('q') or '').strip()
    pagina = max(1, nucleo._int(request.args.get('p'), 1))
    por = 50
    onde, args = '', []
    if busca:
        onde = ' WHERE usuario LIKE ? OR acao LIKE ? OR objeto LIKE ? OR detalhe LIKE ?'
        args = [f'%{busca}%'] * 4
    total = con.execute('SELECT COUNT(*) FROM auditoria' + onde, args).fetchone()[0]
    linhas = con.execute('SELECT * FROM auditoria' + onde +
                         ' ORDER BY id DESC LIMIT ? OFFSET ?', args + [por, (pagina - 1) * por]).fetchall()
    # `pg` e não `pagina`: o admin_base usa `pagina` para marcar a aba ativa, e a
    # colisão derrubava o histórico assim que passava de uma página (50 registros).
    return render_template('admin_historico.html', linhas=linhas, busca=busca, pg=pagina,
                           paginas=max(1, -(-total // por)), total=total)
