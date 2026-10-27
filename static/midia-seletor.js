/* Seletor da biblioteca de imagens.

   window.SeletorMidia.abrir({lista, enviar, csrf, aoEscolher}) mostra as
   imagens já enviadas (com busca) e permite enviar uma nova do computador —
   arrastando-a para a janela ou procurando. Ao escolher, chama
   aoEscolher({arquivo, url, nome, alt}). */
(function () {
  'use strict';
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }

  function abrir(o) {
    var fundo = el('div', 'pe-fundo sm-fundo');
    var j = el('div', 'pe-janela sm-janela');
    j.setAttribute('role', 'dialog'); j.setAttribute('aria-modal', 'true');
    fundo.appendChild(j);
    j.appendChild(el('h3', '', 'Biblioteca de imagens'));

    var barra = el('div', 'sm-barra');
    var busca = el('input'); busca.type = 'search'; busca.placeholder = 'Buscar por nome, título ou descrição…';
    var envia = el('button', 'btn btn-principal', 'Enviar do computador'); envia.type = 'button';
    var arq = el('input'); arq.type = 'file'; arq.accept = '.png,.jpg,.jpeg,.webp,.gif,image/*'; arq.hidden = true;
    barra.appendChild(busca); barra.appendChild(envia); barra.appendChild(arq);
    j.appendChild(barra);
    var msg = el('p', 'pe-erro'); j.appendChild(msg);
    var grade = el('div', 'sm-grade'); j.appendChild(grade);
    var rodape = el('div', 'pe-rodape');
    var fechar = el('button', 'btn', 'Fechar'); fechar.type = 'button';
    rodape.appendChild(fechar); j.appendChild(rodape);

    function fecha() { fundo.remove(); }
    fechar.addEventListener('click', fecha);
    fundo.addEventListener('mousedown', function (e) { if (e.target === fundo) fecha(); });

    function desenha(itens) {
      grade.innerHTML = '';
      if (!itens.length) { grade.appendChild(el('p', 'dica', 'Nenhuma imagem encontrada. Envie uma do computador.')); return; }
      itens.forEach(function (i) {
        var b = el('button', 'sm-item'); b.type = 'button'; b.title = i.nome;
        b.innerHTML = '<img src="' + esc(i.url) + '" alt="" loading="lazy"><span>' + esc(i.nome) + '</span>';
        b.addEventListener('click', function () { fecha(); o.aoEscolher(i); });
        grade.appendChild(b);
      });
    }
    var tempo = null;
    function carrega() {
      fetch(o.lista + '?q=' + encodeURIComponent(busca.value), {credentials: 'same-origin'})
        .then(function (r) { return r.json(); }).then(function (d) { desenha(d.itens || []); })
        .catch(function () { msg.textContent = 'Não consegui carregar a biblioteca.'; });
    }
    busca.addEventListener('input', function () { clearTimeout(tempo); tempo = setTimeout(carrega, 250); });

    function envia1(f) {
      if (!f) return;
      var fd = new FormData(); fd.append('arquivo', f, f.name); fd.append('csrf', o.csrf);
      msg.textContent = 'Enviando…';
      fetch(o.enviar, {method: 'POST', body: fd, credentials: 'same-origin'})
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.ok) { fecha(); o.aoEscolher(d.item); } else msg.textContent = d.erro || 'Não foi possível enviar.';
        }).catch(function () { msg.textContent = 'Sem conexão com o servidor.'; });
    }
    envia.addEventListener('click', function () { arq.click(); });
    arq.addEventListener('change', function () { envia1(arq.files[0]); });
    ['dragover', 'dragenter'].forEach(function (n) { j.addEventListener(n, function (e) { e.preventDefault(); j.classList.add('sobre'); }); });
    ['dragleave', 'drop'].forEach(function (n) { j.addEventListener(n, function (e) { e.preventDefault(); j.classList.remove('sobre'); }); });
    j.addEventListener('drop', function (e) { if (e.dataTransfer.files[0]) envia1(e.dataTransfer.files[0]); });

    document.body.appendChild(fundo);
    carrega();
    busca.focus();
  }
  window.SeletorMidia = {abrir: abrir};

  /* Em qualquer formulário do administrador, o campo de imagem ganha o botão
     "Escolher da biblioteca": a imagem escolhida vai num campo oculto
     "<campo>_biblioteca" e o servidor a reaproveita. */
  function melhora() {
    var csrfEl = document.querySelector('input[name=csrf]');
    if (!csrfEl) return;
    var campos = document.querySelectorAll('form input[type=file][name=imagem], form input[type=file][name=arquivo], form input[type=file][name=capa_arquivo]');
    Array.prototype.forEach.call(campos, function (inp) {
      if (inp.dataset.bib || !/png|image/i.test(inp.accept || '') || /video|zip/i.test(inp.accept || '')) return;
      inp.dataset.bib = '1';
      var oculto = el('input'); oculto.type = 'hidden'; oculto.name = (inp.name === 'capa_arquivo' ? 'capa' : inp.name) + '_biblioteca';
      if (inp.name === 'capa_arquivo') return;           /* a notícia já tem o seu próprio seletor */
      var botao = el('button', 'btn btn-sm', 'Escolher da biblioteca'); botao.type = 'button';
      var nome = el('small', '', '');
      botao.addEventListener('click', function () {
        abrir({lista: '/admin/midia/lista', enviar: '/admin/midia/enviar', csrf: csrfEl.value,
               aoEscolher: function (i) { oculto.value = i.arquivo; nome.textContent = ' Escolhida: ' + i.nome; inp.value = ''; }});
      });
      inp.addEventListener('change', function () { if (inp.files.length) { oculto.value = ''; nome.textContent = ''; } });
      inp.parentNode.insertBefore(botao, inp.nextSibling);
      botao.parentNode.insertBefore(nome, botao.nextSibling);
      botao.parentNode.insertBefore(oculto, botao);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', melhora); else melhora();
})();
