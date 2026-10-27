/* Edição direta das páginas de conteúdo (só para o administrador).

   Botão direito num bloco abre um menu: editar, adicionar abaixo, subir, descer
   e excluir. "Editar" e "Adicionar" abrem uma janela única onde se escreve o
   texto, arrasta-se (ou procura-se no computador) a imagem e define-se para
   onde o clique leva. Tudo é salvo pelo mesmo endereço do editor completo. */
(function () {
  'use strict';
  var raiz = document.querySelector('[data-edicao]');
  if (!raiz) return;

  function json(id) {
    try { return JSON.parse(document.getElementById(id).textContent); } catch (e) { return null; }
  }
  var dados = json('dados-blocos') || [];
  var destinos = json('dados-destinos') || [];
  var opc = json('dados-opcoes') || {larguras: [], alinhamentos: [], estilos: []};
  var csrf = raiz.dataset.csrf, alvo = raiz.dataset.salvar;
  var porId = {};
  dados.forEach(function (d) { porId[d.id] = d; });

  var TIPOS = [['texto', 'Texto'], ['imagem', 'Imagem'], ['subtitulo', 'Subtítulo'], ['botao', 'Botão de link']];
  var NOME_TIPO = {texto: 'Texto', imagem: 'Imagem', subtitulo: 'Subtítulo', botao: 'Botão de link'};

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) {
    return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }

  /* Volta ao mesmo ponto da página depois de salvar. */
  try {
    var y = sessionStorage.getItem('pe-scroll');
    if (y) { sessionStorage.removeItem('pe-scroll'); window.scrollTo(0, +y); }
  } catch (e) {}
  function recarrega() {
    try { sessionStorage.setItem('pe-scroll', String(window.scrollY)); } catch (e) {}
    location.reload();
  }

  function enviar(fd, erroEm) {
    fd.append('csrf', csrf);
    fd.append('ajax', '1');
    return fetch(alvo, {method: 'POST', body: fd, credentials: 'same-origin'})
      .then(function (r) { return r.json().catch(function () { return {ok: false, erro: 'Resposta inesperada do servidor.'}; }); })
      .then(function (j) {
        if (j.ok) { recarrega(); return; }
        if (erroEm) erroEm.textContent = j.erro || 'Não foi possível salvar.';
        else window.alert(j.erro || 'Não foi possível concluir.');
      })
      .catch(function () {
        if (erroEm) erroEm.textContent = 'Sem conexão com o servidor.'; });
  }
  function acao(a, id, extra) {
    var fd = new FormData();
    fd.append('acao', a); fd.append('id', id);
    Object.keys(extra || {}).forEach(function (k) { fd.append(k, extra[k]); });
    return enviar(fd);
  }

  /* ── bloco sob o cursor ── */
  function blocoDe(alvoEl) {
    var e = alvoEl.closest ? alvoEl.closest('.bl, .pi') : null;
    if (!e || !/^b\d+$/.test(e.id || '') || !raiz.contains(e)) return null;
    return porId[+e.id.slice(1)] || null;
  }

  /* ── menu do botão direito ── */
  var menu = null, abertoEm = 0;
  function fechaMenu() { if (menu) { menu.remove(); menu = null; } }
  function abreMenu(x, y, bloco) {
    fechaMenu();
    menu = el('div', 'pe-menu');
    function item(rotulo, fn, perigo) {
      var b = el('button', perigo ? 'perigo' : '', esc(rotulo));
      b.type = 'button';
      b.addEventListener('click', function () { fechaMenu(); fn(); });
      menu.appendChild(b);
    }
    if (bloco) {
      menu.appendChild(el('div', 'pe-menu-tit', esc(NOME_TIPO[bloco.tipo] || 'Bloco')));
      item('Editar…', function () { janela({bloco: bloco}); });
      item('Adicionar abaixo…', function () { janela({depois: bloco.id}); });
      item('Subir', function () { acao('mover', bloco.id, {direcao: 'subir'}); });
      item('Descer', function () { acao('mover', bloco.id, {direcao: 'descer'}); });
      item('Excluir', function () {
        if (window.confirm('Remover este bloco?')) acao('excluir', bloco.id);
      }, true);
    } else {
      item('Adicionar bloco aqui…', function () { janela({depois: ''}); });
    }
    abertoEm = Date.now();
    document.body.appendChild(menu);
    var w = menu.offsetWidth, h = menu.offsetHeight;
    menu.style.left = Math.max(4, Math.min(x, window.innerWidth - w - 4)) + 'px';
    menu.style.top = Math.max(4, Math.min(y, window.innerHeight - h - 4)) + 'px';
  }
  raiz.addEventListener('contextmenu', function (e) {
    if (e.target.closest && e.target.closest('.pe-janela')) return;
    e.preventDefault();
    abreMenu(e.clientX, e.clientY, blocoDe(e.target));
  });
  document.addEventListener('click', function (e) {
    if (menu && !menu.contains(e.target)) fechaMenu();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') fechaMenu(); });
  window.addEventListener('scroll', function () { if (Date.now() - abertoEm > 500) fechaMenu(); }, true);

  document.querySelectorAll('[data-pe-novo]').forEach(function (b) {
    b.addEventListener('click', function () { janela({depois: ''}); });
  });

  /* ── janela de edição ── */
  var aberta = null;
  function janela(o) {
    if (aberta) aberta.remove();
    var bloco = o.bloco || null;
    var tipo = bloco ? bloco.tipo : (o.tipo || 'texto');
    var arquivo = o.arquivo || null, biblioteca = '';

    var fundo = el('div', 'pe-fundo');
    var j = el('div', 'pe-janela');
    j.setAttribute('role', 'dialog');
    j.setAttribute('aria-modal', 'true');
    fundo.appendChild(j);
    aberta = fundo;

    j.appendChild(el('h3', '', bloco ? 'Editar ' + esc(NOME_TIPO[tipo].toLowerCase()) : 'Adicionar à página'));

    var abas = el('div', 'pe-abas');
    if (!bloco) {
      TIPOS.forEach(function (t) {
        var b = el('button', t[0] === tipo ? 'ativa' : '', esc(t[1]));
        b.type = 'button';
        b.addEventListener('click', function () { tipo = t[0]; monta(); });
        abas.appendChild(b);
      });
      j.appendChild(abas);
    }
    var corpo = el('div', 'pe-corpo');
    j.appendChild(corpo);
    var erro = el('p', 'pe-erro');
    j.appendChild(erro);
    var rodape = el('div', 'pe-rodape');
    j.appendChild(rodape);

    var campos = {};          // nome -> elemento
    var area = null, salva = null;

    function rotulo(txt, c) { var l = el('label', '', esc(txt)); c.id = c.id || ('pe-' + Math.random().toString(36).slice(2)); l.htmlFor = c.id; return l; }
    function entrada(nome, txt, valor, ph, max) {
      var i = el('input'); i.type = 'text'; i.value = valor || ''; i.maxLength = max || 300;
      if (ph) i.placeholder = ph;
      campos[nome] = i; corpo.appendChild(rotulo(txt, i)); corpo.appendChild(i); return i;
    }
    function seletor(nome, txt, lista, atual) {
      var s = el('select');
      lista.forEach(function (p) {
        var op = el('option', '', esc(p[1])); op.value = p[0];
        if (String(p[0]) === String(atual)) op.selected = true;
        s.appendChild(op);
      });
      var w = el('div'); campos[nome] = s; w.appendChild(rotulo(txt, s)); w.appendChild(s);
      corpo.appendChild(w); return s;
    }
    function campoLink(valor) {
      var i = entrada('url', 'Ao clicar, abrir (opcional)', valor,
                      'escolha uma página ou cole um endereço https://...', 500);
      var dl = el('datalist'); dl.id = 'pe-destinos';
      destinos.forEach(function (d) { dl.appendChild(el('option', '', esc(d[0]))).value = d[1]; });
      i.setAttribute('list', 'pe-destinos'); corpo.appendChild(dl);
      return i;
    }

    function barraTexto() {
      var barra = el('div', 're-barra');
      function btn(rot, cmd, val, tit) {
        var b = el('button', '', rot); b.type = 'button'; b.title = tit || '';
        b.addEventListener('mousedown', function (e) { e.preventDefault(); });
        b.addEventListener('click', function () {
          if (cmd === 'createLink' && !val) {
            var u = window.prompt('Endereço do link (https://... ou /pagina):', 'https://');
            if (!u || u === 'https://') return; comando(cmd, u); return;
          }
          comando(cmd, val);
        });
        barra.appendChild(b);
      }
      function sep() { barra.appendChild(el('span', 're-sep')); }
      btn('<b>N</b>', 'bold', null, 'Negrito'); btn('<i>I</i>', 'italic', null, 'Itálico');
      btn('<u>S</u>', 'underline', null, 'Sublinhado'); sep();
      btn('Título', 'formatBlock', '<h2>'); btn('Subt.', 'formatBlock', '<h3>'); btn('Normal', 'formatBlock', '<p>'); sep();
      btn('• Lista', 'insertUnorderedList'); btn('1. Lista', 'insertOrderedList'); sep();
      btn('Esq.', 'justifyLeft'); btn('Centro', 'justifyCenter'); btn('Dir.', 'justifyRight'); btn('Just.', 'justifyFull'); sep();
      btn('Link', 'createLink', null, 'Transformar a seleção em link');
      var pg = el('select'); pg.title = 'Link para uma página do portal';
      pg.appendChild(el('option', '', 'Link p/ página…')).value = '';
      destinos.forEach(function (d) { pg.appendChild(el('option', '', esc(d[0]))).value = d[1]; });
      pg.addEventListener('change', function () { if (pg.value) comando('createLink', pg.value); pg.value = ''; });
      barra.appendChild(pg);
      btn('Sem link', 'unlink'); sep();
      var cor = el('label', 're-cor', 'Cor '); var ci = el('input'); ci.type = 'color'; ci.value = '#1e293b';
      ci.addEventListener('input', function () { comando('foreColor', ci.value); });
      cor.appendChild(ci); barra.appendChild(cor);
      var tam = el('select'); tam.title = 'Tamanho do texto';
      [['', 'Tamanho'], ['2', 'Pequeno'], ['3', 'Normal'], ['5', 'Grande'], ['6', 'Muito grande'], ['7', 'Enorme']]
        .forEach(function (p) { tam.appendChild(el('option', '', p[1])).value = p[0]; });
      tam.addEventListener('change', function () { if (tam.value) comando('fontSize', tam.value); tam.value = ''; });
      barra.appendChild(tam); sep();
      btn('Limpar', 'removeFormat'); btn('↶', 'undo'); btn('↷', 'redo');
      return barra;
    }
    function comando(c, v) {
      area.focus();
      if (salva) { var s = window.getSelection(); s.removeAllRanges(); s.addRange(salva); }
      document.execCommand(c, false, v || null);
    }
    function aoSelecionar() {
      var s = window.getSelection();
      if (area && s.rangeCount && area.contains(s.anchorNode)) salva = s.getRangeAt(0).cloneRange();
    }
    document.addEventListener('selectionchange', aoSelecionar);

    function zonaImagem() {
      var zona = el('div', 'pe-zona');
      var prev = el('img', 'pe-prev'); prev.alt = '';
      var txt = el('div', 'pe-zona-txt',
        '<strong>Arraste uma imagem para cá</strong><span>ou clique para procurar no computador (também vale colar com Ctrl+V)</span>');
      var input = el('input'); input.type = 'file'; input.accept = '.png,.jpg,.jpeg,.webp,.gif,image/*'; input.hidden = true;
      function mostra() {
        if (arquivo) { prev.src = URL.createObjectURL(arquivo); prev.hidden = false; zona.classList.add('tem'); txt.querySelector('strong').textContent = arquivo.name; }
        else if (bloco && bloco.imagem) { prev.src = bloco.imagem; prev.hidden = false; zona.classList.add('tem'); txt.querySelector('strong').textContent = 'Imagem atual — arraste outra para trocar'; }
        else { prev.hidden = true; }
      }
      function define(f) {
        if (f && /^image\//.test(f.type)) { arquivo = f; biblioteca = ''; mostra(); erro.textContent = ''; }
        else erro.textContent = 'Escolha um arquivo de imagem (PNG, JPG, WEBP ou GIF).';
      }
      var bib = el('button', 'btn btn-sm', 'Escolher da biblioteca'); bib.type = 'button';
      bib.addEventListener('click', function (e) {
        e.stopPropagation();
        if (!window.SeletorMidia) { erro.textContent = 'A biblioteca não está disponível.'; return; }
        window.SeletorMidia.abrir({lista: '/admin/midia/lista', enviar: '/admin/midia/enviar', csrf: csrf,
          aoEscolher: function (i) { arquivo = null; biblioteca = i.arquivo; prev.src = i.url; prev.hidden = false; zona.classList.add('tem'); txt.querySelector('strong').textContent = i.nome; erro.textContent = ''; }});
      });
      zona.addEventListener('click', function () { input.click(); });
      input.addEventListener('change', function () { if (input.files[0]) define(input.files[0]); });
      ['dragenter', 'dragover'].forEach(function (n) { zona.addEventListener(n, function (e) { e.preventDefault(); e.stopPropagation(); zona.classList.add('sobre'); }); });
      ['dragleave', 'drop'].forEach(function (n) { zona.addEventListener(n, function (e) { e.preventDefault(); e.stopPropagation(); zona.classList.remove('sobre'); }); });
      zona.addEventListener('drop', function (e) { if (e.dataTransfer.files[0]) define(e.dataTransfer.files[0]); });
      j.addEventListener('paste', function (e) {
        var its = (e.clipboardData || {}).items || [];
        for (var k = 0; k < its.length; k++) if (its[k].type.indexOf('image/') === 0) { define(its[k].getAsFile()); e.preventDefault(); return; }
      });
      zona.appendChild(prev); zona.appendChild(txt); zona.appendChild(bib); zona.appendChild(input);
      mostra();
      return zona;
    }

    function monta() {
      corpo.innerHTML = ''; campos = {}; area = null; erro.textContent = '';
      Array.prototype.forEach.call(abas.children, function (b, k) { b.classList.toggle('ativa', TIPOS[k][0] === tipo); });
      var d = bloco || {};
      if (tipo === 'texto') {
        corpo.appendChild(barraTexto());
        area = el('div', 're-area pagina-texto'); area.contentEditable = 'true';
        area.setAttribute('role', 'textbox'); area.setAttribute('aria-multiline', 'true');
        area.innerHTML = d.texto || '';
        corpo.appendChild(area);
        corpo.appendChild(el('p', 'dica', 'Escreva, cole ou arraste texto para cá. Selecione o trecho e use os botões; para criar um link, use “Link p/ página…”.'));
        seletor('estilo', 'Aparência do bloco', opc.estilos, d.estilo || 'normal');
        try { document.execCommand('defaultParagraphSeparator', false, 'p'); document.execCommand('styleWithCSS', false, false); } catch (e) {}
        setTimeout(function () { area.focus(); }, 30);
      } else if (tipo === 'subtitulo') {
        entrada('texto', 'Subtítulo', d.texto, '', 200).focus();
        campoLink(d.url);
      } else if (tipo === 'botao') {
        entrada('texto', 'Texto do botão', d.texto, '', 100).focus();
        campoLink(d.url);
        seletor('alinh', 'Posição', opc.alinhamentos, d.alinh || 'esq');
      } else {
        corpo.appendChild(zonaImagem());
        entrada('texto', 'Legenda (opcional)', d.texto, '', 300);
        campoLink(d.url);
        var duas = el('div', 'pe-duas'); corpo.appendChild(duas);
        var antes = corpo;
        corpo = duas; seletor('larg', 'Largura na página', opc.larguras, d.larg || 100);
        seletor('alinh', 'Posição', opc.alinhamentos, d.alinh || 'centro'); corpo = antes;
        // os dois seletores foram criados dentro da grade; os rótulos vão junto
      }
    }

    var vis = el('label', 'check');
    var cb = el('input'); cb.type = 'checkbox'; cb.checked = bloco ? bloco.ativo : true;
    vis.appendChild(cb); vis.appendChild(document.createTextNode(' Exibir na página'));
    rodape.appendChild(vis);

    var salvar = el('button', 'btn btn-principal', 'Salvar'); salvar.type = 'button';
    var cancelar = el('button', 'btn', 'Cancelar'); cancelar.type = 'button';
    rodape.appendChild(salvar); rodape.appendChild(cancelar);
    if (bloco) {
      var ex = el('button', 'btn perigo', 'Excluir'); ex.type = 'button';
      ex.addEventListener('click', function () { if (window.confirm('Remover este bloco?')) acao('excluir', bloco.id); });
      rodape.appendChild(ex);
    }

    function fecha() { document.removeEventListener('selectionchange', aoSelecionar); fundo.remove(); aberta = null; }
    cancelar.addEventListener('click', fecha);
    fundo.addEventListener('mousedown', function (e) { if (e.target === fundo) fecha(); });
    document.addEventListener('keydown', function esc(e) {
      if (!aberta) { document.removeEventListener('keydown', esc); return; }
      if (e.key === 'Escape') { fecha(); document.removeEventListener('keydown', esc); }
    });

    salvar.addEventListener('click', function () {
      var fd = new FormData();
      fd.append('tipo', tipo);
      if (bloco) fd.append('id', bloco.id);
      else if (o.depois !== undefined) fd.append('depois', o.depois === '' ? '' : String(o.depois));
      if (cb.checked) fd.append('ativo', 'on');
      if (tipo === 'texto') {
        if (!area.textContent.trim() && !area.querySelector('li')) { erro.textContent = 'Escreva o texto antes de salvar.'; return; }
        fd.append('html', area.innerHTML);
      }
      Object.keys(campos).forEach(function (k) { fd.append(k, campos[k].value); });
      if (tipo === 'imagem') {
        if (arquivo) fd.append('arquivo', arquivo, arquivo.name);
        else if (biblioteca) fd.append('arquivo_biblioteca', biblioteca);
        else if (!bloco) { erro.textContent = 'Escolha uma imagem.'; return; }
      }
      salvar.disabled = true;
      enviar(fd, erro).then(function () { salvar.disabled = false; });
    });

    document.body.appendChild(fundo);
    monta();
  }

  /* ── soltar uma imagem direto sobre a página ── */
  function temArquivo(e) {
    var t = e.dataTransfer; if (!t) return false;
    return Array.prototype.indexOf.call(t.types || [], 'Files') >= 0;
  }
  raiz.addEventListener('dragover', function (e) { if (temArquivo(e)) { e.preventDefault(); raiz.classList.add('pe-solta'); } });
  raiz.addEventListener('dragleave', function (e) { if (!raiz.contains(e.relatedTarget)) raiz.classList.remove('pe-solta'); });
  raiz.addEventListener('drop', function (e) {
    raiz.classList.remove('pe-solta');
    if (!temArquivo(e) || e.target.closest('.pe-janela')) return;
    e.preventDefault();
    var f = e.dataTransfer.files[0];
    if (!f || !/^image\//.test(f.type)) { window.alert('Solte um arquivo de imagem (PNG, JPG, WEBP ou GIF).'); return; }
    var b = blocoDe(e.target);
    if (b && b.tipo === 'imagem') janela({bloco: b, arquivo: f});
    else janela({tipo: 'imagem', depois: b ? b.id : '', arquivo: f});
  });
})();
