/* Edição da notícia na própria página (só administrador): uma janela com
   título, capa, texto com imagens e situação. Salva por /admin/noticia-rapida. */
(function () {
  'use strict';
  var fundo = document.getElementById('noticia-fundo');
  if (!fundo) return;
  var form = document.getElementById('form-noticia');
  var area = form.querySelector('.re-area');
  var erro = document.getElementById('noticia-erro');
  var prev = document.getElementById('ne-capa-prev');
  var arq = document.getElementById('ne-capa-arquivo');
  var rem = document.getElementById('ne-capa-remover');

  function abre() { erro.textContent = ''; fundo.style.display = 'flex'; (document.getElementById('ne-titulo') || form.querySelector('input:not([type=hidden]):not([type=file]):not([type=checkbox])')).focus(); }
  function fecha() { fundo.style.display = 'none'; }
  document.addEventListener('click', function (e) { if (e.target.closest('[data-editar-noticia]')) { e.preventDefault(); abre(); } });
  document.getElementById('noticia-cancelar').addEventListener('click', fecha);
  fundo.addEventListener('mousedown', function (e) { if (e.target === fundo) fecha(); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && fundo.style.display !== 'none' && !document.querySelector('.sm-fundo')) fecha();
  });
  if (location.hash === '#editar') abre();

  document.getElementById('ne-capa-biblioteca').addEventListener('click', function () {
    if (!window.SeletorMidia) { erro.textContent = 'A biblioteca não está disponível.'; return; }
    var raiz = form.querySelector('[data-rico]');
    window.SeletorMidia.abrir({
      lista: raiz.dataset.lista, enviar: raiz.dataset.enviar, csrf: raiz.dataset.csrf,
      aoEscolher: function (i) {
        form.elements.capa_biblioteca.value = i.arquivo; arq.value = ''; rem.checked = false;
        prev.src = i.url; prev.hidden = false;
        if (form.elements.capa_alt && !form.elements.capa_alt.value && i.alt) form.elements.capa_alt.value = i.alt;
      }
    });
  });
  arq.addEventListener('change', function () {
    var f = arq.files[0]; if (!f) return;
    form.elements.capa_biblioteca.value = ''; rem.checked = false;
    prev.src = URL.createObjectURL(f); prev.hidden = false;
  });
  rem.addEventListener('change', function () { if (rem.checked) { prev.hidden = true; arq.value = ''; form.elements.capa_biblioteca.value = ''; } else if (prev.src) prev.hidden = false; });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    erro.textContent = 'Salvando…';
    var h = area.querySelector('img[data-sel]'); if (h) h.removeAttribute('data-sel');
    var fd = new FormData(form);
    fd.set('corpo', area.innerHTML);
    fetch(form.action, {method: 'POST', body: fd, credentials: 'same-origin'})
      .then(function (r) { return r.json().catch(function () { return {ok: false, erro: 'Erro ao salvar.'}; }); },
            function () { return {ok: false, erro: 'Sem conexão com o servidor.'}; })
      .then(function (r) { if (r.ok) location.reload(); else erro.textContent = r.erro || 'Não foi possível salvar.'; });
  });
})();
