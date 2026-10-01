/*  Mapa do painel: arrastar os cartões para a região e a coluna desejadas.

    Usa o arrastar-e-soltar do próprio navegador, sem biblioteca — o portal é
    de rede interna e não baixa nada de fora.

    Nada é gravado enquanto se arrasta: as mudanças ficam na tela até alguém
    clicar em Salvar. Assim dá para experimentar arranjos sem deixar o painel
    da unidade mudando a cada movimento do mouse.  */
(function () {
  'use strict';
  var mapa = document.querySelector('[data-mapa]');
  if (!mapa) return;

  var arrastado = null;
  var salvar = mapa.querySelector('[data-salvar]');
  var aviso = mapa.querySelector('[data-aviso]');

  function sujo() {
    if (aviso) aviso.hidden = false;
    if (salvar) salvar.disabled = false;
  }

  /*  A largura do cartão é quantas colunas ele ocupa. Presa entre 1 e 3: a
      grade tem três, e um cartão mais largo que a grade transbordaria.  */
  function larguraDe(cartao) {
    return Math.min(3, Math.max(1, parseInt(cartao.dataset.larg, 10) || 1));
  }

  function pintaLargura(cartao) {
    var n = larguraDe(cartao);
    cartao.dataset.larg = n;
    cartao.style.gridColumnEnd = 'span ' + n;
    var rotulo = cartao.querySelector('[data-larg-rotulo]');
    if (rotulo) rotulo.textContent = n + (n > 1 ? ' colunas' : ' coluna');
  }

  mapa.querySelectorAll('[data-cartao]').forEach(function (cartao) {
    pintaLargura(cartao);

    cartao.addEventListener('dragstart', function (e) {
      arrastado = cartao;
      cartao.classList.add('arrastando');
      e.dataTransfer.effectAllowed = 'move';
      /*  Firefox só inicia o arrasto se houver dado no dataTransfer.  */
      e.dataTransfer.setData('text/plain', cartao.dataset.cartao);
    });

    cartao.addEventListener('dragend', function () {
      cartao.classList.remove('arrastando');
      mapa.querySelectorAll('.alvo').forEach(function (c) {
        c.classList.remove('alvo');
      });
      arrastado = null;
    });

    cartao.querySelectorAll('[data-larg-menos],[data-larg-mais]').forEach(function (b) {
      b.addEventListener('click', function () {
        var passo = b.hasAttribute('data-larg-mais') ? 1 : -1;
        cartao.dataset.larg = larguraDe(cartao) + passo;
        pintaLargura(cartao);
        sujo();
      });
    });
  });

  mapa.querySelectorAll('[data-celula]').forEach(function (celula) {
    celula.addEventListener('dragover', function (e) {
      if (!arrastado) return;
      e.preventDefault();                 /* sem isto o soltar não acontece */
      e.dataTransfer.dropEffect = 'move';
      celula.classList.add('alvo');
    });

    celula.addEventListener('dragleave', function () {
      celula.classList.remove('alvo');
    });

    celula.addEventListener('drop', function (e) {
      if (!arrastado) return;
      e.preventDefault();
      celula.classList.remove('alvo');
      celula.appendChild(arrastado);
      sujo();
    });
  });

  /*  Ao salvar, a posição de cada cartão é lida da tela: região e coluna vêm
      da célula onde ele parou. Ler do DOM em vez de acompanhar cada movimento
      evita que um arrasto perdido deixe o estado guardado diferente do que se
      vê.

      A ordem é gravada por LINHA, não por coluna: dentro de cada região vêm
      primeiro os cartões que estão no topo das colunas (da esquerda para a
      direita), depois os do segundo nível, e assim por diante. Percorrer célula
      por célula gravava a ordem coluna por coluna, e o painel — que é uma grade
      lida linha a linha — montava os cartões fora do lugar. Essa ordem também é
      a de leitura natural quando a tela estreita e tudo vira uma coluna só.  */
  if (salvar) {
    salvar.addEventListener('click', function () {
      var porRegiao = {};          /* regiao -> [{cartao, celula, nivel, coluna}] */
      var regioes = [];
      mapa.querySelectorAll('[data-celula]').forEach(function (celula) {
        var regiao = celula.dataset.regiao;
        if (!porRegiao[regiao]) { porRegiao[regiao] = []; regioes.push(regiao); }
        celula.querySelectorAll('[data-cartao]').forEach(function (cartao, nivel) {
          porRegiao[regiao].push({
            cartao: cartao,
            celula: celula,
            nivel: nivel,
            coluna: parseInt(celula.dataset.coluna, 10)
          });
        });
      });

      var posicoes = [];
      var n = 0;
      regioes.forEach(function (regiao) {
        porRegiao[regiao].sort(function (a, b) {
          return (a.nivel - b.nivel) || (a.coluna - b.coluna);
        });
        porRegiao[regiao].forEach(function (p) {
          posicoes.push({
            ref: p.cartao.dataset.cartao,
            regiao: regiao,
            coluna: p.coluna,
            largura: larguraDe(p.cartao),
            ordem: n++
          });
        });
      });
      mapa.querySelector('[data-posicoes]').value = JSON.stringify(posicoes);
      mapa.querySelector('form').submit();
    });
  }
})();
