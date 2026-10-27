/* Editor de notícias (tela cheia do administrador): estado de salvamento, aviso de saída,
   erro junto do campo e prévia fiel à página pública.

   - O salvamento é feito por fetch: se algo falhar, o texto digitado continua na tela.
   - A prévia pede ao servidor que desenhe a notícia com o mesmo template da página pública;
     nada é gravado.
   - Funciona sem JavaScript: sem este arquivo o formulário envia do jeito de sempre. */
(function () {
  'use strict';
  var form = document.getElementById('form-noticia');
  if (!form || !form.closest('.pe-form')) return;

  var selo = document.getElementById('ed-estado');
  var msg = document.getElementById('ed-mensagem');
  var painel = document.getElementById('pv-painel');
  var quadro = document.getElementById('pv-quadro');
  var pvEstado = document.getElementById('pv-estado');
  var btnPrevia = document.getElementById('ed-previa');
  form.noValidate = true;   // o aviso de campo vazio é o nosso, junto do campo
  var areas = Array.prototype.slice.call(form.querySelectorAll('.re-area'));
  var sujo = false, salvando = false, tPrevia = null, gesto = null;

  // ── estado ────────────────────────────────────────────────────────────────
  var ROTULOS = { limpo: 'Sem alterações', pendente: 'Alterações não salvas', salvando: 'Salvando…', salvo: 'Salvo', falha: 'Falha ao salvar' };
  function estado(s, extra) {
    if (!selo) return;
    selo.setAttribute('data-s', s);
    selo.textContent = ROTULOS[s] + (extra ? ' ' + extra : '');
  }
  function hora() { var d = new Date(); return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2); }
  function marcaSujo() {
    if (salvando) return;
    if (!sujo) { sujo = true; estado('pendente'); }
    agendaPrevia();
  }

  // O que conta como alteração: texto, links, imagens e estrutura. Ajustes automáticos
  // de alinhamento (só atributos de estilo) não contam; mexer no tamanho ou na posição de
  // uma imagem é detectado pelo gesto do mouse, mais abaixo.
  function assinatura(a) {
    var imgs = Array.prototype.map.call(a.querySelectorAll('img'), function (i) { return i.getAttribute('src'); }).join(',');
    var links = Array.prototype.map.call(a.querySelectorAll('a'), function (l) { return l.getAttribute('href'); }).join(',');
    var blocos = a.querySelectorAll('h2,h3,ul,ol,li,blockquote,strong,b,em,i,u,.cols').length;
    return a.textContent + '|' + imgs + '|' + links + '|' + blocos;
  }
  var base = [];
  function fotografa() { base = areas.map(assinatura); }
  function mudou() { return areas.some(function (a, i) { return assinatura(a) !== base[i]; }); }

  form.addEventListener('input', function (e) {
    if (e.target.closest && e.target.closest('.re-barra')) return;
    marcaSujo();
  });
  form.addEventListener('change', function () { marcaSujo(); });
  areas.forEach(function (a) {
    new MutationObserver(function () { if (mudou()) marcaSujo(); }).observe(a, { childList: true, subtree: true, characterData: true });
    a.addEventListener('pointerdown', function (e) {
      if (e.target.closest && e.target.closest('img, .re-alca')) gesto = { x: e.clientX, y: e.clientY, moveu: false };
    });
  });
  document.addEventListener('pointermove', function (e) {
    if (gesto && !gesto.moveu && Math.abs(e.clientX - gesto.x) + Math.abs(e.clientY - gesto.y) > 4) gesto.moveu = true;
  });
  document.addEventListener('pointerup', function () {
    if (gesto && gesto.moveu) setTimeout(marcaSujo, 60);
    gesto = null;
  });
  // Barra do editor (cores, tamanho de letra, colunas…) também muda o conteúdo.
  form.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('.re-barra button')) setTimeout(function () { if (mudou()) marcaSujo(); }, 80);
  });

  window.addEventListener('beforeunload', function (e) {
    if (!sujo || salvando) return;
    e.preventDefault(); e.returnValue = '';   // o navegador mostra o aviso próprio
  });

  // ── erro junto do campo ───────────────────────────────────────────────────
  function limpaErros() {
    Array.prototype.forEach.call(form.querySelectorAll('[aria-invalid]'), function (c) { c.removeAttribute('aria-invalid'); c.removeAttribute('aria-describedby'); });
    Array.prototype.forEach.call(form.querySelectorAll('.ed-erro-campo'), function (n) { n.remove(); });
    if (msg) { msg.textContent = ''; msg.hidden = true; }
  }
  function erroCampo(nome, texto) {
    var c = nome && form.elements[nome];
    if (c && c.type !== 'hidden') {
      var id = 'ed-erro-' + nome;
      var d = document.createElement('div');
      d.className = 'ed-erro-campo'; d.id = id; d.setAttribute('role', 'alert'); d.textContent = texto;
      c.setAttribute('aria-invalid', 'true'); c.setAttribute('aria-describedby', id);
      c.parentNode.insertBefore(d, c.nextSibling);
      c.focus();
      return;
    }
    if (msg) { msg.textContent = texto; msg.hidden = false; }
  }

  // ── salvar ────────────────────────────────────────────────────────────────
  form.addEventListener('submit', function (e) {
    if (!window.fetch || !window.FormData) return;          // navegador antigo: envio normal
    e.preventDefault();
    var botao = e.submitter || null;
    limpaErros();
    var titulo = form.elements.titulo;
    if (!titulo.value.trim()) { estado(sujo ? 'pendente' : 'limpo'); erroCampo('titulo', 'Informe o título.'); return; }
    if (salvando) return;
    salvando = true; estado('salvando');
    Array.prototype.forEach.call(form.querySelectorAll('.acoes .btn'), function (b) { b.setAttribute('aria-disabled', 'true'); });
    // O editor rico copia o texto para os campos ocultos no próprio "submit"; o envio espera
    // essa cópia terminar.
    setTimeout(function () {
      var fd = new FormData(form);
      fd.set('ajax', '1');
      fd.set('acao', botao && botao.value ? botao.value : 'salvar');
      fetch(location.pathname + location.search, { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
        .then(function (r) { return r.json().catch(function () { return { ok: false, erro: 'O servidor respondeu de um jeito inesperado. Seu texto continua aqui.' }; }); },
              function () { return { ok: false, erro: 'Sem conexão com o servidor. Seu texto continua aqui; tente salvar de novo.' }; })
        .then(function (r) {
          salvando = false;
          Array.prototype.forEach.call(form.querySelectorAll('.acoes .btn'), function (b) { b.removeAttribute('aria-disabled'); });
          if (r && r.ok) {
            sujo = false; estado('salvo', 'às ' + hora());
            try { sessionStorage.setItem('ed-salvo', hora()); } catch (x) { /* sem armazenamento: sem selo após recarregar */ }
            location.replace(r.url);                           // recarrega já com o id e a lista atualizados
            return;
          }
          sujo = true; estado('falha');
          erroCampo(r && r.campo, (r && r.erro) || 'Não foi possível salvar.');
        });
    }, 0);
  });

  // ── prévia ────────────────────────────────────────────────────────────────
  function corpoLimpo(a) {
    var c = a.cloneNode(true);
    Array.prototype.forEach.call(c.querySelectorAll('.re-alcas, .re-alca'), function (n) { n.remove(); });
    Array.prototype.forEach.call(c.querySelectorAll('[data-sel]'), function (n) { n.removeAttribute('data-sel'); });
    return c.innerHTML;
  }
  function atualizaPrevia() {
    if (!painel || painel.hidden) return;
    pvEstado.textContent = 'Atualizando…';
    var fd = new FormData(form);
    areas.forEach(function (a) {
      var h = a.closest('[data-rico]'); var o = h && h.querySelector('input[type=hidden]');
      if (o) fd.set(o.name, corpoLimpo(a));
    });
    fetch('/admin/noticias/previa', { method: 'POST', body: fd, credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
      .then(function (html) { quadro.srcdoc = html; pvEstado.textContent = 'Atualizada às ' + hora(); })
      .catch(function () { pvEstado.textContent = 'Não foi possível atualizar a prévia.'; });
  }
  function agendaPrevia() {
    if (!painel || painel.hidden) return;
    clearTimeout(tPrevia); tPrevia = setTimeout(atualizaPrevia, 900);
  }
  function abrePrevia() { painel.hidden = false; btnPrevia.setAttribute('aria-expanded', 'true'); document.body.classList.add('pv-aberta'); atualizaPrevia(); }
  function fechaPrevia() { painel.hidden = true; btnPrevia.setAttribute('aria-expanded', 'false'); document.body.classList.remove('pv-aberta'); btnPrevia.focus(); }
  if (btnPrevia && painel) {
    btnPrevia.addEventListener('click', function () { if (painel.hidden) abrePrevia(); else fechaPrevia(); });
    document.getElementById('pv-fechar').addEventListener('click', fechaPrevia);
    document.getElementById('pv-atualizar').addEventListener('click', atualizaPrevia);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !painel.hidden && !document.querySelector('.sm-fundo')) fechaPrevia(); });
  }

  // ── início ────────────────────────────────────────────────────────────────
  var salvoAntes = '';
  try { salvoAntes = sessionStorage.getItem('ed-salvo') || ''; sessionStorage.removeItem('ed-salvo'); } catch (x) { /* ignora */ }
  estado(salvoAntes ? 'salvo' : 'limpo', salvoAntes ? 'às ' + salvoAntes : '');
  // O editor ajusta o alinhamento ao abrir; a "fotografia" vem depois disso.
  window.addEventListener('load', function () { setTimeout(fotografa, 700); });
  fotografa();
})();
