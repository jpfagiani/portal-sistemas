/*  Ajuste do tamanho da imagem de um item, arrastando a borda com o mouse.

    Só é carregado para o administrador (shell.html). Cada imagem acima do texto
    vem com dois puxadores, na borda direita e no canto de baixo; arrastar
    qualquer um muda a largura, e a altura acompanha (a proporção é mantida).
    Ao soltar, a largura é gravada em % da área do texto, então o tamanho
    escolhido continua proporcional em telas de largura diferente.

    Duplo clique num puxador volta ao tamanho padrão.  */
(function () {
  'use strict';

  var MIN = 10;     /* % — menor que isto some a imagem */
  var MAX = 100;    /* % — a imagem não passa da largura do texto */

  function grava(alca, larg) {
    var corpo = new URLSearchParams();
    corpo.set('csrf', alca.dataset.csrf);
    corpo.set('larg', String(larg));
    return fetch(alca.dataset.url, {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: corpo.toString()
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
    });
  }

  /*  Etiqueta com a medida, enquanto arrasta.  */
  var etiqueta = document.createElement('div');
  etiqueta.className = 'com-img-etiqueta';

  document.addEventListener('pointerdown', function (e) {
    var alca = e.target.closest && e.target.closest('.com-img-alca');
    if (!alca || e.button > 0) return;
    var caixa = alca.closest('.com-img-caixa');
    if (!caixa) return;
    e.preventDefault();

    var pai = caixa.parentElement.getBoundingClientRect().width;
    var inicial = caixa.getBoundingClientRect().width;
    var antes = caixa.style.width;
    var jaLivre = caixa.classList.contains('livre');
    var x0 = e.clientX;
    var pct = inicial / pai * 100;
    var moveu = false;
    caixa.classList.add('livre', 'ajustando');
    caixa.appendChild(etiqueta);
    alca.setPointerCapture(e.pointerId);

    function move(ev) {
      if (Math.abs(ev.clientX - x0) < 3 && !moveu) return;   /* clique, não arrasto */
      moveu = true;
      pct = Math.max(MIN, Math.min(MAX, (inicial + ev.clientX - x0) / pai * 100));
      if (pct > 97) pct = 100;          /* perto da borda, encaixa na largura toda */
      caixa.style.width = pct.toFixed(1) + '%';
      etiqueta.textContent = Math.round(pct) + '%';
    }

    function solta() {
      alca.removeEventListener('pointermove', move);
      alca.removeEventListener('pointerup', solta);
      alca.removeEventListener('pointercancel', solta);
      caixa.classList.remove('ajustando');
      if (etiqueta.parentNode) etiqueta.parentNode.removeChild(etiqueta);
      /*  Só clicou (ou foi o primeiro clique de um duplo clique): nada a gravar.
          Gravar aqui disputava com o pedido de "voltar ao padrão".  */
      if (!moveu) return;
      var larg = Math.round(pct);
      grava(alca, larg).catch(function () {
        /*  Não gravou (sessão expirada, servidor fora): volta ao que estava,
            para a tela não mostrar um tamanho que não ficou guardado.  */
        caixa.style.width = antes;
        if (!jaLivre) caixa.classList.remove('livre');
        window.alert('Não foi possível salvar o tamanho da imagem. ' +
                     'Recarregue a página e tente de novo.');
      });
    }

    alca.addEventListener('pointermove', move);
    alca.addEventListener('pointerup', solta);
    alca.addEventListener('pointercancel', solta);
  });

  /*  Em item do tipo Link o puxador fica dentro do <a> do cartão: sem isto,
      soltar o mouse depois de arrastar (ou clicar no puxador) abriria o link.  */
  ['click', 'auxclick', 'dblclick'].forEach(function (tipo) {
    document.addEventListener(tipo, function (e) {
      if (e.target.closest && e.target.closest('.com-img-alca')) {
        e.preventDefault();
        if (tipo !== 'dblclick') e.stopPropagation();
      }
    }, true);
  });

  /*  Impede o navegador de começar a "arrastar o link" em vez de redimensionar.  */
  document.addEventListener('dragstart', function (e) {
    if (e.target.closest && e.target.closest('.com-img-alca')) e.preventDefault();
  }, true);

  document.addEventListener('dblclick', function (e) {
    var alca = e.target.closest && e.target.closest('.com-img-alca');
    if (!alca) return;
    var caixa = alca.closest('.com-img-caixa');
    if (!caixa) return;
    var antes = caixa.style.width;
    caixa.style.width = '';
    caixa.classList.remove('livre');
    grava(alca, 0).catch(function () {
      caixa.style.width = antes;
      caixa.classList.add('livre');
    });
  });
})();
