/* Editor de texto formatado (contêineres com [data-rico]).

   Barra de formatação, link para páginas do portal, imagem da biblioteca. O
   conteúdo vai para o campo oculto ao enviar o formulário; o servidor limpa o
   HTML antes de guardar (nunca confie só no navegador). */
(function () {
  'use strict';
  document.querySelectorAll('[data-rico]').forEach(function (raiz) {
    var area = raiz.querySelector('.re-area');
    var oculto = raiz.querySelector('input[type=hidden]');
    var form = raiz.closest('form');
    try { document.execCommand('defaultParagraphSeparator', false, 'p'); document.execCommand('styleWithCSS', false, false); } catch (e) {}

    var salva = null;
    document.addEventListener('selectionchange', function () {
      var s = window.getSelection();
      if (s.rangeCount && area.contains(s.anchorNode)) salva = s.getRangeAt(0).cloneRange();
    });
    function comando(c, v) {
      area.focus();
      if (salva) { var s = window.getSelection(); s.removeAllRanges(); s.addRange(salva); }
      document.execCommand(c, false, v || null);
    }
    raiz.querySelectorAll('[data-cmd]').forEach(function (b) {
      b.addEventListener('mousedown', function (e) { e.preventDefault(); });
      b.addEventListener('click', function () {
        var c = b.dataset.cmd, v = b.dataset.val;
        if (c === 'formatBlock') { comando(c, '<' + v + '>'); return; }
        if (c === 'createLink') {
          var u = window.prompt('Endereço do link (https://... ou /pagina):', 'https://');
          if (!u || u === 'https://') return; comando(c, u); return;
        }
        comando(c, v);
      });
    });
    var cor = raiz.querySelector('.re-cor-campo');
    if (cor) cor.addEventListener('input', function () { comando('foreColor', cor.value); });
    var tam = raiz.querySelector('.re-tam');
    if (tam) tam.addEventListener('change', function () { if (tam.value) comando('fontSize', tam.value); tam.value = ''; });
    var pag = raiz.querySelector('.re-pag');
    if (pag) pag.addEventListener('change', function () { if (pag.value) comando('createLink', pag.value); pag.value = ''; });

    var img = raiz.querySelector('[data-img]');
    if (img && window.SeletorMidia) {
      img.addEventListener('mousedown', function (e) { e.preventDefault(); });
      img.addEventListener('click', function () {
        window.SeletorMidia.abrir({
          lista: raiz.dataset.lista, enviar: raiz.dataset.enviar, csrf: raiz.dataset.csrf,
          aoEscolher: function (i) {
            area.focus();
            if (salva) { var s = window.getSelection(); s.removeAllRanges(); s.addRange(salva); }
            var alt = window.prompt('Texto alternativo da imagem (descreve a imagem para quem não a enxerga):', i.alt || '') || '';
            var h = '<img class="im-m" src="' + i.url + '" alt="' + alt.replace(/"/g, '&quot;') + '">';
            document.execCommand('insertHTML', false, h);
            depoisDeInserir(i.url);
          }
        });
      });
    }

    /* ── arrastar ou colar uma imagem do computador direto no texto ── */
    var aviso = document.createElement('p'); aviso.className = 're-aviso'; aviso.hidden = true;
    area.parentNode.insertBefore(aviso, area.nextSibling);
    function envia(arquivo, ponto) {
      if (!/^image\//.test(arquivo.type)) { aviso.textContent = 'Só imagens (PNG, JPG, WEBP ou GIF) podem ser colocadas no texto.'; aviso.hidden = false; return; }
      aviso.textContent = 'Enviando ' + (arquivo.name || 'imagem') + '…'; aviso.hidden = false;
      var fd = new FormData(); fd.set('csrf', raiz.dataset.csrf); fd.set('arquivo', arquivo, arquivo.name || 'imagem.png');
      fetch(raiz.dataset.enviar, {method: 'POST', body: fd, credentials: 'same-origin'})
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d.ok) { aviso.textContent = d.erro || 'Não foi possível enviar a imagem.'; return; }
          area.focus();
          var s = window.getSelection();
          if (ponto && document.caretRangeFromPoint) {
            var r = document.caretRangeFromPoint(ponto.x, ponto.y);
            if (r && area.contains(r.startContainer)) { s.removeAllRanges(); s.addRange(r); }
          } else if (salva) { s.removeAllRanges(); s.addRange(salva); }
          var alt = (d.item.nome || '').replace(/\.[^.]+$/, '').replace(/[<>"&]/g, '');
          document.execCommand('insertHTML', false, '<img class="im-m" src="' + d.item.url + '" alt="' + alt + '">');
          aviso.hidden = true;
          depoisDeInserir(d.item.url);
        })
        .catch(function () { aviso.textContent = 'Sem conexão com o servidor.'; });
    }
    function imagens(lista) { return Array.prototype.filter.call(lista || [], function (f) { return f && /^image\//.test(f.type); }); }
    area.addEventListener('dragover', function (e) {
      if (e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types || [], 'Files') >= 0) { e.preventDefault(); area.classList.add('re-sobre'); }
    });
    area.addEventListener('dragleave', function () { area.classList.remove('re-sobre'); });
    area.addEventListener('drop', function (e) {
      area.classList.remove('re-sobre');
      var fs = e.dataTransfer && e.dataTransfer.files;
      if (!fs || !fs.length) return;
      e.preventDefault();
      Array.prototype.forEach.call(fs, function (f) { envia(f, {x: e.clientX, y: e.clientY}); });
    });
    area.addEventListener('paste', function (e) {
      var fs = imagens((e.clipboardData || {}).files);
      if (!fs.length) return;
      e.preventDefault();
      fs.forEach(function (f) { envia(f, null); });
    });

    /* ── imagem no texto: clique para mudar tamanho, posição, descrição ── */
    var TAM = [['im-p', 'Pequena'], ['im-m', 'Média'], ['im-g', 'Grande'], ['im-c', 'Largura total']];
    var LADO = [['im-esq', 'Esquerda'], ['im-dir', 'Direita']];          /* texto ao lado (a imagem flutua) */
    var EMBAIXO = [['esq', 'Esquerda'], ['centro', 'Centro'], ['dir', 'Direita']];   /* texto sempre abaixo */
    var ALINHA = {esq: 'left', centro: 'center', dir: 'right'};
    var FLUTUA = ['im-esq', 'im-dir', 'im-bloco', 'im-bloco-dir', 'im-centro'];
    var barra = document.createElement('div'); barra.className = 're-img-barra'; barra.hidden = true;
    var atual = null;
    function botao(txt, fn, cls) {
      var b = document.createElement('button'); b.type = 'button'; b.textContent = txt; if (cls) b.className = cls;
      b.addEventListener('mousedown', function (e) { e.preventDefault(); });
      b.addEventListener('click', fn); barra.appendChild(b); return b;
    }
    function semTamanhoPorClasse() {
      TAM.forEach(function (g) { atual.classList.remove(g[0]); });
      atual.removeAttribute('data-w');
    }
    function limpaStyle() { if (!atual.getAttribute('style')) atual.removeAttribute('style'); }
    /* Bloco "figura": imagem + texto logo abaixo, os dois com a mesma largura (como nos portais de notícia).
       A largura fica na caixa (.fig); a imagem sempre ocupa 100% dela, então o texto acompanha qualquer tamanho. */
    function figDe(img) { var f = img && img.closest ? img.closest('.fig') : null; return f && area.contains(f) ? f : null; }
    /* Largura em pixels (valor exato, sem Pequena/Média/Grande). */
    function larguraPx(px) {
      if (!atual) return;
      var area_px = Math.round(area.clientWidth - (parseFloat(getComputedStyle(area).paddingLeft) || 0) - (parseFloat(getComputedStyle(area).paddingRight) || 0));
      px = Math.max(20, Math.min(2000, Math.round(px)));
      var fig = figDe(atual);
      semTamanhoPorClasse();
      if (fig) { fig.style.width = px + 'px'; atual.style.removeProperty('width'); atual.removeAttribute('data-px'); limpaStyle(); }
      else { atual.style.width = px + 'px'; atual.setAttribute('data-px', px); }
      campoPx.value = px; campoPx.title = 'Largura em pixels (a área do texto tem ' + area_px + ' px; passando disso a imagem se ajusta)';
      marca(); posicionaAlca();
    }
    function troca(grupo, cls) {
      if (!atual) return;
      var fig = figDe(atual);
      if (fig && grupo === FLUTUA) soltaFig(atual);
      grupo.forEach(function (g) { atual.classList.remove(g[0]); });
      if (cls) atual.classList.add(cls);
      if (grupo === TAM) {
        if (fig) fig.style.removeProperty('width');
        atual.style.removeProperty('width'); atual.removeAttribute('data-w'); atual.removeAttribute('data-px'); limpaStyle();
      }
      marca(); posicionaAlca();
    }
    /* Desfaz a figura (imagem volta a ser um parágrafo comum, com a largura em px). */
    function soltaFig(img) {
      var fig = figDe(img); if (!fig) return;
      var w = Math.round(img.getBoundingClientRect().width);
      while (fig.firstChild) fig.parentNode.insertBefore(fig.firstChild, fig);
      fig.remove();
      img.style.width = w + 'px'; img.setAttribute('data-px', w);
    }
    /* O bloco do texto (filho direto da área) onde a imagem está. */
    function blocoDe(unidade) { var b = unidade; while (b.parentNode && b.parentNode !== area) b = b.parentNode; return b; }
    /* Texto embaixo: a imagem ganha um parágrafo só dela, com o alinhamento escolhido; o que estava
       antes e depois dela no mesmo parágrafo vira parágrafos próprios, e o texto fica logo abaixo. */
    function textoEmbaixo(img, alinh) {
      var CL = {esq: 'fig-e', centro: 'fig-c', dir: 'fig-d'};
      var fig = figDe(img);
      if (!fig) {
        var w = Math.round(img.getBoundingClientRect().width);
        var unidade = img.parentNode && img.parentNode.tagName === 'A' ? img.parentNode : img;
        var bloco = blocoDe(unidade);
        if (!bloco || bloco.parentNode !== area || /^(UL|OL)$/.test(bloco.tagName)) return;
        FLUTUA.forEach(function (c) { img.classList.remove(c); });
        var alvo = document.createElement('p');
        if (bloco === unidade) {
          area.insertBefore(alvo, bloco); alvo.appendChild(unidade);
        } else {
          var rA = document.createRange(); rA.setStart(bloco, 0); rA.setEndBefore(unidade);
          var rD = document.createRange(); rD.setStartAfter(unidade); rD.setEnd(bloco, bloco.childNodes.length);
          var antes = rA.extractContents(), depois = rD.extractContents();
          var resto = function (frag, antesDe) {
            var t = document.createElement('div'); t.appendChild(frag);
            if (!t.textContent.replace(/ /g, ' ').trim() && !t.querySelector('img')) return;
            var n = bloco.cloneNode(false);
            while (t.firstChild) n.appendChild(t.firstChild);
            area.insertBefore(n, antesDe);
          };
          resto(antes, bloco);
          area.insertBefore(alvo, bloco); alvo.appendChild(unidade);
          resto(depois, bloco);
          area.removeChild(bloco);
        }
        alvo.style.removeProperty('text-align'); if (!alvo.getAttribute('style')) alvo.removeAttribute('style');
        fig = document.createElement('div'); fig.className = 'fig';
        area.insertBefore(fig, alvo); fig.appendChild(alvo);
        /* o texto que vem depois (até a próxima imagem) entra na figura */
        var nx = fig.nextElementSibling;
        while (nx && /^(P|H2|H3|H4|UL|OL|BLOCKQUOTE)$/.test(nx.tagName) && !nx.querySelector('img') && !nx.classList.contains('fig')) {
          var prox = nx.nextElementSibling; fig.appendChild(nx); nx = prox;
        }
        if (!alvo.nextElementSibling) { var p = document.createElement('p'); p.innerHTML = '<br>'; fig.appendChild(p); }
        semTamanhoPorClasse(); img.style.removeProperty('width'); img.removeAttribute('data-px');
        if (!img.getAttribute('style')) img.removeAttribute('style');
        fig.style.width = Math.max(20, w) + 'px';
      }
      fig.classList.remove('fig-e', 'fig-c', 'fig-d'); fig.classList.add(CL[alinh]);
      atual = img; marca(); posicionaAlca();
    }
    function estado(cls) {
      if (!atual) return false;
      if (atual.classList.contains(cls)) return true;
      if (cls.indexOf('emb-') === 0) {
        var f = figDe(atual);
        return !!f && f.classList.contains({esq: 'fig-e', centro: 'fig-c', dir: 'fig-d'}[cls.slice(4)]);
      }
      return false;
    }
    /* Link do bloco: imagem e texto da figura levam ao mesmo lugar (outra página do portal ou site). */
    function desfazLinks(fig) {
      fig.querySelectorAll('a').forEach(function (a) { while (a.firstChild) a.parentNode.insertBefore(a.firstChild, a); a.remove(); });
    }
    function envolve(no, url) {
      var a = document.createElement('a'); a.setAttribute('href', url);
      while (no.firstChild) a.appendChild(no.firstChild);
      no.appendChild(a);
    }
    function linkDoBloco(url) {
      if (!atual) return;
      if (!figDe(atual)) textoEmbaixo(atual, 'centro');
      var fig = figDe(atual); if (!fig) return;
      desfazLinks(fig);
      url = (url || '').trim();
      if (url && url !== 'https://') {
        fig.querySelectorAll(':scope > p, :scope > h2, :scope > h3, :scope > h4, :scope > blockquote, :scope > ul > li, :scope > ol > li').forEach(function (b) {
          if (b.textContent.replace(/ /g, ' ').trim() || b.querySelector('img')) envolve(b, url);
        });
      }
      atualizaLink(); posicionaAlca();
    }
    function marca() {
      barra.querySelectorAll('button[data-c]').forEach(function (b) { b.classList.toggle('on', estado(b.dataset.c)); });
      if (atual && document.activeElement !== campoPx) campoPx.value = Math.round(atual.getBoundingClientRect().width) || '';
    }
    function rotulo(t) { var r = document.createElement('span'); r.className = 're-rot'; r.textContent = t; barra.appendChild(r); }
    rotulo('Imagem — largura:');
    var campoPx = document.createElement('input'); campoPx.type = 'text'; campoPx.inputMode = 'numeric'; campoPx.size = 4; campoPx.maxLength = 4;
    campoPx.className = 're-px'; campoPx.placeholder = 'px'; campoPx.setAttribute('aria-label', 'Largura da imagem em pixels');
    campoPx.title = 'Largura da imagem em pixels';
    campoPx.addEventListener('change', function () { var v = parseInt(campoPx.value, 10); if (!isNaN(v)) larguraPx(v); });
    campoPx.addEventListener('keydown', function (e) {
      var v = parseInt(campoPx.value, 10) || 0;
      if (e.key === 'Enter') { e.preventDefault(); if (v) larguraPx(v); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); larguraPx((v || 200) + 10); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); larguraPx((v || 200) - 10); }
    });
    barra.appendChild(campoPx); rotulo('px');
    botao('Largura total', function () { troca(TAM, atual && atual.classList.contains('im-c') ? '' : 'im-c'); }).dataset.c = 'im-c';
    barra.appendChild(document.createElement('span')).className = 're-sep';
    rotulo('Texto embaixo da imagem:');
    EMBAIXO.forEach(function (t) {
      botao(t[1], function () { if (atual) textoEmbaixo(atual, t[0]); }).dataset.c = 'emb-' + t[0];
    });
    barra.appendChild(document.createElement('span')).className = 're-sep';
    rotulo('Texto ao lado:');
    LADO.forEach(function (t) { botao(t[1], function () { troca(FLUTUA, atual && atual.classList.contains(t[0]) ? '' : t[0]); }).dataset.c = t[0]; });
    barra.appendChild(document.createElement('span')).className = 're-sep';
    barra.appendChild(document.createElement('span')).className = 're-sep';
    botao('↑ Subir', function () { mover(-1); });
    botao('↓ Descer', function () { mover(1); });
    /* Link na imagem: ao clicar nela, o visitante vai para o endereço escolhido.
       A imagem fica dentro de um <a>; endereço vazio remove o link. */
    var seletorPag = null;
    var origemPag = raiz.querySelector('.re-pag');
    if (origemPag) {
      seletorPag = origemPag.cloneNode(true); seletorPag.className = 're-pag-img'; seletorPag.value = '';
      seletorPag.title = 'Imagem e texto abaixo dela levam a uma página do portal'; seletorPag.setAttribute('aria-label', 'Link do bloco para página');
      seletorPag.options[0].textContent = 'Link do bloco p/ página…';
      seletorPag.addEventListener('change', function () { if (seletorPag.value) linkDoBloco(seletorPag.value); seletorPag.value = ''; });
      barra.appendChild(seletorPag);
    }
    botao('Link…', function () {
      if (!atual) return;
      var fig0 = figDe(atual);
      if (fig0) {
        var a0 = fig0.querySelector('a');
        var u0 = window.prompt('Endereço ao clicar na imagem OU no texto abaixo dela (/pagina do portal ou https://...).\nDeixe vazio para tirar o link:',
                               a0 ? a0.getAttribute('href') : 'https://');
        if (u0 !== null) linkDoBloco(u0);
        return;
      }
      var a = atual.parentNode && atual.parentNode.tagName === 'A' ? atual.parentNode : null;
      var u = window.prompt('Endereço ao clicar na imagem (https://... ou /pagina).\nDeixe vazio para tirar o link:',
                            a ? a.getAttribute('href') : 'https://');
      if (u === null) return;
      u = u.trim();
      if (!u || u === 'https://') {
        if (a) { a.parentNode.insertBefore(atual, a); a.remove(); }
      } else if (a) {
        a.setAttribute('href', u);
      } else {
        a = document.createElement('a'); a.setAttribute('href', u);
        atual.parentNode.insertBefore(a, atual); a.appendChild(atual);
      }
      atualizaLink(); posicionaAlca();
    }).dataset.link = '1';
    function atualizaLink() {
      var b = barra.querySelector('button[data-link]');
      if (b) b.classList.toggle('on', !!atual && !!atual.closest('a'));
    }
    botao('Descrição…', function () {
      if (!atual) return;
      var v = window.prompt('Texto alternativo (descreve a imagem para quem não a enxerga):', atual.getAttribute('alt') || '');
      if (v !== null) atual.setAttribute('alt', v);
    });
    botao('Remover', function () { if (atual) { atual.remove(); desmarca(); } }, 'perigo');
    area.parentNode.insertBefore(barra, area);
    function desmarca() {
      if (atual) atual.removeAttribute('data-sel');
      atual = null; barra.hidden = true; alca.hidden = true;
    }
    /* Sobe ou desce a imagem um bloco do texto. */
    function mover(d) {
      if (!atual) return;
      var unidade = atual.parentNode.tagName === 'A' ? atual.parentNode : atual;
      if (figDe(atual)) unidade = figDe(atual);              /* a figura inteira sobe e desce */
      var bloco = unidade; while (bloco.parentNode !== area) bloco = bloco.parentNode;
      var so = bloco === unidade || (bloco.children.length === 1 && !bloco.textContent.trim());
      var vizinho = d < 0 ? bloco.previousElementSibling : bloco.nextElementSibling;
      if (so) {
        if (!vizinho) return;
        if (d < 0) area.insertBefore(bloco, vizinho); else area.insertBefore(bloco, vizinho.nextSibling);
      } else {
        var p = document.createElement('p'); p.appendChild(unidade);
        if (d < 0) area.insertBefore(p, bloco); else area.insertBefore(p, bloco.nextSibling);
      }
      posicionaAlca(); atual.scrollIntoView({block: 'nearest'});
    }
    /* Alça no canto da imagem: arraste para esticar ou encolher (proporção mantida). */
    var alca = document.createElement('div'); alca.className = 're-alca'; alca.hidden = true; alca.title = 'Arraste para mudar o tamanho';
    var dica = document.createElement('span'); dica.className = 're-alca-dica'; alca.appendChild(dica);
    raiz.style.position = 'relative'; raiz.appendChild(alca);
    function posicionaAlca() {
      if (!atual || !atual.isConnected) { alca.hidden = true; return; }
      var a = atual.getBoundingClientRect(), r = raiz.getBoundingClientRect(), c = area.getBoundingClientRect();
      var visivel = a.bottom > c.top + 4 && a.bottom < c.bottom + 4;
      alca.hidden = !visivel;
      alca.style.left = (a.right - r.left - 9) + 'px'; alca.style.top = (a.bottom - r.top - 9) + 'px';
    }
    area.addEventListener('scroll', posicionaAlca);
    window.addEventListener('resize', posicionaAlca);
    alca.addEventListener('pointerdown', function (e) {
      if (!atual) return;
      e.preventDefault(); alca.setPointerCapture(e.pointerId);
      var x0 = e.clientX, w0 = atual.getBoundingClientRect().width;
      var cs = getComputedStyle(area), larg = area.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      function move(ev) {
        var px = Math.max(20, Math.min(Math.round(larg), Math.round(w0 + ev.clientX - x0)));
        ['im-p', 'im-m', 'im-g', 'im-c'].forEach(function (c) { atual.classList.remove(c); });
        atual.removeAttribute('data-w');
        atual.style.width = px + 'px'; atual.setAttribute('data-px', px);
        dica.textContent = px + ' px'; posicionaAlca(); marca();
      }
      function fim() { alca.removeEventListener('pointermove', move); alca.removeEventListener('pointerup', fim); alca.removeEventListener('pointercancel', fim); dica.textContent = ''; }
      alca.addEventListener('pointermove', move); alca.addEventListener('pointerup', fim); alca.addEventListener('pointercancel', fim);
    });
    function seleciona(img) {
      if (atual && atual !== img) atual.removeAttribute('data-sel');
      atual = img; atual.setAttribute('data-sel', '1'); barra.hidden = false; marca(); atualizaLink(); posicionaAlca();
    }
    // Imagem nova entra em tamanho médio e já selecionada, com a barra à vista.
    window.__reSelecionaNova = null;
    function depoisDeInserir(url) {
      var todas = area.querySelectorAll('img[src="' + url + '"]');
      if (!todas.length) return;
      var nova = todas[todas.length - 1];
      textoEmbaixo(nova, 'centro');     /* imagem nova já fica sozinha, com o texto logo abaixo */
      seleciona(nova);
    }
    area.addEventListener('click', function (e) {
      if (e.target.tagName === 'IMG') { e.preventDefault(); seleciona(e.target); } else desmarca();
    });
    document.addEventListener('mousedown', function (e) { if (atual && !raiz.contains(e.target)) desmarca(); });

    if (form) form.addEventListener('submit', function (e) {
      if (atual) atual.removeAttribute('data-sel');
      oculto.value = area.innerHTML;
    });
  });
})();
