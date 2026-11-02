/* Editor de notícia em painéis: salvar, publicar, prévia ao vivo (nada é gravado), mídia e destino do clique.
   O servidor valida tudo de novo; aqui só se cuida da experiência. */
(function () {
  'use strict';
  var form = document.getElementById('form-ne');
  if (!form) return;
  var $ = function (id) { return document.getElementById(id); };
  var erro = $('ne-erro'), estado = $('ne-estado-txt'), painel = $('ne-previa'), corpoPrevia = $('ne-previa-corpo');
  var ocupado = false, sujo = false, seq = 0, timer = null;

  function hora() { var d = new Date(); return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2); }
  function situacao(txt, cls) { estado.textContent = txt; estado.className = cls || ''; }

  function dados(acao, paraPrevia) {
    var fd = new FormData(form);
    form.querySelectorAll('[data-rico]').forEach(function (raiz) {
      var a = raiz.querySelector('.re-area'), h = raiz.querySelector('input[type=hidden]');
      if (a && h && h.name) fd.set(h.name, a.innerHTML);
    });
    if (acao) fd.set('acao', acao);
    if (paraPrevia) {                       // a prévia não precisa dos arquivos: só saber que há um
      var fch = $('ne-ch-arquivo'), fcapa = $('ne-capa-arquivo');
      var temCh = fch ? fch.files.length : 0, temCapa = fcapa ? fcapa.files.length : 0;
      fd.delete('imagem'); fd.delete('chamada_arquivo');
      if (temCapa) fd.set('imagem_nova', '1');
      if (temCh) fd.set('chamada_arquivo', new Blob([''], {type: 'image/png'}), 'x.png');
    }
    return fd;
  }
  function travar(sim) {
    ocupado = sim;
    form.querySelectorAll('button[type=submit],#ne-excluir').forEach(function (b) { b.disabled = sim; });
  }
  function post(url, fd) {
    return fetch(url, {method: 'POST', body: fd, credentials: 'same-origin'}).then(function (r) {
      if (r.status === 401 || r.redirected) return {ok: false, erro: 'Sua sessão expirou. Entre de novo; o texto digitado continua aqui.'};
      return r.json().catch(function () { return {ok: false, erro: 'Resposta inesperada do servidor.'}; });
    }, function () { return {ok: false, erro: 'Sem conexão com o servidor. Nada foi perdido: tente de novo.'}; });
  }

  /* ── alterações pendentes e prévia ao vivo ── */
  function alterou() {
    sujo = true;
    if (!ocupado) situacao('● Alterações não salvas', 'ne2-pend');
    clearTimeout(timer); timer = setTimeout(atualizarPrevia, 700);
  }
  form.addEventListener('input', alterou);
  form.addEventListener('change', alterou);
  window.addEventListener('beforeunload', function (e) { if (sujo && !ocupado) { e.preventDefault(); e.returnValue = ''; } });

  /* ── salvar / publicar ── */
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (ocupado) return;
    var acao = (e.submitter && e.submitter.dataset.acao) || 'salvar';
    erro.textContent = '';
    travar(true); situacao('⟳ Salvando…', 'ne2-salvando');
    post(form.dataset.salvar, dados(acao)).then(function (r) {
      travar(false);
      if (!r.ok) {
        situacao('✖ Não salvo', 'ne2-erro');
        erro.textContent = r.erro || 'Não foi possível salvar.';
        return;                                        // o conteúdo digitado continua na tela
      }
      sujo = false;
      situacao('✔ ' + (r.mensagem || 'Salvo') + ' às ' + hora(), 'ne2-ok');
      if (!form.elements.id.value) location.href = r.editar; else location.reload();
    });
  });

  /* ── contadores ── */
  function conta() {
    form.querySelectorAll('.ne2-conta[data-para]').forEach(function (s) {
      var c = $(s.dataset.para); s.textContent = 'Caracteres: ' + c.value.length + '/' + c.dataset.conta;
    });
    [['ne-corpo-conta', 0], ['ne-mat-conta', 1]].forEach(function (x) {
      var a = form.querySelectorAll('.re-area')[x[1]], o = $(x[0]);
      if (a && o) o.textContent = 'Quantidade de caracteres: ' + (a.textContent || '').trim().length;
    });
  }
  form.addEventListener('input', conta); conta();

  /* ── destino do clique ── */
  var dt = $('ne-dest-tipo'), di = $('ne-dest-interna'), de = $('ne-dest-externa');
  function destino() {
    di.hidden = dt.value !== 'interna'; de.hidden = dt.value !== 'externa';
    form.elements.url.value = dt.value === 'interna' ? di.value : dt.value === 'externa' ? de.value.trim() : '';
  }
  [dt, di, de].forEach(function (x) { x.addEventListener('input', destino); x.addEventListener('change', destino); });

  /* ── categoria ── */
  var cs = $('ne-cat-sel'), cn = $('ne-cat-nova');
  function categoria() {
    if (!cs) return;
    cn.hidden = cs.value !== '__nova__';
    form.elements.categoria.value = cs.value === '__nova__' ? cn.value.trim() : cs.value;
  }
  if (cs) {
    cs.addEventListener('change', function () { categoria(); if (!cn.hidden) cn.focus(); });
    cn.addEventListener('input', categoria);
    $('ne-ordem-topo').addEventListener('click', function () { $('ne-ordem').value = 1; alterou(); });
  }

  /* ── imagens: biblioteca, envio e remoção, com miniatura ── */
  function imagem(c) {
    if (!$(c.prev)) return;                                // cartões e comunicados não têm capa separada
    var prev = $(c.prev), sem = $(c.sem), arq = $(c.arq), rem = $(c.rem);
    function mostra(src) { prev.src = src; prev.hidden = !src; sem.hidden = !!src; if (c.ver) { var v = $(c.ver); if (src && src.indexOf('blob:') !== 0) { v.href = src; v.hidden = false; } else v.hidden = true; } }
    $(c.biblioteca).addEventListener('click', function () {
      window.SeletorMidia.abrir({lista: form.dataset.biblioteca, enviar: form.dataset.enviar, csrf: form.dataset.csrf,
        aoEscolher: function (i) { form.elements[c.campoBib].value = i.arquivo; if (c.nova) form.elements.imagem_nova.value = '1';
          arq.value = ''; rem.checked = false; mostra(i.url); alterou(); }});
    });
    arq.addEventListener('change', function () {
      if (!arq.files[0]) return;
      form.elements[c.campoBib].value = ''; rem.checked = false; mostra(URL.createObjectURL(arq.files[0])); alterou();
    });
    $(c.tirar).addEventListener('click', function () {
      rem.checked = true; arq.value = ''; form.elements[c.campoBib].value = ''; if (c.nova) form.elements.imagem_nova.value = '';
      mostra(''); alterou();
    });
  }
  imagem({prev: 'ne-ch-prev', sem: 'ne-ch-sem', arq: 'ne-ch-arquivo', rem: 'ne-ch-remover', biblioteca: 'ne-ch-trocar', tirar: 'ne-ch-tirar', campoBib: 'chamada_biblioteca'});
  imagem({prev: 'ne-capa-prev', sem: 'ne-capa-sem', arq: 'ne-capa-arquivo', rem: 'ne-capa-remover', biblioteca: 'ne-capa-trocar', tirar: 'ne-capa-tirar', campoBib: 'imagem_biblioteca', nova: true, ver: 'ne-capa-ver'});

  /* ── prévia: não grava nada ── */
  function srcDe(img) { return img && !img.hidden ? img.src : ''; }
  function atualizarPrevia() {
    var minha = ++seq;
    post(form.dataset.previa, dados(null, true)).then(function (r) {
      if (minha !== seq) return;                           // resposta velha: ignora
      if (!r.ok) { $('ne-previa-chamada').innerHTML = '<p class="pe-erro">' + (r.erro || 'Prévia indisponível.') + '</p>'; return; }
      var t = document.createElement('div'); t.innerHTML = r.html;
      var ch = t.querySelector('[data-visao="chamada"]');
      $('ne-previa-chamada').innerHTML = ch ? ch.innerHTML : '';
      if (ch && !form.dataset.cartao) ch.remove();
      corpoPrevia.innerHTML = t.innerHTML;
      var capa = srcDe($('ne-capa-prev')), cham = srcDe($('ne-ch-prev')) || capa;
      if (capa) corpoPrevia.querySelectorAll('[data-previa-imagem]').forEach(function (i) { i.src = capa; });
      if (cham) { document.querySelectorAll('#ne-previa-chamada [data-previa-chamada], #ne-previa-corpo [data-previa-chamada]').forEach(function (i) { i.src = cham; }); }
      corpoPrevia.querySelectorAll('.previa-visao').forEach(function (v) { v.hidden = v.dataset.visao !== painel.dataset.visao; });
    });
  }
  function visao(v) {
    painel.dataset.visao = v;
    painel.querySelectorAll('.ne2-abas [data-visao]').forEach(function (b) { b.classList.toggle('ativa', b.dataset.visao === v); });
    corpoPrevia.querySelectorAll('.previa-visao').forEach(function (x) { x.hidden = x.dataset.visao !== v; });
  }
  function aparelho(a) {
    painel.dataset.aparelho = a;
    painel.querySelectorAll('[data-aparelho]').forEach(function (b) { b.classList.toggle('btn-principal', b.dataset.aparelho === a); });
    painel.querySelector('[data-mobile]').classList.toggle('ativa', a === 'cel');
  }
  painel.addEventListener('click', function (e) {
    var v = e.target.closest('.ne2-abas [data-visao]'), a = e.target.closest('[data-aparelho]'), m = e.target.closest('[data-mobile]');
    if (v) { visao(v.dataset.visao); if (painel.dataset.aparelho === 'cel') aparelho('pc'); }
    if (a) aparelho(a.dataset.aparelho);
    if (m) { aparelho('cel'); }
  });
  $('ne-previa-btn').addEventListener('click', function () { atualizarPrevia(); painel.scrollIntoView({behavior: 'smooth', block: 'start'}); });

  /* ── excluir ── */
  var mover = $('ne-mover');
  if (mover) mover.addEventListener('click', function () {
    if (ocupado) return;
    var t = window.prompt('Texto de chamada que fica no cartão, abaixo da imagem. O texto atual vai inteiro para a matéria completa:', form.elements.titulo.value || '');
    if (t === null) return;
    var fd = new FormData(); fd.set('csrf', form.dataset.csrf); fd.set('tipo', form.elements.tipo.value); fd.set('id', form.elements.id.value); fd.set('chamada', t);
    travar(true);
    post(mover.dataset.url, fd).then(function (r) {
      if (r.ok) { sujo = false; location.reload(); } else { travar(false); erro.textContent = r.erro || 'Não foi possível mover o texto.'; }
    });
  });

  var exc = $('ne-excluir');
  if (exc) exc.addEventListener('click', function () {
    if (ocupado || !window.confirm('Excluir esta notícia? Esta ação não pode ser desfeita.')) return;
    var fd = new FormData(); fd.set('csrf', form.dataset.csrf); fd.set('tipo', form.elements.tipo.value); fd.set('id', form.elements.id.value);
    travar(true);
    post(exc.dataset.url, fd).then(function (r) {
      if (r.ok) { sujo = false; location.href = form.dataset.lista; } else { travar(false); erro.textContent = r.erro || 'Não foi possível excluir.'; }
    });
  });

  categoria(); destino(); atualizarPrevia();
  sujo = false;
})();
