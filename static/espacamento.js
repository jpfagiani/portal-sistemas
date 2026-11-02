/* Espaçamento do texto e da imagem: junta ou afasta, em pixels.

   Melhora qualquer barra de formatação (.re-barra): grupo "Espaço" com
   acima − +, abaixo − +, linhas − +, "Juntar" e "Normal".
   Vale para os parágrafos/títulos/itens selecionados (ou onde está o cursor) e,
   com uma imagem selecionada, para o parágrafo da imagem e o texto logo abaixo dela.
   Juntar = sem espaço entre os blocos e entrelinha apertada; Normal = volta ao padrão. */
(function () {
  'use strict';
  var BLOCOS = 'p,h2,h3,h4,li,blockquote';
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }

  function melhora(barra) {
    if (barra.dataset.reEsp) return;
    var area = barra.parentNode && barra.parentNode.querySelector('.re-area');
    if (!area) return;
    barra.dataset.reEsp = '1';
    var salva = null;
    document.addEventListener('selectionchange', function () {
      var s = window.getSelection();
      if (s.rangeCount && area.contains(s.anchorNode)) salva = s.getRangeAt(0).cloneRange();
    });
    function blocosAlvo() {
      var img = area.querySelector('img[data-sel]'), lista = [];
      if (img) {
        var b = img.closest(BLOCOS) || img.parentNode;
        if (b && b !== area) lista.push(b);
        var p = img.closest('.fig'); if (p) lista = Array.prototype.slice.call(p.querySelectorAll(BLOCOS));
        var seg = (p || b).nextElementSibling; if (seg && seg.matches(BLOCOS)) lista.push(seg);
        return lista;
      }
      if (!salva) return [];
      Array.prototype.forEach.call(area.querySelectorAll(BLOCOS), function (b) {
        if (salva.intersectsNode(b) && !b.querySelector(BLOCOS)) lista.push(b);
      });
      return lista;
    }
    function px(v) { var n = parseFloat(v); return isNaN(n) ? 0 : n; }
    function mexe(prop, delta) {
      var l = blocosAlvo(); if (!l.length) return;
      l.forEach(function (b) {
        var cs = getComputedStyle(b), atual;
        if (prop === 'line-height') {
          atual = cs.lineHeight === 'normal' ? px(cs.fontSize) * 1.4 : px(cs.lineHeight);
          b.style.lineHeight = Math.max(10, Math.min(80, Math.round(atual + delta))) + 'px';
        } else {
          atual = px(cs[prop === 'margin-top' ? 'marginTop' : 'marginBottom']);
          b.style.setProperty(prop, Math.max(-24, Math.min(80, Math.round(atual + delta))) + 'px');
        }
      });
      avisa();
    }
    function juntar() {
      var l = blocosAlvo(); if (!l.length) return;
      l.forEach(function (b) {
        b.style.marginTop = '0px'; b.style.marginBottom = '0px';
        b.style.lineHeight = Math.round(px(getComputedStyle(b).fontSize) * 1.2) + 'px';
      });
      avisa();
    }
    function normal() {
      blocosAlvo().forEach(function (b) {
        b.style.removeProperty('margin-top'); b.style.removeProperty('margin-bottom'); b.style.removeProperty('line-height');
        if (!b.getAttribute('style')) b.removeAttribute('style');
      });
      avisa();
    }
    function avisa() { area.dispatchEvent(new Event('input', {bubbles: true})); }

    var g = el('span', 're-esp-grupo');
    g.appendChild(el('span', 're-rot', 'Espaço:'));
    function par(rot, prop, passo, dica) {
      g.appendChild(el('span', 're-rot', rot));
      [['−', -passo], ['+', passo]].forEach(function (t) {
        var b = el('button', '', t[0]); b.type = 'button'; b.title = dica + (t[1] < 0 ? ' (diminui)' : ' (aumenta)');
        b.addEventListener('mousedown', function (e) { e.preventDefault(); });
        b.addEventListener('click', function () { mexe(prop, t[1]); });
        g.appendChild(b);
      });
    }
    par('acima', 'margin-top', 4, 'Espaço acima do parágrafo (ou da imagem)');
    par('abaixo', 'margin-bottom', 4, 'Espaço abaixo do parágrafo (ou da imagem)');
    par('linhas', 'line-height', 2, 'Distância entre as linhas do texto');
    var j = el('button', '', 'Juntar'); j.type = 'button'; j.title = 'Tira o espaço entre imagem e texto e aperta as linhas';
    var n = el('button', '', 'Normal'); n.type = 'button'; n.title = 'Volta ao espaçamento padrão';
    [j, n].forEach(function (b) { b.addEventListener('mousedown', function (e) { e.preventDefault(); }); });
    j.addEventListener('click', juntar); n.addEventListener('click', normal);
    g.appendChild(j); g.appendChild(n);
    var sep = el('span', 're-sep');
    var ref = barra.querySelector('.re-px-grupo') || barra.querySelector('button[data-cmd=removeFormat]');
    barra.insertBefore(sep, ref); barra.insertBefore(g, ref);
  }

  function inicia() { document.querySelectorAll('.re-barra').forEach(melhora); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(inicia, 0); }); else setTimeout(inicia, 0);
})();
