/*  Encaixe dos cartões do painel.

    A grade de cada região tem linhas finas (4px). Aqui se mede a altura real
    de cada cartão e ele passa a ocupar essa quantidade de linhas. Resultado: o
    cartão tem a altura do próprio conteúdo, e o espaço que sobra embaixo dele
    é usado pelo cartão seguinte da mesma coluna, em vez de ficar vazio só
    porque o vizinho é mais alto.

    Os cartões são observados: quando a altura muda — imagem que termina de
    carregar, busca de ramais escondendo linhas, janela redimensionada — o
    número de linhas é refeito. Sem ResizeObserver (navegador muito antigo)
    nada é feito e o painel segue na grade comum.  */
(function () {
  'use strict';
  if (!('ResizeObserver' in window)) return;

  var UNIDADE = 4;   /* igual a `grid-auto-rows` em .encaixe, no style.css */

  document.querySelectorAll(
    '.regiao-topo, .regiao-meio-grade, .regiao-baixo'
  ).forEach(function (regiao) {
    var cartoes = Array.prototype.filter.call(regiao.children, function (el) {
      return el.classList.contains('cartao');
    });
    if (!cartoes.length) return;

    function ajusta(cartao) {
      /*  Texto longo: o degradê do fim só vale se o texto realmente passa do
          limite do cartão. Esmaecer o último trecho de um texto que cabe
          inteiro parece defeito.  */
      cartao.querySelectorAll('p.cortado').forEach(function (p) {
        p.classList.toggle('transborda', p.scrollHeight > p.clientHeight + 1);
      });
      var vao = parseFloat(getComputedStyle(regiao).columnGap) || 16;
      var alto = cartao.getBoundingClientRect().height;
      cartao.style.gridRowEnd =
        'span ' + Math.max(1, Math.ceil((alto + vao) / UNIDADE));
    }

    /*  A classe entra antes da medição: é ela que tira o `stretch` e deixa o
        cartão com a altura natural.  */
    regiao.classList.add('encaixe');

    var observador = new ResizeObserver(function (entradas) {
      entradas.forEach(function (e) { ajusta(e.target); });
    });
    cartoes.forEach(function (c) {
      ajusta(c);
      observador.observe(c);
    });

    /*  Mudar a largura da janela pode mudar quanto o texto transborda sem
        mudar a altura do cartão (que está no teto) — então o observador não
        avisa. Refaz tudo, uma vez por quadro.  */
    var pendente = false;
    window.addEventListener('resize', function () {
      if (pendente) return;
      pendente = true;
      requestAnimationFrame(function () {
        pendente = false;
        cartoes.forEach(ajusta);
      });
    });
  });
})();
