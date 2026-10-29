/* Editor único de Conteúdos: salvar, publicar, pré-visualizar, mídia e excluir.
   O servidor valida tudo de novo; aqui só se cuida da experiência. */
(function () {
  'use strict';
  var form = document.getElementById('form-conteudo-ed');
  if (!form) return;
  var erro = document.getElementById('c-erro'), ok = document.getElementById('c-ok');
  var area = form.querySelector('.re-area');
  var ocupado = false, sujo = false;
  var el = function (id) { return document.getElementById(id); };

  function dados(acao) {
    var fd = new FormData(form);
    if (area) fd.set('corpo', area.innerHTML);
    if (acao) fd.set('acao', acao);
    return fd;
  }
  function travar(sim) {
    ocupado = sim;
    form.querySelectorAll('button[type=submit],#c-excluir,#c-previa-btn').forEach(function (b) { b.disabled = sim; });
  }
  function post(url, fd) {
    return fetch(url, {method: 'POST', body: fd, credentials: 'same-origin'})
      .then(function (r) {
        if (r.status === 401 || r.redirected) return {ok: false, erro: 'Sua sessão expirou. Entre de novo; o texto digitado continua aqui.'};
        return r.json().catch(function () { return {ok: false, erro: 'Resposta inesperada do servidor.'}; });
      }, function () { return {ok: false, erro: 'Sem conexão com o servidor. Nada foi perdido: tente de novo.'}; });
  }

  form.addEventListener('input', function () { sujo = true; });
  window.addEventListener('beforeunload', function (e) { if (sujo && !ocupado) { e.preventDefault(); e.returnValue = ''; } });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (ocupado) return;                                   // evita envio duplicado
    var acao = (e.submitter && e.submitter.dataset.acao) || 'salvar';
    erro.textContent = ''; ok.hidden = true;
    travar(true); ok.textContent = 'Salvando…'; ok.hidden = false;
    post(form.dataset.salvar, dados(acao)).then(function (r) {
      travar(false);
      if (!r.ok) { ok.hidden = true; erro.textContent = r.erro || 'Não foi possível salvar.'; erro.focus && erro.focus(); return; }
      sujo = false;
      ok.textContent = r.mensagem || 'Salvo.';
      // Conteúdo novo passa a ser editado na própria URL; o formulário não é perdido.
      if (!form.elements.id.value) location.href = r.editar; else location.reload();
    });
  });

  /* Mídia: biblioteca, envio e remoção, com miniatura. */
  var prev = el('c-img-prev'), arq = el('c-img-arquivo'), rem = el('c-img-remover');
  if (prev) {
    el('c-img-biblioteca').addEventListener('click', function () {
      window.SeletorMidia.abrir({lista: form.dataset.biblioteca, enviar: form.dataset.enviar, csrf: form.dataset.csrf,
        aoEscolher: function (i) {
          form.elements.imagem_biblioteca.value = i.arquivo; form.elements.imagem_nova.value = '1';
          arq.value = ''; rem.checked = false; prev.src = i.url; prev.hidden = false; sujo = true;
        }});
    });
    arq.addEventListener('change', function () {
      if (!arq.files[0]) return;
      form.elements.imagem_biblioteca.value = ''; form.elements.imagem_nova.value = '1'; rem.checked = false;
      prev.src = URL.createObjectURL(arq.files[0]); prev.hidden = false; sujo = true;
    });
    rem.addEventListener('change', function () { if (rem.checked) { prev.hidden = true; form.elements.imagem_nova.value = ''; } else if (prev.getAttribute('src')) prev.hidden = false; });
  }

  /* Pré-visualização: não grava nada. */
  var painel = el('c-previa'), corpo = el('c-previa-corpo');
  el('c-previa-btn').addEventListener('click', function () {
    erro.textContent = '';
    travar(true);
    post(form.dataset.previa, dados()).then(function (r) {
      travar(false);
      if (!r.ok) { erro.textContent = r.erro || 'Não foi possível pré-visualizar.'; return; }
      corpo.innerHTML = r.html;
      var src = prev && !prev.hidden ? prev.src : '';
      if (src) corpo.querySelectorAll('[data-previa-imagem], .com-imagem').forEach(function (i) { i.src = src; });
      painel.hidden = false; painel.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    });
  });
  painel.addEventListener('click', function (e) {
    var b = e.target.closest('[data-visao]'); if (!b) return;
    painel.querySelectorAll('button[data-visao]').forEach(function (x) { x.classList.toggle('btn-principal', x === b); });
    corpo.querySelectorAll('.previa-visao').forEach(function (v) { v.hidden = v.dataset.visao !== b.dataset.visao; });
  });

  var exc = el('c-excluir');
  if (exc) exc.addEventListener('click', function () {
    if (ocupado || !window.confirm('Excluir este conteúdo? Esta ação não pode ser desfeita.')) return;
    var fd = new FormData(); fd.set('csrf', form.dataset.csrf); fd.set('tipo', form.elements.tipo.value); fd.set('id', form.elements.id.value);
    travar(true);
    post(exc.dataset.url, fd).then(function (r) {
      if (r.ok) { sujo = false; location.href = form.dataset.lista; } else { travar(false); erro.textContent = r.erro || 'Não foi possível excluir.'; }
    });
  });
})();
