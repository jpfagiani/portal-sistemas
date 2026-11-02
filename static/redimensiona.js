/*  Redimensionar imagem arrastando qualquer lado ou canto (8 alças).

    Uso: Redim.liga(caixa, imagem, {aoMudar: function (w, h, final) {}})
      - `caixa` envolve a imagem (position:relative); as alças ficam dentro dela;
      - arrastar para fora aumenta, para dentro diminui; nos cantos a proporção atual é mantida
        (nos lados, largura e altura são livres; Shift mantém a proporção);
      - `aoMudar` recebe a largura e a altura em px; `final` é true ao soltar o mouse.
    Em caixas [data-redim-url] (itens da página principal em modo de edição) grava sozinho. */
(function () {
  'use strict';
  var DIRS = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];
  var CURSOR = {nw: 'nwse', se: 'nwse', ne: 'nesw', sw: 'nesw', n: 'ns', s: 'ns', e: 'ew', w: 'ew'};
  var MIN_W = 40, MIN_H = 30, MAX = 2000;

  function liga(caixa, img, opc) {
    opc = opc || {};
    if (!caixa || !img || caixa.dataset.redimLigado) return;
    caixa.dataset.redimLigado = '1';
    caixa.classList.add('redim-caixa');
    var dica = document.createElement('span'); dica.className = 'redim-dica'; caixa.appendChild(dica);
    DIRS.forEach(function (d) {
      var a = document.createElement('span');
      a.className = 'redim-alca redim-' + d; a.dataset.dir = d; a.style.cursor = CURSOR[d] + '-resize';
      a.title = 'Arraste para mudar o tamanho'; caixa.appendChild(a);
      a.addEventListener('pointerdown', function (e) { comeca(e, d, a); });
    });
    function comeca(e, d, a) {
      if (e.button > 0) return;
      e.preventDefault(); e.stopPropagation(); a.setPointerCapture(e.pointerId);
      var r0 = img.getBoundingClientRect(), x0 = e.clientX, y0 = e.clientY, w0 = r0.width, h0 = r0.height;
      var lim = (caixa.parentElement ? caixa.parentElement.getBoundingClientRect().width : MAX) || MAX;
      var w = w0, h = h0, moveu = false;
      function move(ev) {
        var dx = ev.clientX - x0, dy = ev.clientY - y0;
        if (!moveu && Math.abs(dx) < 3 && Math.abs(dy) < 3) return;
        moveu = true; w = w0; h = h0;
        if (d.indexOf('e') >= 0) w = w0 + dx; else if (d.indexOf('w') >= 0) w = w0 - dx;
        if (d.indexOf('s') >= 0) h = h0 + dy; else if (d.indexOf('n') >= 0) h = h0 - dy;
        if (d.length === 2 || ev.shiftKey) {
          var k = d.length === 2 ? Math.max(w / w0, h / h0) : (d === 'e' || d === 'w' ? w / w0 : h / h0);
          w = w0 * k; h = h0 * k;
        }
        w = Math.round(Math.max(MIN_W, Math.min(lim, MAX, w))); h = Math.round(Math.max(MIN_H, Math.min(MAX, h)));
        img.style.width = w + 'px'; img.style.height = h + 'px'; img.style.maxWidth = 'none';
        dica.textContent = w + ' × ' + h + ' px';
        if (opc.aoMudar) opc.aoMudar(w, h, false);
      }
      function fim() {
        a.removeEventListener('pointermove', move); a.removeEventListener('pointerup', fim); a.removeEventListener('pointercancel', fim);
        dica.textContent = '';
        if (moveu) { grava(caixa, w, h); if (opc.aoMudar) opc.aoMudar(w, h, true); }
      }
      a.addEventListener('pointermove', move); a.addEventListener('pointerup', fim); a.addEventListener('pointercancel', fim);
    }
    /* Duplo clique numa alça: volta ao tamanho padrão. */
    caixa.addEventListener('dblclick', function (e) {
      if (!e.target.closest('.redim-alca')) return;
      img.style.width = ''; img.style.height = ''; img.style.maxWidth = '';
      grava(caixa, 0, 0); if (opc.aoMudar) opc.aoMudar(0, 0, true);
    });
  }

  function grava(caixa, w, h) {
    if (!caixa.dataset.redimUrl) return;
    var c = new URLSearchParams(); c.set('csrf', caixa.dataset.csrf || ''); c.set('pw', w); c.set('ph', h);
    fetch(caixa.dataset.redimUrl, {method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: c.toString()})
      .then(function (r) { if (!r.ok) throw new Error(); })
      .catch(function () { window.alert('Não foi possível salvar o tamanho. Recarregue a página e tente de novo.'); });
  }

  window.Redim = {liga: liga};
  /* Imagens de itens da página principal (modo de edição) e qualquer caixa marcada com data-redim. */
  function auto() {
    document.querySelectorAll('[data-redim]').forEach(function (c) {
      var i = c.querySelector('img,video'); if (i) liga(c, i, {aoMudar: c.__aoMudar});
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', auto); else auto();
})();
