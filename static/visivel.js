/* Caixa "visível" das listas do painel.

   Cada <input class="marca-visivel" data-lista data-id> grava na hora em
   /admin/visivel, sem abrir o item para editar. Se o servidor recusar ou a rede
   cair, a caixa volta ao que era e o erro aparece — nunca fica marcada sem ter
   salvo. O selo ao lado ("visível" / "oculto") acompanha o resultado real. */
(function () {
  'use strict';
  var csrfEl = document.querySelector('input[name=csrf]');
  var caixas = document.querySelectorAll('.marca-visivel');
  if (!csrfEl || !caixas.length) return;

  function aviso(texto, erro) {
    var d = document.createElement('div');
    d.className = 'toast-ordem' + (erro ? ' toast-erro' : '');
    d.setAttribute('role', erro ? 'alert' : 'status');
    d.textContent = texto;
    document.body.appendChild(d);
    setTimeout(function () { d.classList.add('sumindo'); }, 1800);
    setTimeout(function () { d.remove(); }, 2400);
  }

  function selo(cx, ativo) {
    var tag = cx.parentNode.querySelector('[data-vis]');
    if (!tag) return;
    tag.textContent = ativo ? 'visível' : 'oculto';
    tag.classList.toggle('tag-ok', ativo);
  }

  Array.prototype.forEach.call(caixas, function (cx) {
    cx.addEventListener('change', function () {
      var quer = cx.checked;
      var corpo = new URLSearchParams({
        csrf: csrfEl.value, lista: cx.dataset.lista, id: cx.dataset.id, valor: quer ? '1' : '0'
      });
      cx.disabled = true;
      fetch('/admin/visivel', {method: 'POST', body: corpo, credentials: 'same-origin'})
        .then(function (r) {
          return r.json().catch(function () { return {}; }).then(function (d) { return {http: r, d: d}; });
        })
        .then(function (x) {
          if (!x.http.ok || !x.d.ok) throw new Error(x.d.erro || 'Não consegui salvar. Atualize a página e tente de novo.');
          selo(cx, x.d.ativo);
          var linha = cx.closest('tr, .banner-item');
          if (linha) linha.classList.toggle('item-oculto', !x.d.ativo);
          aviso(x.d.ativo ? 'Item visível.' : 'Item oculto.');
        })
        .catch(function (e) {
          cx.checked = !quer;
          selo(cx, !quer);
          aviso(e.message || 'Sem conexão com o servidor.', true);
        })
        .then(function () { cx.disabled = false; });
    });
  });
})();
