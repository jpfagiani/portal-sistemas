/*  Tamanho e posição da imagem de um item, arrastando com o mouse.

    Só é carregado para o administrador (shell.html). Cada imagem acima do texto
    tem dois puxadores (borda direita e canto):
      - arrastar um PUXADOR muda o tamanho (a proporção é mantida);
      - arrastar a IMAGEM INTEIRA muda a posição na horizontal, para encostá-la
        à esquerda, à direita ou deixá-la centralizada (ela "gruda" no centro).
    Ao soltar, o valor é gravado: tamanho em % da área do texto, posição de 0
    (esquerda) a 100 (direita), 50 = centro. Em % para continuar proporcional em
    telas de largura diferente.

    Duplo clique num puxador volta ao tamanho padrão (e à esquerda).  */
(function () {
  'use strict';

  var MIN = 10;     /* % — menor que isto some a imagem */
  var MAX = 100;    /* % — a imagem não passa da largura do texto */
  var GRUDA = 4;    /* % — perto do centro, a imagem encaixa no centro */

  function grava(el, dados) {
    var corpo = new URLSearchParams();
    corpo.set('csrf', el.dataset.csrf);
    Object.keys(dados).forEach(function (k) { corpo.set(k, String(dados[k])); });
    return fetch(el.dataset.url, {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: corpo.toString()
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
    });
  }

  function falhou() {
    window.alert('Não foi possível salvar. Recarregue a página e tente de novo.');
  }

  /*  Etiqueta com a medida, enquanto arrasta.  */
  var etiqueta = document.createElement('div');
  etiqueta.className = 'com-img-etiqueta';

  /*  A URL e o token vêm dos puxadores da própria caixa.  */
  function alvoDe(caixa) { return caixa.querySelector('.com-img-alca'); }

  /*  Margem esquerda (em %) para uma posição x (0 a 100) numa largura de pct.  */
  function margem(pct, x) { return (100 - pct) * x / 100; }

  /* ───────── tamanho: arrastar um puxador ───────── */
  document.addEventListener('pointerdown', function (e) {
    var alca = e.target.closest && e.target.closest('.com-img-alca');
    if (!alca || e.button > 0) return;
    var caixa = alca.closest('.com-img-caixa');
    if (!caixa) return;
    e.preventDefault();

    var pai = caixa.parentElement.getBoundingClientRect().width;
    var inicial = caixa.getBoundingClientRect().width;
    var antesLarg = caixa.style.width, antesMargem = caixa.style.marginLeft;
    var antesX = caixa.dataset.x, jaLivre = caixa.classList.contains('livre');
    var margem0 = parseFloat(caixa.style.marginLeft) || 0;   /* % — borda esquerda fica onde está */
    var x0 = e.clientX;
    var pct = inicial / pai * 100;
    var moveu = false, marg = margem0;
    caixa.classList.add('livre', 'ajustando');
    caixa.appendChild(etiqueta);
    alca.setPointerCapture(e.pointerId);

    function move(ev) {
      if (Math.abs(ev.clientX - x0) < 3 && !moveu) return;   /* clique, não arrasto */
      moveu = true;
      pct = Math.max(MIN, Math.min(MAX, (inicial + ev.clientX - x0) / pai * 100));
      if (pct > 97) pct = 100;          /* perto da borda, encaixa na largura toda */
      marg = Math.min(margem0, 100 - pct);   /* a borda esquerda fica; só não passa do cartão */
      caixa.style.width = pct.toFixed(1) + '%';
      caixa.style.marginLeft = marg ? marg.toFixed(1) + '%' : '';
      etiqueta.textContent = Math.round(pct) + '%';
    }

    function solta() {
      alca.removeEventListener('pointermove', move);
      alca.removeEventListener('pointerup', solta);
      alca.removeEventListener('pointercancel', solta);
      caixa.classList.remove('ajustando');
      if (etiqueta.parentNode) etiqueta.parentNode.removeChild(etiqueta);
      if (!moveu) return;                /* só clicou: nada a gravar */
      var larg = Math.round(pct);
      var folga = 100 - pct;
      var x = folga > 0.5 ? Math.max(0, Math.min(100, Math.round(marg / folga * 100))) : 0;
      caixa.dataset.x = x;
      grava(alca, {larg: larg, x: x}).catch(function () {
        /*  Não gravou: volta ao que estava, para a tela não mostrar um tamanho
            que não ficou guardado.  */
        caixa.style.width = antesLarg; caixa.style.marginLeft = antesMargem;
        caixa.dataset.x = antesX;
        if (!jaLivre) caixa.classList.remove('livre');
        falhou();
      });
    }

    alca.addEventListener('pointermove', move);
    alca.addEventListener('pointerup', solta);
    alca.addEventListener('pointercancel', solta);
  });

  /* ───────── posição: arrastar a imagem inteira ───────── */
  var engole = false;      /* depois de arrastar, o clique seguinte não pode abrir o link */

  document.addEventListener('pointerdown', function (e) {
    if (e.button > 0 || e.pointerType !== 'mouse') return;
    if (e.target.closest && e.target.closest('.com-img-alca')) return;
    var caixa = e.target.closest && e.target.closest('.com-img-caixa[data-editavel]');
    if (!caixa) return;
    var pai = caixa.parentElement.getBoundingClientRect().width;
    var largura = caixa.getBoundingClientRect().width;
    if (pai - largura < 3) return;       /* ocupa a largura toda: não há para onde mover */

    var x0 = e.clientX;
    var margemPx0 = caixa.getBoundingClientRect().left - caixa.parentElement.getBoundingClientRect().left;
    var pct = largura / pai * 100;
    var antesMargem = caixa.style.marginLeft, antesX = caixa.dataset.x;
    var x = parseFloat(caixa.dataset.x) || 0;
    var moveu = false;

    function move(ev) {
      if (!moveu && Math.abs(ev.clientX - x0) < 4) return;
      if (!moveu) {
        moveu = true;
        caixa.classList.add('movendo');
        caixa.appendChild(etiqueta);
        try { caixa.setPointerCapture(e.pointerId); } catch (_) {}
      }
      var px = Math.max(0, Math.min(pai - largura, margemPx0 + ev.clientX - x0));
      x = px / (pai - largura) * 100;
      var centro = Math.abs(x - 50) <= GRUDA;
      if (centro) x = 50;
      caixa.style.marginLeft = margem(pct, x).toFixed(2) + '%';
      etiqueta.textContent = centro ? 'Centralizada' : Math.round(x) + '%';
      caixa.classList.toggle('no-centro', centro);
    }

    function solta() {
      document.removeEventListener('pointermove', move);
      document.removeEventListener('pointerup', solta);
      document.removeEventListener('pointercancel', solta);
      caixa.classList.remove('movendo', 'no-centro');
      if (etiqueta.parentNode) etiqueta.parentNode.removeChild(etiqueta);
      if (!moveu) return;                /* foi só um clique: o link abre normalmente */
      engole = true;
      setTimeout(function () { engole = false; }, 0);
      x = Math.round(x);
      caixa.dataset.x = x;
      var alca = alvoDe(caixa);
      if (!alca) return;
      grava(alca, {x: x}).catch(function () {
        caixa.style.marginLeft = antesMargem; caixa.dataset.x = antesX;
        falhou();
      });
    }

    document.addEventListener('pointermove', move);
    document.addEventListener('pointerup', solta);
    document.addEventListener('pointercancel', solta);
  });

  /*  A imagem é arrastável por padrão no navegador (arrastar a figura para fora
      da janela); isso brigaria com o arrasto de posição.  */
  document.addEventListener('dragstart', function (e) {
    if (e.target.closest && e.target.closest('.com-img-caixa[data-editavel], .com-img-alca')) {
      e.preventDefault();
    }
  }, true);

  /*  O puxador pode estar dentro do <a> do cartão (item tipo Link), e a imagem
      pode ser um link: o clique que termina um arrasto não pode abrir nada.  */
  ['click', 'auxclick', 'dblclick'].forEach(function (tipo) {
    document.addEventListener(tipo, function (e) {
      var noPuxador = e.target.closest && e.target.closest('.com-img-alca');
      if (noPuxador || (engole && tipo === 'click')) {
        e.preventDefault();
        if (tipo !== 'dblclick') e.stopPropagation();
      }
    }, true);
  });

  /*  Duplo clique num puxador: tamanho padrão e posição à esquerda.  */
  document.addEventListener('dblclick', function (e) {
    var alca = e.target.closest && e.target.closest('.com-img-alca');
    if (!alca) return;
    var caixa = alca.closest('.com-img-caixa');
    if (!caixa) return;
    var antesLarg = caixa.style.width, antesMargem = caixa.style.marginLeft, antesX = caixa.dataset.x;
    caixa.style.width = ''; caixa.style.marginLeft = ''; caixa.dataset.x = 0;
    caixa.classList.remove('livre');
    grava(alca, {larg: 0}).catch(function () {
      caixa.style.width = antesLarg; caixa.style.marginLeft = antesMargem; caixa.dataset.x = antesX;
      caixa.classList.add('livre');
    });
  });
})();
