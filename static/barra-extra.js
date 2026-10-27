/* Barra de formatação, versão "Word": tamanho do texto em pixels (campo, − e +),
   paleta de cores para o texto e para o destaque (marca-texto) e cores recentes.
   Melhora qualquer .re-barra da página — a dos cartões, notícias, módulos e a
   da janela de edição direta — sem mexer nos editores: os controles antigos de
   cor e tamanho ficam escondidos e estes passam a fazer o trabalho. */
(function () {
  'use strict';
  var SENTINELA = '#010203', MIN = 8, MAX = 96;

  /* ── paleta: cinzas, cores vivas e tons claros/escuros de cada matiz ── */
  function hsl(h, s, l) {
    s /= 100; l /= 100;
    var a = s * Math.min(l, 1 - l);
    function f(n) { var k = (n + h / 30) % 12, c = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1)); return Math.round(255 * c).toString(16).padStart(2, '0'); }
    return '#' + f(0) + f(8) + f(4);
  }
  var CINZAS = ['#000000', '#1e293b', '#475569', '#64748b', '#94a3b8', '#cbd5e1', '#e2e8f0', '#f1f5f9', '#ffffff'];
  var BASE = ['#c1121f', '#dc2626', '#ea580c', '#d97706', '#ca8a04', '#16a34a', '#0d9488', '#0891b2', '#2563eb', '#4f46e5', '#7c3aed', '#c026d3', '#db2777'];
  var MATIZES = [0, 25, 45, 60, 120, 170, 200, 220, 270, 310];
  var LINHAS = [CINZAS, BASE];
  [[88, 25], [88, 38], [88, 78], [88, 90]].forEach(function (p) {   // tons escuros e claros
    LINHAS.push(MATIZES.map(function (h) { return hsl(h, 70, p[1]); }));
  });

  function recentes() { try { return JSON.parse(localStorage.getItem('re-cores') || '[]'); } catch (e) { return []; } }
  function lembra(c) {
    try { var l = recentes().filter(function (x) { return x !== c; }); l.unshift(c); localStorage.setItem('re-cores', JSON.stringify(l.slice(0, 8))); } catch (e) {}
  }

  var pop = null;
  function fechaPop() { if (pop) { pop.remove(); pop = null; } }
  document.addEventListener('mousedown', function (e) { if (pop && !pop.contains(e.target) && !e.target.closest('.re-cor-btn')) fechaPop(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') fechaPop(); });
  window.addEventListener('resize', fechaPop);

  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }

  function melhora(barra) {
    if (barra.dataset.rePlus) return;
    var raiz = barra.parentNode, area = raiz && raiz.querySelector('.re-area');
    if (!area) return;
    barra.dataset.rePlus = '1';
    var antigos = barra.querySelectorAll('.re-cor, .re-tam, select[title="Tamanho do texto"]');
    var ponto = antigos[0] || null;
    antigos.forEach(function (a) { a.style.display = 'none'; });

    var salva = null;
    function restaura() {
      area.focus();
      if (salva) { var s = window.getSelection(); s.removeAllRanges(); s.addRange(salva); }
    }

    /* ── tamanho em pixels ── */
    var grupo = el('span', 're-px-grupo');
    var menos = el('button', '', '−'), mais = el('button', '', '+');
    menos.type = mais.type = 'button'; menos.title = 'Diminuir a letra'; mais.title = 'Aumentar a letra';
    var campo = el('input', 're-px'); campo.type = 'text'; campo.inputMode = 'numeric'; campo.size = 3; campo.maxLength = 3;
    campo.setAttribute('list', 're-px-lista'); campo.title = 'Tamanho da letra em pixels (selecione o texto antes)'; campo.setAttribute('aria-label', 'Tamanho da letra em pixels');
    campo.placeholder = 'px';
    if (!document.getElementById('re-px-lista')) {
      var dl = el('datalist'); dl.id = 're-px-lista';
      [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 60, 72, 96].forEach(function (n) { var o = el('option'); o.value = n; dl.appendChild(o); });
      document.body.appendChild(dl);
    }
    grupo.appendChild(menos); grupo.appendChild(campo); grupo.appendChild(mais);

    function pxAtual() {
      var n = salva && salva.startContainer;
      if (!n) return '';
      if (n.nodeType === 3) n = n.parentNode;
      return n && n.nodeType === 1 ? String(Math.round(parseFloat(getComputedStyle(n).fontSize))) : '';
    }
    function aplicaPx(px) {
      px = Math.max(MIN, Math.min(MAX, Math.round(px)));
      if (!salva || salva.collapsed) {
        campo.classList.add('re-px-aviso'); campo.title = 'Selecione o trecho de texto que quer mudar';
        setTimeout(function () { campo.classList.remove('re-px-aviso'); campo.title = 'Tamanho da letra em pixels (selecione o texto antes)'; }, 2500);
        return;
      }
      restaura();
      var s = window.getSelection();
      try { document.execCommand('styleWithCSS', false, false); } catch (e) {}
      document.execCommand('fontSize', false, '7');
      var novos = [];
      area.querySelectorAll('font[size="7"]').forEach(function (f) {
        var sp = document.createElement('span'); sp.style.fontSize = px + 'px';
        while (f.firstChild) sp.appendChild(f.firstChild);
        f.parentNode.replaceChild(sp, f); novos.push(sp);
      });
      novos.forEach(function (sp) {                    // tamanhos antigos dentro do trecho deixam de valer
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
    function lerCampo() { var v = parseInt(campo.value, 10); return isNaN(v) ? null : v; }
    campo.addEventListener('change', function () { var v = lerCampo(); if (v != null) aplicaPx(v); });
    campo.addEventListener('keydown', function (e) {
      var v = lerCampo();
      if (e.key === 'ArrowUp') { e.preventDefault(); aplicaPx((v || 16) + 1); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); aplicaPx((v || 16) - 1); }
      else if (e.key === 'Enter') { e.preventDefault(); if (v != null) aplicaPx(v); area.focus(); }
    });
    [menos, mais].forEach(function (b) {
      b.addEventListener('mousedown', function (e) { e.preventDefault(); });
      b.addEventListener('click', function () {
        var v = lerCampo() || parseInt(pxAtual(), 10) || 16;
        aplicaPx(v + (b === mais ? 2 : -2));
      });
    });

    /* ── cores ── */
    function removeMarca(teste) {
      area.querySelectorAll('[style], font').forEach(function (n) {
        if (!teste(n)) return;
        if (n.tagName === 'FONT') { while (n.firstChild) n.parentNode.insertBefore(n.firstChild, n); n.remove(); return; }
        if (n.style.color === 'rgb(1, 2, 3)') n.style.removeProperty('color');
        if (n.style.backgroundColor === 'transparent') n.style.removeProperty('background-color');
        if (!n.getAttribute('style')) {
          n.removeAttribute('style');
          if (n.tagName === 'SPAN') { while (n.firstChild) n.parentNode.insertBefore(n.firstChild, n); n.remove(); }
        }
      });
    }
    function aplicaCor(tipo, cor) {
      restaura();
      try { document.execCommand('styleWithCSS', false, true); } catch (e) {}
      if (tipo === 'texto') {
        document.execCommand('foreColor', false, cor || SENTINELA);
        if (!cor) removeMarca(function (n) { return n.tagName === 'FONT' ? (n.getAttribute('color') || '').toLowerCase() === SENTINELA : n.style.color === 'rgb(1, 2, 3)'; });
      } else {
        if (!document.execCommand('hiliteColor', false, cor || 'transparent')) document.execCommand('backColor', false, cor || 'transparent');
        if (!cor) removeMarca(function (n) { return n.style && n.style.backgroundColor === 'transparent'; });
      }
      try { document.execCommand('styleWithCSS', false, false); } catch (e) {}
      var s = window.getSelection(); if (s.rangeCount) salva = s.getRangeAt(0).cloneRange();
      if (cor) lembra(cor);
    }
    function botaoCor(tipo, rotulo, dica) {
      var b = el('button', 're-cor-btn'); b.type = 'button'; b.title = dica; b.setAttribute('aria-label', dica);
      var a = el('span', tipo === 'texto' ? 're-cor-a' : 're-cor-m', rotulo), barraCor = el('span', 're-cor-barra');
      barraCor.style.background = tipo === 'texto' ? '#1e293b' : '#fde047';
      b.appendChild(a); b.appendChild(barraCor); b.appendChild(el('span', 're-cor-seta', '▾'));
      b.addEventListener('mousedown', function (e) { e.preventDefault(); });
      b.addEventListener('click', function () {
        if (pop && pop.dataset.dono === tipo + barra.dataset.rePlus && pop._barra === barra) { fechaPop(); return; }
        fechaPop();
        pop = el('div', 're-pop'); pop._barra = barra; pop.dataset.dono = tipo + barra.dataset.rePlus;
        pop.addEventListener('mousedown', function (e) { if (e.target.tagName !== 'INPUT') e.preventDefault(); });
        function escolhe(cor) { aplicaCor(tipo, cor); if (cor) barraCor.style.background = cor; fechaPop(); }
        var auto = el('button', 're-pop-auto', tipo === 'texto' ? 'Cor automática (a do tema)' : 'Sem destaque'); auto.type = 'button';
        auto.addEventListener('click', function () { escolhe(null); });
        pop.appendChild(auto);
        var grade = el('div', 're-pop-grade');
        function amostra(cor) {
          var c = el('button', 're-amostra'); c.type = 'button'; c.style.background = cor; c.title = cor; c.setAttribute('aria-label', cor);
          c.addEventListener('click', function () { escolhe(cor); }); return c;
        }
        LINHAS.forEach(function (lin) { var l = el('div', 're-pop-linha'); lin.forEach(function (cor) { l.appendChild(amostra(cor)); }); grade.appendChild(l); });
        pop.appendChild(grade);
        var rec = recentes();
        if (rec.length) { pop.appendChild(el('div', 're-pop-tit', 'Usadas recentemente')); var l = el('div', 're-pop-linha'); rec.forEach(function (cor) { l.appendChild(amostra(cor)); }); pop.appendChild(l); }
        var mais = el('label', 're-pop-mais', 'Mais cores… '); var ci = el('input'); ci.type = 'color'; ci.value = tipo === 'texto' ? '#1e293b' : '#fde047';
        ci.addEventListener('change', function () { escolhe(ci.value); });
        mais.appendChild(ci); pop.appendChild(mais);
        document.body.appendChild(pop);
        var r = b.getBoundingClientRect();
        pop.style.left = Math.max(6, Math.min(r.left, window.innerWidth - pop.offsetWidth - 6)) + 'px';
        var abaixo = r.bottom + 4; if (abaixo + pop.offsetHeight > window.innerHeight - 6) abaixo = Math.max(6, r.top - pop.offsetHeight - 4);
        pop.style.top = abaixo + 'px';
      });
      return b;
    }
    var bTexto = botaoCor('texto', 'A', 'Cor da letra'), bMarca = botaoCor('marca', 'ab', 'Cor de destaque (marca-texto)');
    bMarca.querySelector('.re-cor-m').style.background = '';

    var inicio = el('span', 're-px-bloco');
    inicio.appendChild(grupo); inicio.appendChild(bTexto); inicio.appendChild(bMarca);
    if (ponto) barra.insertBefore(inicio, ponto); else barra.appendChild(inicio);

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
