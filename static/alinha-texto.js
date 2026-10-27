/* Texto na mesma largura da imagem que vem antes dele.

   Numa matéria ou página de conteúdo, depois de uma imagem sozinha na linha
   (Média, Grande, em pixels…), o texto, os títulos e as listas que vêm abaixo
   ficam com a mesma largura e a mesma posição dela, como nos portais de notícia.
   Imagem em largura total não limita nada, e uma nova imagem passa a valer para
   o que vem depois. Colunas e imagens com texto ao lado ficam como estão. */
(function () {
  'use strict';
  var MARCA = 'data-alinhado', MINIMA = 100;   // só imagem minúscula deixa de limitar o texto

  /* Parágrafo que só tem imagens (uma ou várias, lado a lado): devolve a lista delas. */
  function soImagens(no) {
    if (no.tagName === 'IMG') return [no];
    if (!/^(P|DIV|FIGURE|A)$/.test(no.tagName)) return null;
    var imgs = no.querySelectorAll('img');
    if (!imgs.length) return null;
    var resto = no.cloneNode(true);
    resto.querySelectorAll('img,br').forEach(function (x) { x.remove(); });
    return resto.textContent.trim() ? null : [].slice.call(imgs);
  }
  function flutua(img) { return /^(left|right)$/.test(getComputedStyle(img).cssFloat); }
  function limpa(no) {
    no.querySelectorAll('[' + MARCA + ']').forEach(function (x) {
      x.style.removeProperty('max-width'); x.style.removeProperty('margin-left'); x.removeAttribute(MARCA);
      if (!x.getAttribute('style')) x.removeAttribute('style');
    });
  }
  function aplica(f, ctx) {
    // posição da borda da imagem em relação à área de conteúdo do elemento que guarda o bloco
    var pai = f.parentNode, cs = getComputedStyle(pai), pr = pai.getBoundingClientRect();
    var base = pr.left + pai.clientLeft + (parseFloat(cs.paddingLeft) || 0);
    var x = Math.max(0, Math.round(ctx.esq - base));
    // listas já têm o recuo dos marcadores; ele continua dentro da largura da imagem
    var recuo = /^(UL|OL)$/.test(f.tagName) ? (parseFloat(getComputedStyle(f).marginLeft) || 0) : 0;
    f.style.maxWidth = (ctx.w - recuo) + 'px'; f.style.marginLeft = (x + recuo) + 'px'; f.setAttribute(MARCA, '1');
  }
  /* Faixa ocupada por um grupo de imagens. Largura total ou estreita demais não limita o texto. */
  function contexto(imgs, cont) {
    var esq = Infinity, dir = -Infinity, c = cont.getBoundingClientRect();
    for (var i = 0; i < imgs.length; i++) {
      if (flutua(imgs[i])) return undefined;                      // texto ao lado: não mexe
      var r = imgs[i].getBoundingClientRect();
      if (!r.width) return null;
      esq = Math.min(esq, r.left); dir = Math.max(dir, r.right);
    }
    var w = dir - esq;
    var cs = getComputedStyle(cont), util = c.width - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0);
    if (w >= util - 4 || w < MINIMA) return null;
    return {w: Math.round(w), esq: esq};
  }

  /* ── prepara o texto: imagem e texto no mesmo bloco viram blocos separados ──
     Quem insere a imagem no meio de um parágrafo fica com "texto + imagem + texto"
     num bloco só, e não há como alinhar o texto à imagem. Aqui cada imagem (ou
     grupo de imagens lado a lado) vira o seu bloco, e o texto de antes e de depois
     continua em blocos próprios, com a mesma formatação. */
  var BLOCO = /^(P|DIV|H[1-6]|BLOCKQUOTE)$/, INLINE = /^(SPAN|A|STRONG|B|EM|I|U|S|FONT|SMALL|MARK|SUB|SUP|CODE|BR)$/;
  function temTexto(no) {
    var c = no.cloneNode(true);
    c.querySelectorAll('img,br').forEach(function (x) { x.remove(); });
    return !!c.textContent.replace(/ /g, ' ').trim();
  }
  function agrupaInline(pai) {                 // texto solto (sem parágrafo) ganha um parágrafo
    var run = [];
    function fecha() {
      if (!run.length) return;
      var tem = run.some(function (n) { return n.nodeType === 3 ? !!n.textContent.trim() : (n.tagName !== 'BR' && (!!n.textContent.trim() || !!n.querySelector('img'))); });
      if (tem) { var p = document.createElement('p'); run[0].parentNode.insertBefore(p, run[0]); run.forEach(function (n) { p.appendChild(n); }); }
      run = [];
    }
    [].slice.call(pai.childNodes).forEach(function (n) {
      if (n.nodeType === 3 || (n.nodeType === 1 && INLINE.test(n.tagName))) run.push(n); else fecha();
    });
    fecha();
  }
  function vizinho(no, dir) {
    var n = dir < 0 ? no.previousSibling : no.nextSibling;
    while (n && n.nodeType === 3 && !n.textContent.trim()) n = dir < 0 ? n.previousSibling : n.nextSibling;
    return n;
  }
  function isola(cont) {
    agrupaInline(cont);
    cont.querySelectorAll('div:not(.col):not(.cols)').forEach(function (d) {
      if (d.querySelector(':scope > p, :scope > h1, :scope > h2, :scope > h3, :scope > h4, :scope > ul, :scope > ol, :scope > blockquote, :scope > div')) agrupaInline(d);
    });
    [].slice.call(cont.querySelectorAll('img')).forEach(function (img) {
      if (!img.isConnected || flutua(img)) return;
      var prev = vizinho(img, -1);
      if (prev && prev.nodeType === 1 && prev.tagName === 'IMG') return;        // não é a primeira do grupo
      var fim = img, nx;
      while ((nx = vizinho(fim, 1)) && nx.nodeType === 1 && nx.tagName === 'IMG' && !flutua(nx)) fim = nx;
      var bloco = img.parentNode;
      while (bloco && bloco !== cont && !BLOCO.test(bloco.tagName) && bloco.tagName !== 'LI') bloco = bloco.parentNode;
      if (!bloco || bloco === cont || bloco.tagName === 'LI' || !temTexto(bloco)) return;
      var r = document.createRange();
      r.setStart(bloco, 0); r.setEndBefore(img); var antes = r.extractContents();
      r = document.createRange();
      r.setStartAfter(fim); r.setEnd(bloco, bloco.childNodes.length); var depois = r.extractContents();
      [[antes, bloco], [depois, bloco.nextSibling]].forEach(function (par, k) {
        var t = document.createElement('div'); t.appendChild(par[0]);
        if (!temTexto(t) && !t.querySelector('img')) return;
        var n = bloco.cloneNode(false); n.removeAttribute('id');
        while (t.firstChild) n.appendChild(t.firstChild);
        bloco.parentNode.insertBefore(n, par[1]);
      });
    });
  }

  /* Lista plana, na ordem da página, com o que importa: imagens, colunas e blocos de texto.
     Texto colado de outro lugar costuma vir embrulhado num <div>; entra-se nele. */
  function achata(no, cont, saida) {
    [].slice.call(no.children).forEach(function (f) {
      if (f.classList.contains('cols') || f.classList.contains('figura')) { saida.push({f: f, cols: true}); return; }
      var imgs = soImagens(f);
      if (imgs) { saida.push({f: f, ctx: contexto(imgs, cont)}); return; }
      if (/^(DIV|SECTION|ARTICLE|MAIN)$/.test(f.tagName) && f.querySelector('p,h1,h2,h3,h4,h5,h6,ul,ol,blockquote,div,section')) { achata(f, cont, saida); return; }
      saida.push({f: f, texto: !f.querySelector('img')});
    });
  }
  /* ── bloco "imagem + texto": mede a imagem e põe o texto abaixo dela numa caixa da mesma largura ──
     Feito ao salvar no editor e guardado na própria notícia (<div class="figura" style="width:Npx">),
     então a página publicada não depende de cálculo nenhum: imagem e texto têm as mesmas bordas. */
  function desagrupa(cont) {
    [].slice.call(cont.querySelectorAll('.figura')).forEach(function (g) {
      while (g.firstChild) g.parentNode.insertBefore(g.firstChild, g);
      g.remove();
    });
  }
  function agrupa(cont) {
    desagrupa(cont); limpa(cont); isola(cont);
    var cs = getComputedStyle(cont), c = cont.getBoundingClientRect();
    var baseEsq = c.left + cont.clientLeft + (parseFloat(cs.paddingLeft) || 0);
    var util = cont.clientWidth - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0);
    var itens = [];
    [].slice.call(cont.children).forEach(function (f) {
      if (f.classList.contains('cols')) { itens.push({f: f, quebra: true}); return; }
      var imgs = soImagens(f);
      if (imgs) { itens.push({f: f, imgs: imgs, ctx: contexto(imgs, cont)}); return; }
      itens.push({f: f, texto: !f.querySelector('img') && !/^(HR|TABLE)$/.test(f.tagName), quebra: !!f.querySelector('img')});
    });
    var grupos = [], primeira = true;
    for (var i = 0; i < itens.length; i++) {
      if (!itens[i].imgs) continue;
      var ini = i, fim = i;
      if (primeira) while (ini > 0 && itens[ini - 1].texto) ini--;      // texto em cima da 1ª imagem também entra
      while (fim + 1 < itens.length && itens[fim + 1].texto) fim++;
      primeira = false;
      if (itens[i].ctx) grupos.push({ini: ini, img: i, fim: fim, ctx: itens[i].ctx});
      i = fim;
    }
    grupos.forEach(function (g) {
      var w = g.ctx.w, off = g.ctx.esq - baseEsq, sobra = util - w;
      var classe = off < 4 ? 'fig-e' : (sobra - off < 4 ? 'fig-d' : 'fig-c');
      var caixa = document.createElement('div');
      caixa.className = 'figura ' + classe; caixa.style.width = w + 'px';
      itens[g.ini].f.parentNode.insertBefore(caixa, itens[g.ini].f);
      for (var k = g.ini; k <= g.fim; k++) caixa.appendChild(itens[k].f);
      itens[g.img].imgs.forEach(function (img) {                      // a imagem passa a ter a largura exata da caixa
        ['im-p', 'im-m', 'im-g', 'im-c'].forEach(function (x) { img.classList.remove(x); });
        img.removeAttribute('data-w'); img.style.width = Math.round(img.getBoundingClientRect().width || w) + 'px';
      });
    });
  }

  function alinhaCorpo(cont, opcoes) {
    limpa(cont);
    if (!opcoes || opcoes.isola !== false) isola(cont);
    if (window.innerWidth <= 560) return;
    var itens = []; achata(cont, cont, itens);
    // texto em cima da primeira imagem também acompanha a largura dela
    var ctx = null;
    for (var i = 0; i < itens.length; i++) { if (itens[i].cols) break; if (itens[i].ctx !== undefined && !itens[i].texto) { ctx = itens[i].ctx; break; } }
    itens.forEach(function (it) {
      if (it.cols) { ctx = null; return; }
      if (it.ctx !== undefined && !it.texto) { ctx = it.ctx; return; }
      if (ctx && it.texto) aplica(it.f, ctx);
    });
  }
  function alinhaBlocos(cont) {
    limpa(cont);
    if (window.innerWidth <= 560) return;
    var itens = [].slice.call(cont.children).filter(function (f) { return f.classList.contains('pagina-imagens') || f.classList.contains('bl'); })
      .map(function (f) {
        if (f.classList.contains('bl')) return {f: f, texto: true};
        var figs = [].slice.call(f.querySelectorAll('.pi img'));
        return {f: f, ctx: figs.length ? contexto(figs, cont) : null};
      });
    var ctx = null;
    for (var i = 0; i < itens.length; i++) { if (!itens[i].texto) { ctx = itens[i].ctx || null; break; } }
    itens.forEach(function (it) {
      if (!it.texto) { ctx = it.ctx || null; return; }
      if (ctx) aplica(it.f, ctx);
    });
  }
  window.AlinhaTexto = {corpo: alinhaCorpo, blocos: alinhaBlocos, limpa: limpa, isola: isola, agrupa: agrupa, desagrupa: desagrupa};

  function prepara(cont, fn) {
    var pendente = false;
    function agenda() { if (pendente) return; pendente = true; requestAnimationFrame(function () { pendente = false; fn(cont); }); }
    cont.querySelectorAll('img').forEach(function (i) { if (!i.complete) i.addEventListener('load', agenda); });
    if (window.ResizeObserver) new ResizeObserver(agenda).observe(cont); else window.addEventListener('resize', agenda);
    fn(cont);
  }
  function inicia() {
    document.querySelectorAll('.noticia-corpo').forEach(function (c) { prepara(c, alinhaCorpo); });
    var pg = document.querySelector('main.pagina-conteudo:not(.pagina-materia)');
    if (pg) prepara(pg, alinhaBlocos);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inicia); else inicia();
})();
