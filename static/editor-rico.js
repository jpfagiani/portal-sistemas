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
    var POS = [['im-esq', 'À esquerda, texto ao lado'], ['im-dir', 'À direita, texto ao lado'],
               ['im-bloco', 'Sozinha à esquerda'], ['im-centro', 'Sozinha no centro'], ['im-bloco-dir', 'Sozinha à direita']];
    var barra = document.createElement('div'); barra.className = 're-img-barra'; barra.hidden = true;
    var atual = null;
    function botao(txt, fn, cls) {
      var b = document.createElement('button'); b.type = 'button'; b.textContent = txt; if (cls) b.className = cls;
      b.addEventListener('mousedown', function (e) { e.preventDefault(); });
      b.addEventListener('click', fn); barra.appendChild(b); return b;
    }
    function troca(grupo, cls) {
      if (!atual) return;
      grupo.forEach(function (g) { atual.classList.remove(g[0]); });
      if (cls) atual.classList.add(cls);
      if (grupo === TAM) { atual.style.removeProperty('width'); atual.removeAttribute('data-w'); if (!atual.getAttribute('style')) atual.removeAttribute('style'); }
      marca(); posicionaAlca();
    }
    function marca() {
      barra.querySelectorAll('button[data-c]').forEach(function (b) {
        b.classList.toggle('on', !!atual && atual.classList.contains(b.dataset.c));
      });
    }
    function rotulo(t) { var r = document.createElement('span'); r.className = 're-rot'; r.textContent = t; barra.appendChild(r); }
    rotulo('Imagem — tamanho:');
    TAM.forEach(function (t) { botao(t[1], function () { troca(TAM, atual && atual.classList.contains(t[0]) ? '' : t[0]); }).dataset.c = t[0]; });
    barra.appendChild(document.createElement('span')).className = 're-sep';
    rotulo('posição (texto ao lado, ou em cima e embaixo):');
    POS.forEach(function (t) { botao(t[1], function () { troca(POS, atual && atual.classList.contains(t[0]) ? '' : t[0]); }).dataset.c = t[0]; });
    barra.appendChild(document.createElement('span')).className = 're-sep';
    barra.appendChild(document.createElement('span')).className = 're-sep';
    botao('↑ Subir', function () { mover(-1); });
    botao('↓ Descer', function () { mover(1); });
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
      var bloco = atual; while (bloco.parentNode !== area) bloco = bloco.parentNode;
      var so = bloco === atual || (bloco.children.length === 1 && !bloco.textContent.trim());
      var vizinho = d < 0 ? bloco.previousElementSibling : bloco.nextElementSibling;
      if (so) {
        if (!vizinho) return;
        if (d < 0) area.insertBefore(bloco, vizinho); else area.insertBefore(bloco, vizinho.nextSibling);
      } else {
        var p = document.createElement('p'); p.appendChild(atual);
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
        var pct = Math.max(10, Math.min(100, Math.round((w0 + ev.clientX - x0) / larg * 100)));
        ['im-p', 'im-m', 'im-g', 'im-c'].forEach(function (c) { atual.classList.remove(c); });
        atual.style.width = pct + '%'; atual.setAttribute('data-w', pct);
        dica.textContent = pct + '%'; posicionaAlca(); marca();
      }
      function fim() { alca.removeEventListener('pointermove', move); alca.removeEventListener('pointerup', fim); alca.removeEventListener('pointercancel', fim); dica.textContent = ''; }
      alca.addEventListener('pointermove', move); alca.addEventListener('pointerup', fim); alca.addEventListener('pointercancel', fim);
    });
    function seleciona(img) {
      if (atual && atual !== img) atual.removeAttribute('data-sel');
      atual = img; atual.setAttribute('data-sel', '1'); barra.hidden = false; marca(); posicionaAlca();
    }
    // Imagem nova entra em tamanho médio e já selecionada, com a barra à vista.
    window.__reSelecionaNova = null;
    function depoisDeInserir(url) {
      var todas = area.querySelectorAll('img[src="' + url + '"]');
      if (todas.length) seleciona(todas[todas.length - 1]);
    }
    area.addEventListener('click', function (e) {
      if (e.target.tagName === 'IMG') seleciona(e.target); else desmarca();
    });
    document.addEventListener('mousedown', function (e) { if (atual && !raiz.contains(e.target)) desmarca(); });

    if (form) form.addEventListener('submit', function (e) {
      if (atual) atual.removeAttribute('data-sel');
      oculto.value = area.innerHTML;
    });
  });
})();
