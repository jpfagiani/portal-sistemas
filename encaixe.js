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

    /*  Base alinhada. O encaixe deixa cada cartão com a altura do conteúdo, e
        as colunas acabavam em alturas diferentes — a borda de baixo do painel
        ficava em degraus. Aqui o ÚLTIMO cartão de cada coluna (o que não tem
        outro embaixo dele) cresce até a base da coluna mais alta. Só ele é
        esticado: o espaço entre os cartões continua sendo aproveitado, e a
        sobra vira altura do último cartão, não vão no meio da coluna.  */
    function alinhaBase() {
      var caixas = cartoes.map(function (c) {
        c.style.minHeight = '';              /* medir sempre a altura natural */
        return c;
      });
      caixas.forEach(ajusta);
      var medidas = caixas.map(function (c) {
        var r = c.getBoundingClientRect();
        return { c: c, topo: r.top, base: r.bottom, esq: r.left, dir: r.right };
      }).filter(function (m) { return m.base - m.topo > 0; });
      if (!medidas.length) return;
      var maior = Math.max.apply(null, medidas.map(function (m) { return m.base; }));
      medidas.forEach(function (m) {
        var temAbaixo = medidas.some(function (o) {
          return o !== m && o.topo >= m.base - 1 &&
                 Math.min(o.dir, m.dir) - Math.max(o.esq, m.esq) > 1;
        });
        if (!temAbaixo && maior - m.base > 1) {
          m.c.style.minHeight = (maior - m.topo) + 'px';
          ajusta(m.c);
        }
      });
    }

    /*  A classe entra antes da medição: é ela que tira o `stretch` e deixa o
        cartão com a altura natural.  */
    regiao.classList.add('encaixe');

    /*  Um só refazer por quadro, não importa quantos cartões mudaram.  */
    var pendente = false;
    function agenda() {
      if (pendente) return;
      pendente = true;
      requestAnimationFrame(function () {
        pendente = false;
        alinhaBase();
      });
    }

    var observador = new ResizeObserver(agenda);
    cartoes.forEach(function (c) { observador.observe(c); });
    alinhaBase();

    /*  Mudar a largura da janela pode mudar quanto o texto transborda sem
        mudar a altura do cartão (que está no teto) — então o observador não
        avisa. Refaz tudo.  */
    window.addEventListener('resize', agenda);
    window.addEventListener('load', agenda);
  });
})();
