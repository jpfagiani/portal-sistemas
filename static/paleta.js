/*  Paleta de cores da administração.

    A amostra clicada grava a cor no campo escondido; o seletor livre ao lado
    grava qualquer outra. O campo escondido existe porque a escolha pode ser
    "nenhuma" — voltar ao padrão de Aparência —, e um <input type="color"> não
    consegue representar ausência de cor: ele sempre devolve alguma. */
(function () {
  document.querySelectorAll('[data-paleta]').forEach(function (paleta) {
    if (paleta.dataset.pronta) return;   // a tela pode carregar o script duas vezes
    paleta.dataset.pronta = '1';
    var campo = paleta.querySelector('[data-paleta-valor]');
    var livre = paleta.querySelector('[data-paleta-livre]');
    var amostras = paleta.querySelectorAll('.paleta-amostra');

    function marcar(cor) {
      campo.value = cor;
      var achou = false;
      amostras.forEach(function (a) {
        var igual = a.dataset.cor.toLowerCase() === cor.toLowerCase();
        a.classList.toggle('ativa', igual);
        if (igual) achou = true;
      });
      // Cor que não está na paleta: o próprio seletor livre fica marcado.
      paleta.classList.toggle('livre-ativa', !achou && cor !== '');
      if (cor) livre.value = cor;
    }

    amostras.forEach(function (a) {
      a.addEventListener('click', function () { marcar(a.dataset.cor); });
    });
    livre.addEventListener('input', function () { marcar(livre.value); });

    marcar(campo.value);
  });
})();
