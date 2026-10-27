/* Cartões de texto e imagem: criar e editar na própria página inicial.
   "+ Texto ou imagem" abre a janela em branco; clicar no nome de um cartão
   desse tipo abre a janela com o conteúdo dele. O servidor limpa o HTML. */
(function () {
  'use strict';
  var fundo = document.getElementById('conteudo-fundo');
  if (!fundo) return;
  var form = document.getElementById('form-conteudo');
  var area = form.querySelector('.re-area');
  var erro = document.getElementById('conteudo-erro');
  var excluir = document.getElementById('conteudo-excluir');
  var dados = {};
  try { dados = JSON.parse(document.getElementById('dados-conteudo').textContent) || {}; } catch (e) {}

  function abre(chave) {
    var d = dados[chave] || {nome: '', html: '', titulo_visivel: true};
    form.elements.chave.value = chave || '';
    form.elements.nome.value = d.nome;
    form.elements.titulo_visivel.checked = d.titulo_visivel;
    area.innerHTML = d.html;
    excluir.hidden = !chave;
    erro.textContent = '';
    fundo.style.display = 'flex';
    document.getElementById('conteudo-titulo').textContent = chave ? 'Editar cartão' : 'Novo cartão de texto e imagem';
    (d.html ? area : form.elements.nome).focus();
  }
  function fecha() { fundo.style.display = 'none'; }

  document.addEventListener('click', function (e) {
    var novo = e.target.closest('[data-novo-conteudo]');
    if (novo) { e.preventDefault(); abre(''); return; }
    var ed = e.target.closest('[data-editar-conteudo]');
    if (ed) { e.preventDefault(); abre(ed.dataset.editarConteudo); }
  });
  document.getElementById('conteudo-cancelar').addEventListener('click', fecha);
  fundo.addEventListener('mousedown', function (e) { if (e.target === fundo) fecha(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && fundo.style.display !== 'none') fecha(); });

  function envia(extra) {
    var fd = new FormData(form);
    fd.set('corpo', area.innerHTML);
    if (extra) Object.keys(extra).forEach(function (k) { fd.set(k, extra[k]); });
    return fetch(form.action, {method: 'POST', body: fd, credentials: 'same-origin'})
      .then(function (r) { return r.json().catch(function () { return {ok: false, erro: 'Erro ao salvar.'}; }); },
            function () { return {ok: false, erro: 'Sem conexão com o servidor.'}; });
  }
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    erro.textContent = 'Salvando…';
    envia().then(function (r) { if (r.ok) location.reload(); else erro.textContent = r.erro || 'Não foi possível salvar.'; });
  });
  excluir.addEventListener('click', function () {
    if (!window.confirm('Excluir este cartão? As imagens continuam na biblioteca.')) return;
    envia({acao: 'excluir'}).then(function (r) { if (r.ok) location.reload(); else erro.textContent = r.erro || 'Não foi possível excluir.'; });
  });
})();
