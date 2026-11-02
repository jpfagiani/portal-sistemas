/* Bloco "Destino do clique" do editor de Conteúdos: mostra só o campo do tipo escolhido.
   Só conforto de tela — o servidor valida o destino de novo e ignora os campos dos outros tipos. */
(function () {
  'use strict';
  var bloco = document.querySelector('[data-destino]');
  if (!bloco) return;
  function atualiza() {
    var marcado = bloco.querySelector('input[name=destino_tipo]:checked');
    var tipo = marcado ? marcado.value : 'padrao';
    bloco.querySelectorAll('[data-destino-grupo]').forEach(function (g) {
      g.hidden = g.dataset.destinoGrupo !== tipo;
    });
    var nova = bloco.querySelector('input[name=nova_aba]');
    if (nova) nova.closest('label').hidden = (tipo === 'padrao' || tipo === 'nenhum');
  }
  bloco.addEventListener('change', atualiza);
  atualiza();
})();
