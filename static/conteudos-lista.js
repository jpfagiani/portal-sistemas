/* Lista de Conteúdos: excluir e duplicar sem recarregar o formulário todo. */
(function () {
  'use strict';
  var cfg = {};
  try { cfg = JSON.parse(document.getElementById('cont-urls').textContent); } catch (e) { return; }
  var aviso = document.getElementById('cont-aviso');
  function envia(url, tr) {
    var fd = new FormData();
    fd.set('csrf', cfg.csrf); fd.set('tipo', tr.dataset.tipo); fd.set('id', tr.dataset.id);
    aviso.textContent = '';
    return fetch(url, {method: 'POST', body: fd, credentials: 'same-origin'})
      .then(function (r) { return r.json().catch(function () { return {ok: false, erro: 'Erro inesperado.'}; }); },
            function () { return {ok: false, erro: 'Sem conexão com o servidor.'}; });
  }
  document.getElementById('cont-tabela').addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b || b.disabled) return;
    var tr = b.closest('tr');
    if (b.hasAttribute('data-excluir')) {
      if (!window.confirm('Excluir “' + b.dataset.titulo + '”? Esta ação não pode ser desfeita.')) return;
      b.disabled = true;
      envia(cfg.excluir, tr).then(function (r) { if (r.ok) location.reload(); else { b.disabled = false; aviso.textContent = r.erro || 'Não foi possível excluir.'; } });
    } else if (b.hasAttribute('data-duplicar')) {
      b.disabled = true;
      envia(cfg.duplicar, tr).then(function (r) { if (r.ok) location.reload(); else { b.disabled = false; aviso.textContent = r.erro || 'Não foi possível duplicar.'; } });
    }
  });
})();
