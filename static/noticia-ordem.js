/* Botões ▲ ▼ da lista de notícias: mesma gravação do arrastar-e-soltar
   (ordenar.js), para quem prefere clicar ou não usa mouse. */
(function () {
  var caixa = document.querySelector('tbody[data-ordenavel]');
  if (!caixa) return;

  function linhas() {
    return Array.prototype.filter.call(caixa.children, function (e) { return e.dataset && e.dataset.id; });
  }
  function aviso(texto, erro) {
    var d = document.createElement('div');
    d.className = 'toast-ordem' + (erro ? ' toast-erro' : '');
    d.textContent = texto;
    document.body.appendChild(d);
    setTimeout(function () { d.classList.add('sumindo'); }, 1800);
    setTimeout(function () { d.remove(); }, 2400);
  }
  function numerar() {
    linhas().forEach(function (tr, i) {
      var c = tr.querySelector('[data-coluna-ordem]');
      if (c && c.textContent !== String(i + 1)) c.textContent = i + 1;   // só escreve se mudou: evita laço do observador
    });
  }

  caixa.addEventListener('click', function (e) {
    var b = e.target.closest('[data-mover]');
    if (!b) return;
    var tr = b.closest('tr'), passo = parseInt(b.dataset.mover, 10);
    var alvo = passo < 0 ? tr.previousElementSibling : tr.nextElementSibling;
    if (!alvo || !alvo.dataset.id) return;
    caixa.insertBefore(tr, passo < 0 ? alvo : alvo.nextSibling);
    numerar();
    var dados = new FormData();
    dados.append('csrf', caixa.dataset.csrf);
    dados.append('acao', 'ordenar');
    dados.append('ids', linhas().map(function (l) { return l.dataset.id; }).join(','));
    fetch(caixa.dataset.ordenavel, { method: 'POST', body: dados, credentials: 'same-origin' })
      .then(function (r) { aviso(r.ok ? 'Ordem salva.' : 'Não foi possível salvar a ordem (' + r.status + ').', !r.ok); })
      .catch(function () { aviso('Falha de conexão ao salvar a ordem.', true); });
    b.focus();
  });

  // O arrastar (ordenar.js) renumera de 0; aqui a contagem começa em 1.
  new MutationObserver(numerar).observe(caixa, { childList: true, subtree: true, characterData: true });
})();
