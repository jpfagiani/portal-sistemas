/* Tamanho da letra em pixels, no lugar de "Pequeno / Normal / Grande".

   Melhora qualquer barra de formatação (.re-barra) que tenha o seletor
   "Tamanho do texto": esconde o seletor e põe um campo em pixels com − e +
   (setas ↑ ↓ do teclado também). Selecione o trecho e digite, por exemplo, 18.
   Vale para cartões, notícias, módulos e páginas, porque todos usam a mesma barra. */
(function () {
  'use strict';
  var MIN = 8, MAX = 96;

  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }

  function melhora(barra) {
    if (barra.dataset.rePx) return;
    var seletor = barra.querySelector('select[title="Tamanho do texto"], select.re-tam');
    var area = barra.parentNode && barra.parentNode.querySelector('.re-area');
    if (!seletor || !area) return;
    barra.dataset.rePx = '1';
    seletor.style.display = 'none';

    var salva = null;
    var grupo = el('span', 're-px-grupo');
    var menos = el('button', '', '−'), mais = el('button', '', '+');
    menos.type = mais.type = 'button'; menos.title = 'Diminuir a letra'; mais.title = 'Aumentar a letra';
    var campo = el('input', 're-px'); campo.type = 'text'; campo.inputMode = 'numeric'; campo.size = 3; campo.maxLength = 3;
    campo.setAttribute('list', 're-px-lista'); campo.placeholder = 'px';
    var DICA = 'Tamanho da letra em pixels (selecione o texto antes)';
    campo.title = DICA; campo.setAttribute('aria-label', 'Tamanho da letra em pixels');
    if (!document.getElementById('re-px-lista')) {
      var dl = el('datalist'); dl.id = 're-px-lista';
      [10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 60, 72, 96].forEach(function (n) { var o = el('option'); o.value = n; dl.appendChild(o); });
      document.body.appendChild(dl);
    }
    grupo.appendChild(el('span', 're-rot', 'Letra:')); grupo.appendChild(menos); grupo.appendChild(campo);
    grupo.appendChild(el('span', 're-rot', 'px')); grupo.appendChild(mais);
    barra.insertBefore(grupo, seletor);

    function restaura() {
      area.focus();
      if (salva) { var s = window.getSelection(); s.removeAllRanges(); s.addRange(salva); }
    }
    function pxAtual() {
      var n = salva && salva.startContainer;
      if (!n) return '';
      if (n.nodeType === 3) n = n.parentNode;
      return n && n.nodeType === 1 ? String(Math.round(parseFloat(getComputedStyle(n).fontSize))) : '';
    }
    function aplica(px) {
      px = Math.max(MIN, Math.min(MAX, Math.round(px)));
      if (!salva || salva.collapsed) {
        campo.classList.add('re-px-aviso'); campo.title = 'Selecione o trecho de texto que quer mudar';
        setTimeout(function () { campo.classList.remove('re-px-aviso'); campo.title = DICA; }, 2500);
        return;
      }
      restaura();
      var s = window.getSelection();
      try { document.execCommand('styleWithCSS', false, false); } catch (e) {}
      document.execCommand('fontSize', false, '7');          /* marca o trecho; abaixo vira px */
      var novos = [];
      area.querySelectorAll('font[size="7"]').forEach(function (f) {
        var sp = document.createElement('span'); sp.style.fontSize = px + 'px';
        while (f.firstChild) sp.appendChild(f.firstChild);
        f.parentNode.replaceChild(sp, f); novos.push(sp);
      });
      novos.forEach(function (sp) {                          /* tamanhos antigos dentro do trecho deixam de valer */
        sp.querySelectorAll('[style*="font-size"]').forEach(function (c) {
          c.style.removeProperty('font-size'); if (!c.getAttribute('style')) c.removeAttribute('style');
        });
      });
      if (novos.length) {
        var r = document.createRange(); r.setStartBefore(novos[0]); r.setEndAfter(novos[novos.length - 1]);
        s.removeAllRanges(); s.addRange(r); salva = r.cloneRange();
      }
      campo.value = px;
    }
    function lido() { var v = parseInt(campo.value, 10); return isNaN(v) ? null : v; }
    campo.addEventListener('change', function () { var v = lido(); if (v != null) aplica(v); });
    campo.addEventListener('keydown', function (e) {
      var v = lido();
      if (e.key === 'ArrowUp') { e.preventDefault(); aplica((v || 16) + 1); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); aplica((v || 16) - 1); }
      else if (e.key === 'Enter') { e.preventDefault(); if (v != null) aplica(v); area.focus(); }
    });
    [menos, mais].forEach(function (b) {
      b.addEventListener('mousedown', function (e) { e.preventDefault(); });
      b.addEventListener('click', function () {
        var v = lido() || parseInt(pxAtual(), 10) || 16;
        aplica(v + (b === mais ? 2 : -2));
      });
    });

    function aoMudarSelecao() {
      if (!barra.isConnected) { document.removeEventListener('selectionchange', aoMudarSelecao); return; }
      var s = window.getSelection();
      if (s.rangeCount && area.contains(s.anchorNode)) {
        salva = s.getRangeAt(0).cloneRange();
        if (document.activeElement !== campo) campo.value = pxAtual();
      }
    }
    document.addEventListener('selectionchange', aoMudarSelecao);
  }

  function varre(no) { (no || document).querySelectorAll('.re-barra').forEach(melhora); }
  function inicia() {
    varre();
    new MutationObserver(function (muts) {
      muts.forEach(function (m) {
        m.addedNodes.forEach(function (n) {
          if (n.nodeType !== 1) return;
          if (n.classList && n.classList.contains('re-barra')) melhora(n); else varre(n);
        });
      });
    }).observe(document.body, {childList: true, subtree: true});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inicia); else inicia();
})();
